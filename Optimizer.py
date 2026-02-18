import orhelper
import jpype
import numpy as np
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args

# TODO:
# - Add more design variables (Nose Cone Shape, Fin Count, Material Density)
# - Add more penalties (Structural Mass, Cost, etc.)
# - Refactor to support multiple optimizers (Random Search, TPE, etc.)

# Access the Java Enum directly
def list_flight_data_types():        
    try:
        FlightDataType = jpype.JPackage("net").sf.openrocket.simulation.FlightDataType
            
        # Print all valid names
        for field in FlightDataType.values():
            print(f"'{field.name()}'")
    except Exception as e:
        print(f"Could not list types: {e}")
    
class Optimizer:
    def __init__(self, rocket_instance, ROCKET_FILE):
        self.orh = orhelper.Helper(rocket_instance)
        self.doc = self.orh.load_doc(ROCKET_FILE)
        self.sim = self.doc.getSimulation(0)
        self.FlightDataType = jpype.JPackage("net").sf.openrocket.simulation.FlightDataType
        self.rocket = self.doc.getRocket()
        self.components = []
        self.setup_components(self.rocket)
        # Search Space
        self.space = [
            Real(0.48, 1, name='top_tube_length'),    # Tube m
            Real(0.03, 0.25, name='fin_height'),     # Height m
            Real(0.03, 0.25, name='root_chord'),   # Root Chord m
            Real(0.01, 0.5, name='tip_chord'),      # Tip Chord m
            Real(0.01, 0.5, name='fin_sweep'),      # Sweep m
            Real(0.0, 0.50, name='fin_bottom_offset'), # position of fin relative to bottom of tube m
            Real(0.0, 0.4, name='vary_mass'),      # Vary Mass kg
            Real(0.0, self.rocket.getLength(), name='vary_position')       # Position m
        ]

    def setup_components(self, component):
        name = str(component.getName())
        self.components.append((name, component))
        
        for child in component.getChildren():
            self.setup_components(child)

    def get_component(self, name):
        for comp_name, comp in self.components:
            if comp_name == name:
                return comp
        return None

    # --- RUN OPTIMIZATION ---
    def run_optimizer(self, TARGET_ALTITUDE, iterations=50):
        print(f"🚀 Starting Optimization Run ({iterations} Iterations)...")
        best_apogee = 0.0

        @use_named_args(self.space)
        def objective_function(top_tube_length, fin_height, root_chord, tip_chord, 
                               fin_sweep, fin_bottom_offset, vary_mass, vary_position):
            # Mod Rocket
            try:
                # --- TUBE ---
                tube = self.get_component("Top Tube")
                if tube: 
                    tube.setLength(top_tube_length)
                    if tube.getLength() != top_tube_length:
                        print(f"⚠️ Warning: Tube length not set correctly. Expected {top_tube_length}, got {tube.getLength()}") 
                else:
                    print(f"❌ ERROR: Could not find component top tube")

                # --- FINS ---
                fins = self.get_component("Trapezoidal Fin Set")
                if fins:
                    fins.setHeight(fin_height)
                    fins.setRootChord(root_chord)
                    if fins.getRootChord() != root_chord:
                        print(f"⚠️ Warning: Root chord not set correctly. Expected {root_chord}, got {fins.getRootChord()}")    
                    fins.setTipChord(tip_chord)
                    fins.setSweep(fin_sweep)

                    # --- APPLY DISTANCE FROM TOP ---
                    parent = fins.getParent()
                    if parent:
                        parent_len = parent.getLength()

                        # Formula: Length - Root - Offset
                        calculated_pos = parent_len - root_chord - fin_bottom_offset
                        fins.setAxialOffset(calculated_pos)
                    else:
                        print("❌ ERROR: Could not find component Trapezoidal Fin Set")

                # --- Vary Mass & Position ---
                custom_vary_mass = self.get_component("Var Mass")
                if custom_vary_mass:
                    custom_vary_mass.setMassOverridden(True)
                    custom_vary_mass.setOverrideMass(vary_mass)
                    custom_vary_mass.setAxialOffset(vary_position)
                else:
                    print("❌ ERROR: Could not find component Vary Mass")

            except Exception as e:
                print(f"❌ Design Error: {e}")
                return 99999.0 # Massive penalty for crashing

            # Run Simulation
            try:
                self.sim = self.doc.getSimulation(0) # Reset sim to clear old data
                self.orh.run_simulation(self.sim)
                data = self.sim.getSimulatedData().getBranch(0)
                
                # Extract Flight Data
                alt_arr = np.array(data.get(self.FlightDataType.TYPE_ALTITUDE))
                stab_arr = np.array(data.get(self.FlightDataType.TYPE_STABILITY))
                # vel_arr = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))
                
                apogee = max(alt_arr)
                if apogee < 100:
                    return 100000000
                nonlocal best_apogee
                if apogee > best_apogee:
                    best_apogee = apogee
            except Exception as e:
                print(f"❌ Simulation Error: {e}")

            # Compute metrics
            FlightEventType = jpype.JPackage("net").sf.openrocket.simulation.FlightEvent.Type
            time_arr = np.array(data.get(self.FlightDataType.TYPE_TIME))
            sim_config = self.sim.getOptions()
            rail_length = sim_config.getLaunchRodLength()
            events = data.getEvents()
            burnout_time = 0.0
            found_burnout = False

            for event in events:
                if event.getType() == FlightEventType.BURNOUT:
                    burnout_time = event.getTime()
                    found_burnout = True
                    break
            
            if not found_burnout:
                burnout_time = time_arr[-1]

            end_index = np.searchsorted(time_arr, burnout_time)
            rail_indices = np.where(alt_arr >= rail_length)[0]
            
            if len(rail_indices) > 0:
                start_index = rail_indices[0]
            else:
                start_index = 0

            if end_index > start_index:
                boost_stability = stab_arr[start_index:end_index]
            else:
                boost_stability = [] # Flight was too short to measure

            valid_stab = boost_stability[~np.isnan(boost_stability)]
            if len(valid_stab) == 0:
                print("💥 unstable crash (All NaN)")
                return 100000000.0
            else:
                avg_stab = np.mean(valid_stab) # The "General Health"
                min_stab = np.min(valid_stab)  # The "Worst Moment"

            ## Compute Loss with Penalties
            loss = abs(apogee - TARGET_ALTITUDE)
            
            # Safety Check: Did it ever dip below 1.5? (Dangerous!)
            if min_stab < 1.5:
                penalty = (1.5 - min_stab) * 100000
                loss += penalty
                print(f"⚠️ Dangerous Instability Detected (Min: {min_stab:.2f})")

            # Optimization Check: Is the average too low? (Wobbly flight)
            if avg_stab < 1.75:
                loss += 2000 * (1.75 - avg_stab) ** 2

            if avg_stab > 2:
                loss += 5000 * (avg_stab - 2) ** 2

            # Constraint: Sweep length cannot be more than 2x the Root Chord
            if fin_sweep > (root_chord * 2.0):
                penalty = (fin_sweep - (root_chord * 2.0)) * 5000
                loss += penalty

            # Constraint: Penalty grows as the violation gets worse
            if tip_chord > 2 * root_chord:
                penalty = (tip_chord - 2 * root_chord) * 10000 
                loss += penalty

            return loss

        # Run the optimizer
        res = gp_minimize(
            objective_function,
            self.space,
            n_calls=iterations,            
            n_random_starts=int(iterations * 0.5),
            noise=1e-6,            
            random_state=42        
        )

        return (res, best_apogee)
    
    # --- ADD THIS TO Optimizer.py ---
    def verify_and_save(self, best_params, filename="optimized_rocket.ork"):
        print("\n" + "="*40)
        print("🔍 VERIFYING BEST SOLUTION")
        print("="*40)

        # 1. UNPACK PARAMETERS
        # ⚠️ CRITICAL: This must match the order in self.space EXACTLY
        # If you switched to Ratios, update these variable names!
        top_tube_length, fin_height, root_chord, tip_chord, \
        fin_sweep, fin_position, vary_mass, vary_position = best_params

        print(f"📝 Applying parameters:\n"
            f"   - Tube Len: {top_tube_length * 100:.2f} cm\n"
            f"   - Fin Height: {fin_height * 100:.2f} cm\n"
            f"   - Fin Root: {root_chord * 100:.2f} cm\n"
            f"   - Fin Tip:  {tip_chord * 100:.2f} cm\n"
            f"   - Sweep:    {fin_sweep * 100:.2f} cm\n"
            f"   - Fin Pos:  {fin_position * 100:.2f} cm\n"
            f"   - Var Mass: {vary_mass * 1000:.0f} g\n"
            f"   - Var Pos:  {vary_position * 100:.2f} cm\n")
        
        # 2. APPLY TO ROCKET (Same logic as objective_function)
        # --- TUBE ---
        tube = self.get_component("Top Tube") # Verify this name!
        if tube: tube.setLength(top_tube_length)

        # --- FINS ---
        fins = self.get_component("Trapezoidal Fin Set") # Verify this name!
        if fins:
            fins.setHeight(fin_height)
            fins.setRootChord(root_chord)
            fins.setTipChord(tip_chord)
            fins.setSweep(fin_sweep)
            
            # Position Logic
            parent = fins.getParent()
            if parent:
                tube_len = parent.getLength()
                pos_from_top = tube_len + fin_position - root_chord
                if pos_from_top < 0: pos_from_top = 0
                fins.setAxialOffset(pos_from_top)

        # --- MASS ---
        mass_comp = self.get_component("Var Mass") # Verify this name!
        if mass_comp:
            mass_comp.setMassOverridden(True)
            mass_comp.setOverrideMass(vary_mass)
            mass_comp.setAxialOffset(vary_position)

        # 3. REFRESH & RUN SIMULATION
        self.sim = self.doc.getSimulation(0) # Get fresh sim instance
        self.sim.getOptions().setLaunchRodLength(1) 
        
        print("🏃 Running Final Simulation...")
        self.orh.run_simulation(self.sim)
        sim_data = self.sim.getSimulatedData()
        data = sim_data.getBranch(0)
        
        # Get Events from the PARENT object (sim_data), not the branch
        events = data.getEvents() 
        FlightEventType = jpype.JPackage("net").sf.openrocket.simulation.FlightEvent.Type
        
        # Calculate Burnout
        burnout_time = 0.0
        found_burnout = False
        for event in events:
            if event.getType() == FlightEventType.BURNOUT:
                burnout_time = event.getTime()
                found_burnout = True
                break
        
        if not found_burnout:
             time_arr = np.array(data.get(self.FlightDataType.TYPE_TIME))
             burnout_time = time_arr[-1]

        # Calculate Stability Window
        stab = np.array(data.get(self.FlightDataType.TYPE_STABILITY))
        time = np.array(data.get(self.FlightDataType.TYPE_TIME))
        
        # Rail Exit Index
        rail_len = self.sim.getOptions().getLaunchRodLength()
        alt = np.array(data.get(self.FlightDataType.TYPE_ALTITUDE))
        rail_indices = np.where(alt >= rail_len)[0]
        start_idx = rail_indices[0] if len(rail_indices) > 0 else 0
        
        # Burnout Index
        end_idx = np.searchsorted(time, burnout_time)
        
        # Compute Stats
        if end_idx > start_idx:
            boost_stab = stab[start_idx:end_idx]
            valid_stab = boost_stab[~np.isnan(boost_stab)]
            if len(valid_stab) > 0:
                avg_stab = np.mean(valid_stab)
                min_stab = np.min(valid_stab)
            else:
                avg_stab = 0.0
                min_stab = 0.0
        else:
            avg_stab = 0.0
            min_stab = 0.0

        # Extract other stats
        apogee = max(alt)
        max_vel = max(np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL)))
        max_mach = max_vel / 343.0
        rail_exit_vel = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))[start_idx]

        # 5. PRINT REPORT
        print("-" * 30)
        # print(stab)
        print(f"✅ FINAL RESULTS:")
        print(f"   🎯 Apogee:         {apogee:.2f} m  ({(apogee*3.28084):.0f} ft)")
        print(f"   💨 Max Velocity:   {max_vel:.1f} m/s (Mach {max_mach:.2f})")
        print(f"   🚀 Rail Exit Vel:  {rail_exit_vel:.1f} m/s")
        print(f"   🧠 Avg Stability:  {avg_stab:.2f} cal")
        print(f"   🧠 Min Stability:  {min_stab:.2f} cal")
        print("-" * 30)

        # 7. SAVE FILE (The Correct Way)
        print(f"💾 Saving optimized design to '{filename}'...")

        try:
            # 1. Setup Stream
            fos = jpype.JPackage("java.io").FileOutputStream(filename)
            
            # 2. Setup Helper Objects (REQUIRED by the function signature)
            # We need to create empty containers for warnings/errors/options
            StorageOptions = jpype.JPackage("net.sf.openrocket.document").StorageOptions
            options = StorageOptions() # Default options
            
            WarningSet = jpype.JPackage("net.sf.openrocket.logging").WarningSet
            warnings = WarningSet()
            
            ErrorSet = jpype.JPackage("net.sf.openrocket.logging").ErrorSet
            errors = ErrorSet()
            
            # 3. Get the Saver
            Saver = jpype.JPackage("net.sf.openrocket.file.openrocket").OpenRocketSaver()
            
            # 4. SAVE (Pass all 5 arguments)
            # Signature: save(OutputStream, Document, StorageOptions, WarningSet, ErrorSet)
            Saver.save(fos, self.doc, options, warnings, errors)
            
            fos.close()
            print("Done.")
            
        except Exception as e:
            print(f"❌ Save Failed: {e}")
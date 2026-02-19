import orhelper
import jpype
import numpy as np
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args
from scipy.optimize import minimize

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
        halfcluster = 35.5 / 100.0 # cm to m
        nosefit = 13.5 / 100.0 # cm to m
        moterfit = 35.5 / 100.0 # cm to m
        self.space = [
            Real(halfcluster + nosefit, 1, name='top_tube_length'),    # Total Tube m
            Real(halfcluster + moterfit, 1.25, name='bottom_tube_length'),     # Bottom Tube m
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

    # --- 1. THE SHARED PHYSICS ENGINE ---
    def calculate_loss(self, x, TARGET_ALTITUDE):
        # Initialize apogee tracker safely
        if not hasattr(self, 'best_apogee'):
            self.best_apogee = 0.0

        # Unpack the list 'x' into your variables
        top_tube_length, bottom_tube_length, fin_height, root_chord, tip_chord, \
        fin_sweep, fin_bottom_offset, vary_mass, vary_position = x

        try:
            # --- TUBE ---
            top_tube = self.get_component("Top Tube")
            bottom_tube = self.get_component("Bottom Tube")
            if top_tube: 
                top_tube.setLength(top_tube_length)
            if bottom_tube:
                bottom_tube.setLength(bottom_tube_length)

            # --- FINS ---
            fins = self.get_component("Trapezoidal Fin Set")
            if fins:
                fins.setHeight(fin_height)
                fins.setRootChord(root_chord)
                fins.setTipChord(tip_chord)
                fins.setSweep(fin_sweep)

                # --- APPLY DISTANCE FROM TOP ---
                parent = fins.getParent()
                if parent:
                    parent_len = parent.getLength()
                    calculated_pos = parent_len - root_chord - fin_bottom_offset
                    fins.setAxialOffset(calculated_pos)

            # --- Vary Mass & Position ---
            custom_vary_mass = self.get_component("Var Mass")
            if custom_vary_mass:
                custom_vary_mass.setMassOverridden(True)
                custom_vary_mass.setOverrideMass(vary_mass)
                custom_vary_mass.setAxialOffset(vary_position)

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
            vel_arr = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))
            
            apogee = max(alt_arr)
            if apogee < 100:
                return 100000000.0
                
            if apogee > self.best_apogee:
                self.best_apogee = apogee
                
        except Exception as e:
            print(f"❌ Simulation Error: {e}")
            return 100000000.0

        # Compute metrics
        FlightEventType = jpype.JPackage("net").sf.openrocket.simulation.FlightEvent.Type
        time_arr = np.array(data.get(self.FlightDataType.TYPE_TIME))
        sim_config = self.sim.getOptions()
        rail_length = sim_config.getLaunchRodLength()
        if rail_length < 2.44: 
            rail_length = 2.44 # 8 ft minimum for a real rocket
            print(f"⚠️  Warning: Rail length too short ({rail_length} m). Adjusting to 2.44 m for calculations.")
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
        
        start_index = rail_indices[0] if len(rail_indices) > 0 else 0

        if end_index > start_index:
            boost_stability = stab_arr[start_index:end_index]
        else:
            boost_stability = []

        rail_exit_vel = vel_arr[start_index] if start_index < len(vel_arr) else 0.0
        valid_stab = boost_stability[~np.isnan(boost_stability)]
        
        if len(valid_stab) == 0:
            return 100000000.0
        else:
            avg_stab = np.mean(valid_stab) 
            min_stab = np.min(valid_stab)  

        # --- LOSS CALCULATION ---
        loss = ((abs(apogee - TARGET_ALTITUDE) / 20.0) ** 2) * 100000

        if min_stab < 1.6:
            loss += ((1.6 - min_stab) + 10000) ** 2
        if avg_stab > 2:
            loss += ((avg_stab - 2) + 100) ** 2
        if fin_sweep > 2 * root_chord:
            loss += ((fin_sweep - root_chord) + 10000) ** 2
        if tip_chord > 2 * root_chord:
            loss += ((tip_chord - root_chord) + 10000) ** 2
        if rail_exit_vel < 13.0: 
            loss += ((13.0 - rail_exit_vel) + 10000) ** 2

        return loss

    # --- 2. STAGE 1: THE GLOBAL SCANNER (Bayesian) ---
    def run_stage1_global(self, TARGET_ALTITUDE, iterations=50):
        print(f"\n🚀 STAGE 1: Global Search ({iterations} Iterations)...")
        self.best_apogee = 0.0 # Reset tracking

        # Wrapper to convert skopt's dictionary to a flat list for our shared function
        @use_named_args(self.space)
        def objective_wrapper(**kwargs):
            x = [kwargs[dim.name] for dim in self.space]
            return self.calculate_loss(x, TARGET_ALTITUDE)

        res = gp_minimize(
            objective_wrapper,
            self.space,
            n_calls=iterations,            
            n_random_starts=int(iterations * 0.4),
            noise=1e-6,            
            random_state=42        
        )
        print(f"✅ STAGE 1 COMPLETE. Best Score: {res.fun:.4f}")
        return res, self.best_apogee

    # --- 3. STAGE 2: THE LOCAL CLIMBER (Nelder-Mead) ---
    def run_stage2_local(self, start_params, TARGET_ALTITUDE, max_iter=40, tolerance=1e-3):
        print(f"\n🏔️ STAGE 2: Nelder-Mead Refinement ({max_iter} max iterations)")
        print("   Walking the simplex to the local minimum...")
        
        # Define physical constraints from your search space so Scipy doesn't go out of bounds
        bounds = [(dim.low, dim.high) for dim in self.space]

        # Wrapper with an "Electric Fence" penalty
        def bounded_objective(x):
            penalty = 0.0
            is_out_of_bounds = False
            
            # 1. Check every variable against its min/max limits
            for i, val in enumerate(x):
                low, high = bounds[i]
                if val < low:
                    # Penalize based on how far out of bounds it went
                    penalty += (low - val) * 10000000
                    is_out_of_bounds = True
                elif val > high:
                    penalty += (val - high) * 10000000
                    is_out_of_bounds = True
            
            # 2. If it stepped out of bounds, DO NOT run the simulation.
            # Just return the massive penalty so the optimizer retreats.
            if is_out_of_bounds:
                return 1000000000.0 + penalty

            # 3. If it is safely inside the bounds, run the actual physics
            return self.calculate_loss(x, TARGET_ALTITUDE)

        # Run the geometric walk
        result = minimize(
            bounded_objective, 
            x0=start_params, 
            method='Nelder-Mead', 
            options={
                'maxiter': max_iter, 
                'disp': True,        # Prints Scipy's convergence messages
                'xatol': tolerance,  # Stops if it stops moving
                'fatol': tolerance   # Stops if the score stops improving
            }
        )

        print(f"\n🎉 STAGE 2 FINISHED.")
        print(f"   Success: {result.success}")
        print(f"   Final Score: {result.fun:.4f}")
        return result.x
    
    def verify_and_save(self, best_params, filename="optimized_rocket.ork"):
        print("\n" + "="*40)
        print("🔍 VERIFYING BEST SOLUTION")
        print("="*40)

        # UNPACK PARAMETERS
        # ⚠️ CRITICAL: This must match the order in self.space EXACTLY
        top_tube_length, bottom_tube_length, fin_height, root_chord, tip_chord, \
        fin_sweep, fin_bottom_offset, vary_mass, vary_position = best_params
        
        # APPLY TO ROCKET 
        # --- TUBE ---
        top_tube = self.get_component("Top Tube")
        bottom_tube = self.get_component("Bottom Tube")
        if top_tube: 
            top_tube.setLength(top_tube_length)
        if bottom_tube:
            bottom_tube.setLength(bottom_tube_length)

        # --- FINS ---
        fins = self.get_component("Trapezoidal Fin Set")
        calculated_pos = None
        if fins:
            fins.setHeight(fin_height)
            fins.setRootChord(root_chord)
            fins.setTipChord(tip_chord)
            fins.setSweep(fin_sweep)
            
            # --- APPLY DISTANCE FROM TOP ---
            parent = fins.getParent()
            if parent:
                parent_len = parent.getLength()
                # Formula: Length - Root - Offset
                calculated_pos = parent_len - root_chord - fin_bottom_offset
                fins.setAxialOffset(calculated_pos)

        # --- MASS ---
        mass_comp = self.get_component("Var Mass")
        if mass_comp:
            mass_comp.setMassOverridden(True)
            mass_comp.setOverrideMass(vary_mass)
            mass_comp.setAxialOffset(vary_position)

        print(f"📝 Applying parameters:\n"
            f"   - Top Tube Len: {top_tube_length * 100:.2f} cm\n"
            f"   - Bottom Tube Len:  {bottom_tube_length * 100:.2f} cm\n"
            f"   - Fin Height: {fin_height * 100:.2f} cm\n"
            f"   - Fin Root: {root_chord * 100:.2f} cm\n"
            f"   - Fin Tip:  {tip_chord * 100:.2f} cm\n"
            f"   - Sweep:    {fin_sweep * 100:.2f} cm\n"
            f"   - Fin Pos from top:  {calculated_pos * 100:.2f} cm (Offset: {fin_bottom_offset * 100:.2f} cm)\n"
            f"   - Var Mass: {vary_mass * 1000:.0f} g\n"
            f"   - Var Pos:  {vary_position * 100:.2f} cm\n")
        
        # REFRESH & RUN SIMULATION
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
        if rail_len < 2.44:
            rail_len = 2.44 # 8 ft minimum for a real rocket
            print(f"⚠️  Warning: Rail length too short ({rail_len} m). Adjusting to 2.44 m for calculations.")
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
            fos = jpype.JPackage("java.io").FileOutputStream(filename)
            StorageOptions = jpype.JPackage("net.sf.openrocket.document").StorageOptions
            options = StorageOptions() # Default options
            WarningSet = jpype.JPackage("net.sf.openrocket.logging").WarningSet
            warnings = WarningSet()
            ErrorSet = jpype.JPackage("net.sf.openrocket.logging").ErrorSet
            errors = ErrorSet()
            Saver = jpype.JPackage("net.sf.openrocket.file.openrocket").OpenRocketSaver()
            Saver.save(fos, self.doc, options, warnings, errors)
            fos.close()
            print("Done.")
            
        except Exception as e:
            print(f"❌ Save Failed: {e}")
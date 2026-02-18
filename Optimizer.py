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
            # Real(0.0, 1.3, name='fin_angle'),      # Angle rads
            Real(-0.20, 0.0, name='fin_position'),   # Position m (Negative is forward)
            # Real(0.0, 1.0, name='nose_mass'),      # Nose Mass kg
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
                               fin_sweep, fin_position, vary_mass, vary_position):
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
                    # fins.setCantAngle(fin_angle) 
                    # Set Position (Relative to BOTTOM)
                    parent = fins.getParent()
                    if parent:
                        tube_len = parent.getLength()
                        pos_from_top = tube_len + fin_position - root_chord
                        if pos_from_top < 0: pos_from_top = 0 
                        fins.setAxialOffset(pos_from_top)
                else:
                    print("❌ ERROR: Could not find component Trapezoidal Fin Set")

                # # --- NOSE BALLAST ---
                # ballast = self.get_component("Nose Mass")
                # if ballast: 
                #     ballast.setMass(nose_mass)

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
                vel_arr = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))
                
                apogee = max(alt_arr)
                if apogee < 100:
                    return 100000000
                nonlocal best_apogee
                if apogee > best_apogee:
                    best_apogee = apogee
            except Exception as e:
                print(f"❌ Simulation Error: {e}")

            # Calculate Loss (Distance from Target)
            loss = abs(apogee - TARGET_ALTITUDE)

            sim_config = self.sim.getOptions()
            rail_length = sim_config.getLaunchRodLength()
            rail_indices = np.where(alt_arr >= rail_length)[0]

            if len(rail_indices) > 0:
                launch_stab = stab_arr[rail_indices[0]]
            else:
                launch_stab = -10.0

            # If OpenRocket failed to calculate stability, it returns NaN.
            # We must treat this as a CRITICAL FAILURE.
            if np.isnan(launch_stab):
                print("⚠️ Stability is NaN (Math Error) - Penalizing!")
                return 100000000.0 # Instant Death Penalty

            # Penalty: Unstable
            if launch_stab < 1.8:
                 loss += 50000 * (1.8 - launch_stab) ** 2

            # Constraint: Sweep length cannot be more than 2x the Root Chord
            if fin_sweep > (root_chord * 2.0):
                penalty = (fin_sweep - (root_chord * 2.0)) * 5000
                loss += penalty

            # Penalty grows as the violation gets worse
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
              f"   - Tube Len: {top_tube_length:.3f} m\n"
              f"   - Fin Root: {root_chord:.3f} m\n"
              f"   - Fin Tip:  {tip_chord:.3f} m\n"
              f"   - Sweep:    {fin_sweep:.3f} m")

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
        data = self.sim.getSimulatedData().getBranch(0)

        # 4. EXTRACT FINAL STATS
        alt = data.get(self.FlightDataType.TYPE_ALTITUDE)
        vel = data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL)
        stab = data.get(self.FlightDataType.TYPE_STABILITY)
        
        apogee = max(alt)
        max_vel = max(vel)
        max_mach = max_vel / 343.0
        
        # Calculate Stability off the Rail
        rail_len = self.sim.getOptions().getLaunchRodLength()
        rail_indices = [i for i, h in enumerate(alt) if h >= rail_len]
        
        if rail_indices:
            rail_exit_stab = stab[rail_indices[0]]
            rail_exit_vel = vel[rail_indices[0]]
        else:
            rail_exit_stab = 0.0
            rail_exit_vel = 0.0

        # 5. PRINT REPORT
        print("-" * 30)
        print(f"✅ FINAL RESULTS:")
        print(f"   🎯 Apogee:         {apogee:.2f} m  ({(apogee*3.28084):.0f} ft)")
        print(f"   ⚖️ Launch Stab:    {rail_exit_stab:.2f} cal")
        print(stab)
        print(f"   💨 Max Velocity:   {max_vel:.1f} m/s (Mach {max_mach:.2f})")
        print(f"   🚀 Rail Exit Vel:  {rail_exit_vel:.1f} m/s")
        print("-" * 30)

        # 6. SAVE FILE
        print(f"💾 Saving optimized design to '{filename}'...")
        self.doc.save(filename)
        print("Done.")
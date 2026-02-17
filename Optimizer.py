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
        # Search Space
        self.space = [
            Real(0.4, 2.5, name='top_tube_length'),    # Tube m
            Real(0.005, 0.25, name='fin_height'),     # Span m
            Real(0.005, 0.25, name='root_chord'),   # Root Chord m
            Real(0.0, 1.0, name='tip_chord'),      # Tip Chord m
            Real(0.0, 1.0, name='fin_sweep'),      # Sweep m
            Real(0.0, 1.35, name='fin_angle'),      # Angle rads
            Real(-0.20, 0.0, name='fin_position'),   # Position m (Negative is forward)
            Real(0.0, 1.0, name='nose_mass'),      # Nose Mass kg
            Real(0.0, 1.0, name='vary_mass'),      # Vary Mass kg
            Real(0.05, self.rocket.getLength(), name='vary_position')       # Position m
        ]
        self.components = []
        self.setup_components(self.rocket)

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
        @use_named_args(self.space)
        def objective_function(top_tube_length, fin_height, root_chord, tip_chord, 
                               fin_sweep, fin_angle, fin_position, nose_mass, vary_mass, vary_position):
            # Mod Rocket
            try:
                # --- TUBE ---
                tube = self.get_component("Top Tube")
                if tube: 
                    tube.setLength(top_tube_length)

                # --- FINS ---
                fins = self.get_component("Trapezoidal Fin Set")
                if fins:
                    fins.setSpan(fin_height)
                    fins.setRootChord(root_chord)
                    fins.setTipChord(tip_chord)
                    fins.setSweepLength(fin_sweep)
                    fins.setCantAngle(fin_angle) 
                    fins.setPositionValue(fin_position)

                # --- NOSE BALLAST ---
                ballast = self.get_component("Nose Mass")
                if ballast: 
                    ballast.setMass(nose_mass)

                # --- Vary Mass & Position ---
                custom_vary_mass= self.get_component("Vary Mass")
                if custom_vary_mass: 
                    custom_vary_mass.setMass(vary_mass)
                    custom_vary_mass.setPositionValue(vary_position)

            except Exception as e:
                print(f"❌ Design Error: {e}")
                return 99999.0 # Massive penalty for crashing

            # Run Simulation
            try:
                self.orh.run_simulation(self.sim)
                data = self.sim.getSimulatedData().getBranch(0)
                
                # Extract Flight Data
                alt_arr = np.array(data.get(self.FlightDataType.TYPE_ALTITUDE))
                # stab_arr = np.array(data.get(self.FlightDataType.TYPE_STABILITY))
                # vel_arr = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))
                
                apogee = max(alt_arr)
            except Exception as e:
                print(f"❌ Simulation Error: {e}")
                return 99999.0

            # 3. Calculate Loss (Distance from Target)
            loss = abs(apogee - TARGET_ALTITUDE)

            # --- OPTIONAL PENALTIES (Uncomment if needed) ---
            # # Get Rail Exit Data (approx 2.44m / 8ft)
            # rail_indices = np.where(alt_arr >= 2.44)[0]
            # if len(rail_indices) > 0:
            #     launch_stab = stab_arr[rail_indices[0]]
            #     launch_vel = vel_arr[rail_indices[0]]
            # else:
            #     launch_stab = 0.0; launch_vel = 0.0

            # # Penalty: Unstable (< 1.5 cal)
            # if launch_stab < 1.5:
            #     loss += 5000 * (1.5 - launch_stab) ** 2

            # print(f"   Alt: {apogee*3.28:.0f}ft | Loss: {loss:.2f}")
            return loss

        # Run the optimizer
        res = gp_minimize(
            objective_function,
            self.space,
            n_calls=iterations,            
            n_random_starts=10,    
            noise=10.0,            
            random_state=42        
        )

        return res
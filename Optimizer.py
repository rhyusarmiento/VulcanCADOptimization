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
        self.sim = self.doc.get_simulation(0)
        self.FlightDataType = jpype.JPackage("net").sf.openrocket.simulation.FlightDataType
        self.rocket = self.doc.getRocket()
        # Search Space
        self.space = [
            Real(1.0, 2.5, name='tube_length'),    # Tube: 1.0m to 2.5m
            Real(0.05, 0.25, name='fin_span'),     # Span: 5cm to 25cm
            Real(0.10, 0.40, name='root_chord'),   # Chord: 10cm to 40cm
            Real(0.0, 1.0, name='nose_mass'),      # Ballast: 0kg to 1kg
            Real(0.2, 0.8, name='avbay_pos')       # Position: 0.2m to 0.8m
        ]
        self.components = []

    def setup_component(self, component):
        name = str(component.getName())
        self.components.append((name, component))
        
        for child in component.getChildren():
            self.components(child)

    def get_component(self, name):
        for comp_name, comp in self.components:
            if comp_name == name:
                return comp
        return None

    # --- RUN OPTIMIZATION ---
    def run_optimizer(self, TARGET_ALTITUDE, iterations=50):
        print(f"🚀 Starting Optimization Run ({iterations} Iterations)...")

        # Objective Function
        @use_named_args(self.space)
        def objective_function(tube_length, fin_span, root_chord, nose_mass, avbay_pos):
            # Mod design
            try:
                tube = self.get_component("Main Tube")
                if tube: tube.setLength(tube_length)
                fins = self.get_component("Fins")
                if fins:
                    fins.setSpan(fin_span)
                    fins.setRootChord(root_chord)
                    # Geometric Constraint: Tip is 40% of Root (Maintains shape)
                    fins.setTipChord(root_chord * 0.4) 
                    # Geometric Constraint: Sweep angle scales with chord
                    fins.setSweepLength(root_chord * 0.5)
                ballast = self.get_component("Nose Weight")
                if ballast: ballast.setMass(nose_mass)
                avbay = self.get_component("AvBay")
                if avbay: avbay.setPositionValue(avbay_pos)
            except Exception as e:
                print(f"❌ Design Error: {e}")
                return 99999.0 # Massive penalty for crashing

            # Run sim and extract data
            self.orh.run_simulation(self.sim)
            data = self.sim.getSimulatedData().getBranch(0)
            alt_arr = np.array(data.get(self.FlightDataType.TYPE_ALTITUDE))
            stab_arr = np.array(data.get(self.FlightDataType.TYPE_STABILITY))
            vel_arr = np.array(data.get(self.FlightDataType.TYPE_VELOCITY_TOTAL))
            apogee = max(alt_arr)

            # # Get Rail Exit Data (Critical for Safety)
            # rail_indices = np.where(alt_arr >= 2.44)[0] # Assumes 8ft rail
            # if len(rail_indices) > 0:
            #     launch_stab = stab_arr[rail_indices[0]]
            #     launch_vel = vel_arr[rail_indices[0]]
            # else:
            #     launch_stab = 0.0
            #     launch_vel = 0.0

            # Caclulate Loss
            # Base score: Distance from 5000ft target
            loss = abs(apogee - TARGET_ALTITUDE)

            # # Penalty 1: Instability (< 1.5 cal)
            # # We use an exponential penalty so it REALLY avoids unstable rockets
            # if launch_stab < 1.5:
            #     loss += 5000 * (1.5 - launch_stab) ** 2

            # # Penalty 2: Slow Rail Exit (< 15 m/s)
            # if launch_vel < 15.0:
            #     loss += 5000 * (15.0 - launch_vel) ** 2
            # Progress Update
            # print(f"   Testing: L={tube_length:.2f}m, S={fin_span:.2f}m -> Alt: {apogee*3.28:.0f}ft (Stab: {launch_stab:.2f})")
            return loss

        res = gp_minimize(
            objective_function,
            self.space,
            n_calls=iterations,            
            n_random_starts=10,    
            noise=10.0,            
            random_state=42        
        )

        return res
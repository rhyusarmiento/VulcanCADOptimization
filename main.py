import orhelper
from pathlib import Path
import sys
import jpype
from Optimizer import Optimizer
import UiTools
import traceback

# 1. Path to your verified JAR
JAR_PATH = Path(__file__).parent / 'OpenRocket-23.09.jar'
ROCKET_FILE = Path(__file__).parent / 'ALC Rocket Rough Draft.ork'
TARGET_ALTITUDE = 1524.0 # 5000 ft
print("Initializing OpenRocket...")


from skopt.space import Real
space = [
    Real(1.0, 2.5, name='tube_length'),    # Tube: 1.0m to 2.5m
    Real(0.05, 0.25, name='fin_span'),     # Span: 5cm to 25cm
    Real(0.10, 0.40, name='root_chord'),   # Chord: 10cm to 40cm
    Real(0.0, 1.0, name='nose_mass'),      # Ballast: 0kg to 1kg
    Real(0.2, 0.8, name='avbay_pos')       # Position: 0.2m to 0.8m
]

try:
    with orhelper.OpenRocketInstance(str(JAR_PATH)) as instance:
        orh = orhelper.Helper(instance)
        print("✅ SUCCESS: OpenRocket backend is connected and ready!")

        # Load the rocket
        if not ROCKET_FILE.exists():
            print(f"❌ Warning: Could not find {ROCKET_FILE}")
            print("Please save a rocket design in this folder to test.")
        else:
            doc = orh.load_doc(str(ROCKET_FILE))
            print(f"Loaded rocket: {doc.getRocket().getName()}")
            sim = doc.getSimulation(0)
            FlightDataType = jpype.JPackage("net").sf.openrocket.simulation.FlightDataType

            # Run the Optimizer
            Opt = Optimizer(instance, str(ROCKET_FILE))
            results = Opt.run_optimizer(TARGET_ALTITUDE, iterations=50)
            print(f"✅ Optimization Complete! Best Result: {results.fun:.2f} ft error")
            # Report Results
            UiTools.report_results(results)

except Exception as e:
    print(f"❌ Error: {e}")
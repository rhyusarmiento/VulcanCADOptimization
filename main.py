import orhelper
from pathlib import Path
import sys
import jpype
from sklearn.discriminant_analysis import Real
from Optimizer import Optimizer
import UiTools
import traceback

# 1. Path to your verified JAR
JAR_PATH = Path(__file__).parent / 'OpenRocket-23.09.jar'
ROCKET_FILE = Path(__file__).parent / 'ALC Rocket Rough Draft.ork'
TARGET_ALTITUDE = 1524.0 # 5000 ft
print("Initializing OpenRocket...")

try:
    with orhelper.OpenRocketInstance(str(JAR_PATH)) as instance:
        orh = orhelper.Helper(instance)
        print("✅ SUCCESS: OpenRocket backend is connected and ready!")

        # Load the rocket
        if not ROCKET_FILE.exists():
            print(f"❌ Warning: Could not find {ROCKET_FILE}")
            print("Please save a rocket design in this folder to test.")
        else:
            print(f"Loaded rocket")
            # Run the Optimizer
            Opt = Optimizer(instance, str(ROCKET_FILE))
            results = Opt.run_optimizer(TARGET_ALTITUDE, iterations=500)
            print(f"✅ Optimization Complete! Best Apogee: {results[1]} m")
            # Report Results
            UiTools.report_results(results[0])

except Exception as e:
    print(f"❌ Error: {e}")
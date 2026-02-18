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
ROCKET_FILE = Path(__file__).parent / 'ALC Rocket PDR Checked.ork'
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
            # orh = orhelper.Helper(instance)
            # doc = orh.load_doc(str(ROCKET_FILE))
            # sim = doc.getSimulation(0)

            # Run the Optimizer
            Opt = Optimizer(instance, str(ROCKET_FILE))
            results = Opt.run_optimizer(TARGET_ALTITUDE, iterations=50)
    
            # Report Results
            UiTools.report_results(results[0])
            
            # RUN FINAL VERIFICATION & SAVE
            # results[0].x contains the list of best parameters found
            best_parameters = results[0].x
            
            # Call the new function we just wrote
            Opt.verify_and_save(best_parameters, "ALC_Optimized_Final.ork")

except Exception as e:
    print(f"❌ Error: {e}")
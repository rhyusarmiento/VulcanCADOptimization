import orhelper
from pathlib import Path
import sys
import jpype
from pyparsing import Opt
from sklearn.discriminant_analysis import Real
from Optimizer import Optimizer
import UiTools
import traceback

# 1. Path to your verified JAR
JAR_PATH = Path(__file__).parent / 'OpenRocket-23.09.jar'
ROCKET_FILE = Path(__file__).parent / 'ALC Rocket PDR Checked.ork'
TARGET_ALTITUDE = 1350.0 # 4250~ ft
print("Initializing OpenRocket...")

try:
    with orhelper.OpenRocketInstance(str(JAR_PATH)) as instance:
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
            Opt = Optimizer(instance, str(ROCKET_FILE))

            # 1. Parachute Drop (Find the safe zone)
            best_stage1_params, s1_apogee = Opt.run_stage1_global(TARGET_ALTITUDE, iterations=60)

            # 2. Mountain Hike (Get to the absolute peak)
            # We pass the exact parameters from Stage 1 into Stage 2
            final_optimized_params = Opt.run_stage2_local(best_stage1_params.x, TARGET_ALTITUDE, max_iter=40)

            # 3. Verify and Save
            UiTools.report_stats(best_stage1_params)
            Opt.verify_and_save(final_optimized_params, "ALC_Optimized_Final.ork")

except Exception as e:
    print(f"❌ Error: {e}")
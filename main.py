import orhelper
from pathlib import Path
import sys
import jpype
import Optimizer

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
            doc = orh.load_doc(str(ROCKET_FILE))
            print(f"Loaded rocket: {doc.getRocket().getName()}")

            # manage input request for diferent optimizers
            
            # Run the Optimizer
            results = Optimizer.run_optimizer(instance, str(ROCKET_FILE), TARGET_ALTITUDE)

            # run simulation and print results
            # optimise on stats

except Exception as e:
    print(f"❌ Error: {e}")
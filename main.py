import orhelper
from pathlib import Path
import sys
import jpype
import RocketTools as rt

# 1. Path to your verified JAR
jar_path = Path(__file__).parent / 'OpenRocket-23.09.jar'
rocket_file = Path(__file__).parent / 'ALC Rocket Rough Draft.ork'
print("Initializing OpenRocket...")

try:
    with orhelper.OpenRocketInstance(str(jar_path)) as instance:
        orh = orhelper.Helper(instance)
        print("✅ SUCCESS: OpenRocket backend is connected and ready!")

        
        # Load the rocket
        if not rocket_file.exists():
            print(f"❌ Warning: Could not find {rocket_file}")
            print("Please save a rocket design in this folder to test.")
        else:
            doc = orh.load_doc(str(rocket_file))
            print(f"Loaded rocket: {doc.getRocket().getName()}")

except Exception as e:
    print(f"❌ Error: {e}")
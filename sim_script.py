import orhelper
from pathlib import Path
import sys

# 1. Path to your verified JAR
jar_path = Path(__file__).parent / 'OpenRocket-23.09.jar'

print("Initializing OpenRocket...")

# 2. Start the instance and capture it as 'instance'
try:
    with orhelper.OpenRocketInstance(str(jar_path)) as instance:
        # 3. Pass the instance to the helper
        orh = orhelper.Helper(instance)
        
        print("✅ SUCCESS: OpenRocket backend is connected and ready!")
        
        # Example: Load a rocket (uncomment if you have a file)
        # doc = orh.load_doc('my_rocket.ork')
        # sim = doc.get_simulation(0)
        # orh.run_simulation(sim)
        # print("Simulation complete!")

except Exception as e:
    print(f"❌ Error: {e}")
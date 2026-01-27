import orhelper
from pathlib import Path

# 1. Point this to the exact filename you downloaded
jar_path = Path(__file__).parent / 'OpenRocket-23.09.jar' 

# 2. Initialize the bridge
with orhelper.OpenRocketInstance(jar_path):
    orh = orhelper.Helper()
    
    # 3. Load your rocket file (must be in the same folder)
    # doc = orh.load_doc('my_rocket.ork')
    
    # Run simulation logic here...
    print("OpenRocket backend is now connected to Python!")

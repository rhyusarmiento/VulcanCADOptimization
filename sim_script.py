import orhelper
from pathlib import Path
import sys

# 1. Path to your verified JAR
jar_path = Path(__file__).parent / 'OpenRocket-23.09.jar'
rocket_file = Path(__file__).parent / 'VulcanPy.ork'
print("Initializing OpenRocket...")

try:
    with orhelper.OpenRocketInstance(str(jar_path)) as instance:
        orh = orhelper.Helper(instance)
        
        print("✅ SUCCESS: OpenRocket backend is connected and ready!")
        
        # Load the rocket
        if not rocket_file.exists():
            print(f"❌ Warning: Could not find {rocket_file}")
            print("Please save a rocket design as 'VulcanPy.ork' in this folder to test.")
        else:
            doc = orh.load_doc(str(rocket_file))
            print(f"Loaded rocket: {doc.getName()}")

            # Get the simulation defined in that rocket
            sim = doc.get_simulation(0)
            print(f"Running simulation: {sim.getName()}...")
            orh.run_simulation(sim)
            
            # Extract Data
            data = orh.get_timeseries(sim, ["Time", "Altitude", "Vertical velocity"])
            events = orh.get_events(sim)
            
            # Calculate Apogee (Max Altitude)
            max_altitude = max(data["Altitude"])
            print(f"✅ Simulation Complete!")
            print(f"📈 Apogee: {max_altitude:.2f} m")
            print(f"⏱️ Flight Time: {data['Time'][-1]:.2f} s")

except Exception as e:
    print(f"❌ Error: {e}")
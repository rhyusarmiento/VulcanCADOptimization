# Access the Java Enum directly
def list_flight_data_types():        
    try:
        FlightDataType = jpype.JPackage("net").sf.openrocket.simulation.FlightDataType
            
        # Print all valid names
        for field in FlightDataType.values():
            print(f"'{field.name()}'")
    except Exception as e:
        print(f"Could not list types: {e}")
    

def run_simulation(orh, doc):        
    # Get the simulation defined in that rocket
    sim = doc.getSimulation(0)
    print(f"Running simulation: {sim.getName()}...")
    orh.run_simulation(sim)
    
    # Extract Data
    data = orh.get_timeseries(sim, ["TIME", "ALTITUDE", "VERTICAL_VELOCITY"])
    events = orh.get_events(sim)
    
    # Calculate Apogee (Max Altitude)
    max_altitude = max(data["Altitude"])
    print(f"✅ Simulation Complete!")
    print(f"📈 Apogee: {max_altitude:.2f} m")
    print(f"⏱️ Flight Time: {data['Time'][-1]:.2f} s")

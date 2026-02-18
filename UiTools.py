import math
import matplotlib
# CRITICAL: Switch backend to 'Agg' before importing pyplot
# This prevents "UserWarning: Matplotlib is currently using agg..." or crashes
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from skopt.plots import plot_convergence, plot_objective

def report_results(results):
    # # --- 1. PRINT TEXT REPORT ---
    # print("\n" + "="*50)
    # print("✅ OPTIMAL DESIGN FOUND")
    # print("="*50)
    
    # # Geometry (Tube & Fins)
    # print("🚀 GEOMETRY")
    # print(f"   Tube Length:      {results.x[0]*100:.2f} cm")
    # print(f"   Fin Height:         {results.x[1]*100:.2f} cm")
    # print(f"   Root Chord:       {results.x[2]*100:.2f} cm")
    # print(f"   Tip Chord:        {results.x[3]*100:.2f} cm")
    # print(f"   Fin Sweep:        {results.x[4]*100:.2f} cm")
    # # print(f"   Fin Cant Angle:   {math.degrees(results.x[5]):.2f}° ({results.x[5]:.3f} rad)")
    # print(f"   Fin Position:     {results.x[5]*100:.2f} cm (Relative)")

    # # Mass & Balance
    # print("\n⚖️ MASS & BALANCE")
    # # print(f"   Nose Ballast:     {results.x[7]*1000:.0f} g")
    # print(f"   Var Mass:     {results.x[6]*1000:.0f} g")
    # print(f"   Var Position: {results.x[7]*100:.2f} cm")
    
    # print("-" * 50)
    # print(f"🎯 Predicted Error:  {results.fun:.4f} (Objective Score)")

    # --- 2. SAVE PLOTS TO DISK ---
    print("\n📊 Saving Visualization Files...")
    
    # Plot 1: Convergence
    print("   -> Saving 'opt_convergence.png'...")
    plt.figure(figsize=(10, 6))
    plot_convergence(results)
    plt.title("Optimization Convergence")
    plt.savefig("opt_convergence.png", dpi=100) # Save file
    plt.close() # Close memory buffer

    # Plot 2: The Landscape
    print("   -> Saving 'opt_landscape.png' (This may take a moment)...")
    plt.figure(figsize=(20, 20)) # Massive size for 10x10 matrix
    
    # Plotting all 10 variables is very dense. 
    # Use 'dimensions' to pick specific names if you defined them in 'results.space'
    plot_objective(results, n_points=20) 
    
    plt.savefig("opt_landscape.png", dpi=100)
    plt.close()
    
    print("✅ Done! Check your project folder for the .png files.")


def print_rocket_tree(rocket):
    print("\n🌳 ROCKET COMPONENT TREE (Copy these names!):")
    for component in rocket.getChildren():
        print(f"   📂 {component.getName()}")
        for child in component.getChildren():
            print(f"      🔹 {child.getName()}")
            for subchild in child.getChildren():
                print(f"         🔸 {subchild.getName()}")
    print("-" * 40 + "\n")

            #     # --- FINS ---
            #     fins = Opt.get_component("Trapezoidal Fin Set")
            #     print(f"🔍 METHODS FOR: {fins.getName()}")

            #     # Get all attributes/methods
            #     all_attributes = dir(fins)

            #     # # 1. Filter for "Getters" (Reading values)
            #     # getters = [m for m in all_attributes if m.startswith('get')]
            #     # print(f"\n--- GETTERS ({len(getters)}) ---")
            #     # for g in sorted(getters):
            #     #     print(f"  . {g}()")

            #     # 2. Filter for "Setters" (Changing values - CRITICAL for optimization)
            #     # setters = [m for m in all_attributes if m.startswith('set')]
            #     # print(f"\n--- SETTERS ({len(setters)}) ---")
            #     # for s in sorted(setters):
            #     #     print(f"  . {s}(val)")

            #     # 3. specific keywords you might be missing (like 'is', 'update', 'calc')
            #     others = [m for m in all_attributes if not m.startswith('get') and not m.startswith('set') and not m.startswith('_')]
            #     print(f"\n--- OTHER METHODS ---")
            #     print(others)
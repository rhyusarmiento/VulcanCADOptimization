import math
import matplotlib
# CRITICAL: Switch backend to 'Agg' before importing pyplot
# This prevents "UserWarning: Matplotlib is currently using agg..." or crashes
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from skopt.plots import plot_convergence, plot_objective

def report_stats(stage1_res):
    # --- 1. PRINT TEXT REPORT ---
    print("\n" + "="*50)
    print("✅ OPTIMAL DESIGN FOUND (Stage 1 Final)")
    print("="*50)
    
    final_params = stage1_res.x

    # Geometry (Tube & Fins)
    print("🚀 GEOMETRY")
    print(f"   Top Tube Length:    {final_params[0]*100:.2f} cm")
    print(f"   Bottom Tube Length: {final_params[1]*100:.2f} cm")
    print(f"   Fin Height:         {final_params[2]*100:.2f} cm")
    print(f"   Root Chord:         {final_params[3]*100:.2f} cm")
    print(f"   Tip Chord:          {final_params[4]*100:.2f} cm")
    print(f"   Fin Sweep:          {final_params[5]*100:.2f} cm")
    print(f"   Fin Bottom Offset:  {final_params[6]*100:.2f} cm")

    # Mass & Balance
    print("\n⚖️ MASS & BALANCE")
    print(f"   Var Mass:           {final_params[7]*1000:.0f} g")
    print(f"   Var Position:       {final_params[8]*100:.2f} cm")
    
    print("-" * 50)
    print(f"🎯 Final Predicted Loss: {stage1_res.fun:.4f}")

    # --- 2. SAVE PLOTS TO DISK ---
    # We use the Stage 1 result for plotting because it contains the 
    # Gaussian surrogate map of the entire search space.
    
    print("\n📊 Saving Visualization Files (From Stage 1 Global Search)...")
    
    # Plot 1: Convergence
    print("   -> Saving 'opt_convergence.png'...")
    plt.figure(figsize=(10, 6))
    plot_convergence(stage1_res)
    plt.title("Stage 1: Bayesian Optimization Convergence")
    plt.savefig("opt_convergence.png", dpi=100, bbox_inches='tight') 
    plt.close() 
    # Plot 2: The Landscape
    print("   -> Saving 'opt_landscape.png' (This may take a moment)...")
    plt.figure(figsize=(20, 20)) 
    
    # skopt plots the landscape based on the random exploration and gaussian process
    plot_objective(stage1_res, n_points=20) 
    
    plt.savefig("opt_landscape.png", dpi=100, bbox_inches='tight')
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
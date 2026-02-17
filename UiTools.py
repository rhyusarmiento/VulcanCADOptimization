from skopt.plots import plot_objective, plot_convergence
import matplotlib.pyplot as plt
import math

def report_results(results):
    print("\n" + "="*50)
    print("✅ OPTIMAL DESIGN FOUND")
    print("="*50)
    
    # 1. Geometry (Tube & Fins)
    print("🚀 GEOMETRY")
    print(f"   Tube Length:      {results.x[0]*100:.2f} cm")
    print(f"   Fin Span:         {results.x[1]*100:.2f} cm")
    print(f"   Root Chord:       {results.x[2]*100:.2f} cm")
    print(f"   Tip Chord:        {results.x[3]*100:.2f} cm")
    print(f"   Fin Sweep:        {results.x[4]*100:.2f} cm")
    print(f"   Fin Cant Angle:   {math.degrees(results.x[5]):.2f}° ({results.x[5]:.3f} rad)")
    print(f"   Fin Position:     {results.x[6]*100:.2f} cm (Relative)")

    # 2. Mass & Balance
    print("\n⚖️ MASS & BALANCE")
    print(f"   Nose Ballast:     {results.x[7]*1000:.0f} g")
    print(f"   Payload Mass:     {results.x[8]*1000:.0f} g")
    print(f"   Payload Position: {results.x[9]*100:.2f} cm")
    
    print("-" * 50)
    print(f"🎯 Predicted Error:  {results.fun:.4f} (Objective Score)")

    # --- VISUALIZATION ---
    print("\n📊 Generating Partial Dependence Plots...")
    
    # Plot 1: Convergence
    plt.figure(figsize=(10, 6))
    plot_convergence(results)
    plt.title("Optimization Convergence (Did we find a minimum?)")
    plt.show()

    # Plot 2: The Landscape
    # Note: 10 variables creates a massive 10x10 plot matrix. 
    # We increase figsize to handle the density.
    plt.figure(figsize=(16, 16)) 
    
    # Optional: Plot only the most impactful variables if it's too crowded
    # plot_objective(results, dimensions=["top_tube_length", "fin_height", "root_chord", "nose_mass"], n_points=40)
    
    plot_objective(results, n_points=30) 
    plt.show()
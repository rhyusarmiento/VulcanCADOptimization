from skopt.plots import plot_objective, plot_convergence
import matplotlib.pyplot as plt

def report_results(results):
    print("\n" + "="*40)
    print("✅ OPTIMAL DESIGN FOUND")
    print("="*40)
    print(f"   Tube Length:    {results.x[0]*100:.1f} cm")
    print(f"   Fin Span:       {results.x[1]*100:.1f} cm")
    print(f"   Root Chord:     {results.x[2]*100:.1f} cm")
    print(f"   Nose Ballast:   {results.x[3]*1000:.0f} g")
    print(f"   AvBay Position: {results.x[4]*100:.1f} cm")
    print("-" * 40)
    print(f"   Predicted Error: {results.fun:.2f} meters")

    # --- 6. VISUALIZE (The Interview Money Shot) ---
    print("\n📊 Generating Partial Dependence Plots...")
    
    # Plot 1: Convergence (Did we get better over time?)
    plt.figure(figsize=(10, 6))
    plot_convergence(results)
    plt.title("Bayesian Optimization Convergence")
    plt.show()

    # Plot 2: The "Landscape" (How each variable affects the result)
    # This shows the "Partial Dependence" of the objective function
    plt.figure(figsize=(12, 12))
    plot_objective(results, n_points=40)
    plt.show()
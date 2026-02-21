# OpenRocket Automated Optimization Pipeline

An advanced, two-stage mathematical optimization framework for OpenRocket (`.ork`) designs. This tool uses Python, Java (via `JPype` and `orhelper`), and machine learning libraries to automatically design rockets that reach a target altitude while strictly adhering to aerodynamic, kinematic, and geometric safety rules.

## 🚀 Overview

Designing a high-power rocket is a multi-variable optimization problem. Maximizing apogee directly conflicts with aerodynamic stability (larger fins = more drag = lower apogee, but smaller fins = unstable flight). 

This pipeline solves that by treating the OpenRocket simulation as a "Black Box" physics engine and wrapping it in a custom objective function. It explores the design space using a **Two-Stage Strategy**:
1. **Global Search (Bayesian Optimization):** Scans the entire design space to find the "Safe Zone" of stable flight.
2. **Local Refinement (Nelder-Mead Simplex):** Walks down the local gradient to find the absolute peak performance within that safe zone.

---

## 🧠 Optimization Architecture

## 🧮 Deep Dive: The Optimization Mathematics

Our pipeline solves a **non-convex, black-box optimization problem**. 
* **Black-Box:** We do not have a mathematical formula for the OpenRocket simulator. We can only give it an input $x$ (design parameters) and observe the output $f(x)$ (flight data).
* **Non-Convex:** The "landscape" of rocket performance is full of local minima (e.g., a rocket that is perfectly stable but only goes 500 meters) and discontinuous cliffs (e.g., a rocket that suddenly becomes unstable and crashes).

To solve this efficiently, we split the math into two distinct paradigms: Probabilistic (Bayesian) and Geometric (Nelder-Mead).

---

### Stage 1: Bayesian Optimization (Gaussian Processes)

In Stage 1, we don't just blindly guess. We build a mathematical "ghost" of the OpenRocket simulator called a **Surrogate Model**.

#### 1. The Gaussian Process (GP)
Instead of predicting a single altitude for a set of fin dimensions, a Gaussian Process predicts a *probability distribution* of possible altitudes. The GP is defined by a mean function $\mu(x)$ and a covariance function, or kernel, $k(x, x')$:

$$f(x) \sim \mathcal{GP}(\mu(x), k(x, x'))$$

The kernel $k(x, x')$ dictates that if two rocket designs $x$ and $x'$ are physically similar (e.g., the fins are only 1mm different), their resulting flight performances $f(x)$ and $f(x')$ should also be similar.



#### 2. The Acquisition Function
Once the GP builds a map of the search space, it must decide which rocket to simulate next. It does this by maximizing an **Acquisition Function**. We typically use **Expected Improvement (EI)**:

$$EI(x) = \mathbb{E}[\max(0, f(x^*) - f(x))]$$

Where:
* $f(x^*)$ is the loss score of the best rocket design found so far.
* $f(x)$ is the predicted distribution of the *next* design.

**The Math at Work:** The Expected Improvement equation mathematically balances two competing desires:
* **Exploitation:** Testing areas where the mean $\mu(x)$ predicts a great score (the "safe zone").
* **Exploration:** Testing areas where the uncertainty (variance) is very high (the "unknown").

*Why it stops here:* Bayesian optimization is incredible at finding the global "valley," but as the uncertainty drops, the Expected Improvement calculation becomes dominated by statistical noise. It struggles to find the exact millimeter-perfect bottom of the valley.

---

### Stage 2: The Nelder-Mead Simplex (Geometric Descent)

Once Stage 1 drops us into the correct "valley" (a stable, high-performing design), we switch to a heuristic, derivative-free search method called **Nelder-Mead**.

#### 1. The Simplex
In an $N$-dimensional search space (where $N$ is your number of variables, e.g., 9), a simplex is a geometric shape with $N+1$ vertices (e.g., a triangle in 2D, a tetrahedron in 3D). Stage 2 creates a 10-vertex simplex clustered tightly around your Stage 1 winner.



#### 2. The Geometric Walk
At every step, Nelder-Mead calculates the loss function $f(x)$ for all $N+1$ points. It sorts them from best to worst: $f(x_1) \le f(x_2) \dots \le f(x_{n+1})$.

It then calculates the **centroid** (center of mass) $x_o$ of all points *except* the worst point.

The algorithm then literally "walks" down the mathematical hill using a set of geometric transformations to replace the worst point $x_{n+1}$:

1. **Reflection:** It flips the worst point over the centroid to see if the grass is greener on the other side.
   $$x_r = x_o + \alpha(x_o - x_{n+1})$$
2. **Expansion:** If the reflected point is the new best point, it keeps going in that direction.
   $$x_e = x_o + \gamma(x_r - x_o)$$
3. **Contraction:** If the reflection was worse, it pulls back and tries a point closer to the centroid.
   $$x_c = x_o + \rho(x_{n+1} - x_o)$$
4. **Shrink:** If all else fails, it shrinks the entire simplex toward the best known point $x_1$.

**The Math at Work:** Because Nelder-Mead only compares relative values (better vs. worse) rather than calculating complex gradients, it is immune to the small "numerical noise" generated by OpenRocket's physics engine. It greedily and rapidly slides down the slope until the simplex becomes so small that the difference between points is less than our `tolerance` threshold ($1\text{e-}3$).

---

## 📐 The Underlying Mathematics

The core of the optimizer is the **Objective Function** (the Loss). The algorithm attempts to drive this loss to $0$.

### 1. The Apogee Bowl (Primary Objective)
The primary goal is to hit the `TARGET_ALTITUDE`. We use a normalized quadratic curve to create a smooth "bowl" for the optimizer to roll into.

$$L_{apogee} = \left( \frac{|A_{sim} - A_{target}|}{20.0} \right)^2 \times 100,000$$

*Why divide by 20?* This normalizes the error so the gradients don't explode when the rocket is 5,000 meters off target, but remain strong enough to guide the solver when it is only 5 meters off target.

### 2. The Stability Penalty ("The Electric Fence")
Stability is defined in calibers:

$$S = \frac{X_{cp} - X_{cg}}{D_{ref}}$$

Where $X_{cp}$ is the Center of Pressure, $X_{cg}$ is the Center of Gravity, and $D_{ref}$ is the maximum tube diameter. 

If the minimum stability during the boost phase drops below $1.5$ cal, we trigger a massive exterior penalty. We use a heavily weighted quadratic function combined with an offset to create a "wall":

$$P_{danger} = \left( (1.5 - S_{min}) + 10,000,000 \right)^2$$

This ensures that an unstable rocket receives an infinitely bad score, forcing the optimizer to retreat immediately.

### 3. Over-Stability (Weathercocking)
If a rocket is *too* stable ($S > 2.1$), it will weathercock into the wind, increasing drag and losing altitude. We apply a gentler quadratic penalty to nudge the optimizer back toward lower-drag designs:

$$P_{drag} = \left( S_{avg} - 2.1 \right)^2 \times 10,000$$

### 4. Geometric Constraints (Fin Flutter & Structural Integrity)
To prevent the optimizer from exploiting the physics engine by creating infinitely thin "needle" fins or bizarre shapes, we penalize structural weaknesses:
* **Max Sweep:** Sweep cannot exceed $2 \times RootChord$.
* **Taper Ratio:** Tip Chord cannot exceed $2 \times RootChord$.

$$P_{sweep} = (Sweep - RootChord)^2 \times 100$$

### 5. Kinematic Constraints (Rail Exit Velocity)
A rocket must be moving fast enough when it leaves the launch rod to allow the fins to generate correcting lift. If $V_{rail} < 13.0 \text{ m/s}$, a hard penalty is applied:

$$P_{kinematic} = \left( (13.0 - V_{rail}) + 1,000,000 \right)^2$$

### Total Loss Function
The final value returned to the optimizer is the sum of all objectives and active constraints:

$$L_{total} = L_{apogee} + \sum P$$

---

## 🛠️ Coordinate System Translation

OpenRocket natively utilizes a **Top-Down** absolute coordinate system (where $0.0$ is the tip of the nose cone). This creates a problem during optimization: if the optimizer lengthens the body tube, the fins (which are defined by distance from the top) will slide up the rocket and detach from the bottom.

To solve this, the optimizer operates in a **Bottom-Up** relative system using a calculated offset:

$$X_{Absolute} = L_{Parent} - C_{Root} - O_{Bottom}$$

Where:
* $X_{Absolute}$ = The value sent to OpenRocket's `.setAxialOffset()`.
* $L_{Parent}$ = The dynamically changing length of the body tube.
* $C_{Root}$ = The root chord of the fin.
* $O_{Bottom}$ = The optimizer's chosen distance from the very bottom of the tube ($0.0$ = flush with the bottom).

This guarantees that every combination of variables results in a physically valid geometry.

---

## ⚙️ Setup and Installation

### Prerequisites
* Python 3.8+
* Java Development Kit (JDK) 8 or higher (Required for JPype)
* OpenRocket `.jar` core files

### Dependencies
```bash
pip install numpy scipy scikit-optimize jpype1 matplotlib
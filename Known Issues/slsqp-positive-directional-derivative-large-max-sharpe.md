# SLSQP positive directional derivative on large Max Sharpe runs

> **Status: RESOLVED** — fixed by the modular optimizer layer (`allolabs_optimizer.py`).
> Auto solver selection no longer routes large Max Sharpe runs to SLSQP; see
> "Resolution" at the end of this note. The analysis below is kept as the
> diagnostic record of the original failure.

When a Max Sharpe optimization grows from about 250 assets to 947 assets, SciPy's Sequential Least Squares Programming (SLSQP) solver can fail with `RuntimeError: Positive directional derivative for linesearch`. The hardware is not the main cause. The problem is the shape and scale of the math the solver has to navigate.

Max Sharpe is a fractional objective: maximize return divided by volatility. In solver form, that usually becomes a minimization of negative Sharpe. This surface is non-convex, which means the solver does not see one clean bowl-shaped path downhill. At 250 weights, SLSQP can often find a workable descent direction anyway. At 947 weights, there are far more directions where tiny changes in weights barely improve return, inflate risk, or violate constraints, so the internal line search can decide that every step it tries makes the local approximation worse.

Numerical scaling makes that worse. Expected returns, covariance terms, penalties, bounds, and equality constraints can live on different magnitudes. With 947 variables, covariance noise and near-collinearity between assets create a flatter and more ill-conditioned risk surface. SLSQP builds local quadratic and linear approximations from gradients. If those gradients are poorly scaled or nearly cancel each other, its proposed step can point in a direction that should help on paper but increases the true objective when evaluated.

L2 smoothing can also conflict with the Max Sharpe objective. The Sharpe objective wants concentrated positions when a few assets have attractive return-to-risk trade-offs. L2 regularization wants weights to stay smaller, smoother, or closer to a reference shape. Position caps, full-investment constraints, sector caps, long-only bounds, and L2 pressure can pull the solution in incompatible directions. At high dimension, SLSQP may find a direction that satisfies one part of the approximation while pushing against another part of the real constrained problem.

The specific error means: SLSQP tried to move along its chosen search direction, but the directional derivative was positive, so the move was not a descent step for the minimized objective. After repeated attempts, it could not find a step length that improved the objective while respecting the constraints.

Diagnostic takeaway: the 947-asset failure is likely a large, noisy, non-convex optimization problem overwhelming SLSQP's local line-search assumptions. Reduce the active universe, improve scaling, simplify or rescale the L2 penalty, use a convex reformulation when possible, or switch to an optimizer designed for large constrained nonlinear programs.

## Resolution

The optimizer was rebuilt as a modular layer (`allolabs_optimizer.py`) that computes exactly the targets a run requests (Max Sharpe, Min Volatility, Max Return, Risk Parity, Max Diversification) and routes each target to a solver suited to its structure and size. The Console exposes this through an "Optimization target" dropdown and a "Solver mode" dropdown (`auto` by default).

How the fix addresses this failure specifically:

- **Convex reformulation.** An unregularized Max Sharpe (or Max Diversification) problem is solved through the standard fractional-programming substitution, which turns the non-convex ratio objective into a convex quadratic program. Every hard constraint (full investment, long-only bounds, position caps, sector caps) is positively homogeneous, so the reformulation is exact. CVXPY with OSQP solves the 947-asset case in seconds — there is no line search to fail.
- **trust-constr for large nonlinear targets.** When the target must stay nonlinear (L2/smooth-L1 regularization breaks the reformulation's homogeneity, and Risk Parity is inherently nonlinear), universes above 250 assets use SciPy's `trust-constr` interior-point method instead of SLSQP. It accepts a feasible near-optimal iterate at the iteration cap rather than aborting mid-line-search.
- **SLSQP retained where it works.** Small portfolios (≤250 assets) keep SLSQP with the original multi-start restarts and identical objective math, and `scipy-slsqp` can always be requested explicitly.
- **Honest fallbacks only.** Solver fallbacks (e.g. requested ECOS is not bundled with modern CVXPY, or CVXPY itself is not installed) always solve the *same formulation or the same target's nonlinear form* — a run never silently switches to a different objective. Impossible combinations (e.g. `cvxpy-osqp` for Risk Parity) fail with a clear configuration error.

Remaining limitation: the PDF memorandum's narrative is written for the classic Max Sharpe vs Min Volatility comparison, so it is generated only when a run computes that pair (the default). Other target selections still produce the console report, out-of-sample analysis, performance chart, allocation CSV, run archive, and dashboard results; the console prints a note that the PDF was skipped.

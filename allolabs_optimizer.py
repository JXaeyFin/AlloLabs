"""Modular portfolio optimizer layer for AlloLabs.

Computes exactly the optimization targets requested by the run configuration
and routes each target to the most appropriate solver backend:

Targets
    max_sharpe            maximize return per unit of total risk
    min_volatility        minimize total portfolio risk
    max_return            maximize expected return subject to constraints
    risk_parity           equalize asset risk contributions
    max_diversification   maximize weighted asset volatility / portfolio vol

Solver backends
    cvxpy-osqp            fast free QP solver for convex quadratic targets
    cvxpy-ecos            conic solver for SOCP formulations (falls back to
                          SCS when ECOS is not bundled with CVXPY)
    cvxpy-scs             approximate conic solver for very large problems
    scipy-slsqp           small nonlinear problems (under ~250 assets)
    scipy-trust-constr    large constrained nonlinear problems

Auto-selection avoids SLSQP for large Max Sharpe runs, which fail with
"Positive directional derivative for linesearch" (see Known Issues).  When a
target is convex-expressible and unregularized, Max Sharpe and Max
Diversification are solved through the standard fractional-programming
reformulation (a convex QP), which is far more stable than the raw
non-convex ratio objective.  A fallback is only ever taken when it preserves
the mathematical meaning of the requested target; otherwise the run fails
with a clear error.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import LinearConstraint, linprog, minimize

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Target and Solver Catalogs
# Canonical identifiers, display labels, and thresholds shared by the
# pipeline, the dashboard, and the AI context builders.
# ═══════════════════════════════════════════════════════════════════════════════

OPTIMIZATION_TARGETS: Tuple[str, ...] = (
    "max_sharpe",
    "min_volatility",
    "max_return",
    "risk_parity",
    "max_diversification",
)

SOLVER_MODES: Tuple[str, ...] = (
    "auto",
    "cvxpy-osqp",
    "cvxpy-ecos",
    "cvxpy-scs",
    "scipy-slsqp",
    "scipy-trust-constr",
)

DEFAULT_TARGETS: Tuple[str, ...] = ("max_sharpe", "min_volatility")

# Short labels used in AI prompts and dashboard summaries.
TARGET_LABELS: Dict[str, str] = {
    "max_sharpe": "Max Sharpe Ratio",
    "min_volatility": "Min Volatility",
    "max_return": "Max Return",
    "risk_parity": "Risk Parity",
    "max_diversification": "Max Diversification",
}

# Formal labels used in the PDF memorandum and archives.
TARGET_FORMAL_LABELS: Dict[str, str] = {
    "max_sharpe": "Maximum Sharpe",
    "min_volatility": "Minimum Volatility",
    "max_return": "Maximum Return",
    "risk_parity": "Risk Parity",
    "max_diversification": "Maximum Diversification",
}

# Column keys used for out-of-sample return frames and chart series.
TARGET_COLUMN_KEYS: Dict[str, str] = {
    "max_sharpe": "Max_Sharpe",
    "min_volatility": "Min_Vol",
    "max_return": "Max_Return",
    "risk_parity": "Risk_Parity",
    "max_diversification": "Max_Div",
}

# Risk posture wording injected into analyst/auditor context.
TARGET_RISK_POSTURES: Dict[str, str] = {
    "max_sharpe": "return-per-unit-risk",
    "min_volatility": "minimum variance",
    "max_return": "maximum return",
    "risk_parity": "risk parity (equalized asset risk contributions)",
    "max_diversification": "diversification (maximum diversification ratio)",
}

# SLSQP remains acceptable below this asset count for nonlinear objectives.
SLSQP_ASSET_LIMIT = 250

# Above this asset count, prefer the approximate conic solver for QP forms.
SCS_ASSET_THRESHOLD = 3000


class OptimizerError(RuntimeError):
    """A portfolio optimization could not be completed as requested."""


def parse_targets(raw: Optional[str]) -> List[str]:
    """Parse a comma-separated target list, preserving order and uniqueness."""
    if raw is None or not raw.strip():
        return list(DEFAULT_TARGETS)
    targets: List[str] = []
    for token in raw.split(","):
        target = token.strip().lower()
        if not target:
            continue
        if target not in OPTIMIZATION_TARGETS:
            raise ValueError(
                f"Unsupported optimization target {target!r}; expected one of: "
                + ", ".join(OPTIMIZATION_TARGETS)
            )
        if target not in targets:
            targets.append(target)
    if not targets:
        raise ValueError("At least one optimization target is required.")
    return targets


def ai_context_lines(targets: Sequence[str], solver_mode: str) -> List[str]:
    """Human-readable context lines describing the run's construction objective.

    Injected into analyst, auditor, and Guide LLM context so the models know
    what portfolio construction problem their inputs feed.
    """
    labels = [TARGET_LABELS.get(target, target) for target in targets]
    postures = [TARGET_RISK_POSTURES.get(target, target) for target in targets]
    return [
        f"Optimization target: {', '.join(labels)}",
        f"Solver mode: {solver_mode}",
        f"Risk posture implied by target: {'; '.join(postures)}",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Problem Specification and Outcome Containers
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ProblemSpec:
    """Full description of one portfolio optimization problem."""

    target: str
    mu: np.ndarray
    Sigma: np.ndarray
    risk_free_rate: float = 0.0
    long_only: bool = True
    max_position_weight: float = 1.0
    max_sector_weight: float = 1.0
    sector_indices: Dict[str, np.ndarray] = field(default_factory=dict)
    regularization_method: str = "none"
    regularization_strength: float = 0.0
    solver_mode: str = "auto"
    initial_guess: Optional[np.ndarray] = None
    starting_points: Tuple[np.ndarray, ...] = ()

    def __post_init__(self) -> None:
        if self.target not in OPTIMIZATION_TARGETS:
            raise ValueError(
                f"Unsupported optimization target {self.target!r}; expected one "
                f"of: {', '.join(OPTIMIZATION_TARGETS)}"
            )
        if self.solver_mode not in SOLVER_MODES:
            raise ValueError(
                f"Unsupported solver mode {self.solver_mode!r}; expected one "
                f"of: {', '.join(SOLVER_MODES)}"
            )
        self.mu = np.asarray(self.mu, dtype=float)
        self.Sigma = np.asarray(self.Sigma, dtype=float)
        if self.target == "risk_parity" and not self.long_only:
            raise ValueError(
                "Risk parity requires a long-only portfolio; short positions "
                "make risk contributions ill-defined."
            )

    @property
    def num_assets(self) -> int:
        return int(len(self.mu))

    @property
    def regularization_active(self) -> bool:
        return (
            self.regularization_method != "none"
            and self.regularization_strength > 0
        )

    @property
    def equal_weight(self) -> np.ndarray:
        return np.ones(self.num_assets) / self.num_assets

    @property
    def lower_bound(self) -> float:
        return 0.0 if self.long_only else -self.max_position_weight

    def scipy_bounds(self) -> Tuple[Tuple[float, float], ...]:
        return tuple(
            (self.lower_bound, self.max_position_weight)
            for _ in range(self.num_assets)
        )


@dataclass
class OptimizationOutcome:
    """Validated result of one portfolio optimization."""

    target: str
    weights: np.ndarray
    solver: str
    formulation: str
    message: str = ""

    @property
    def label(self) -> str:
        return TARGET_LABELS[self.target]

    @property
    def formal_label(self) -> str:
        return TARGET_FORMAL_LABELS[self.target]

    @property
    def column_key(self) -> str:
        return TARGET_COLUMN_KEYS[self.target]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: CVXPY Availability
# CVXPY is an optional acceleration dependency; every import is guarded so the
# pipeline keeps working on installs that only ship SciPy.
# ═══════════════════════════════════════════════════════════════════════════════

_CVXPY_CACHE: Dict[str, object] = {}


def cvxpy_module():
    """Return the cvxpy module, or None when it is not installed."""
    if "module" not in _CVXPY_CACHE:
        try:
            import cvxpy  # noqa: PLC0415 - optional dependency probe

            _CVXPY_CACHE["module"] = cvxpy
        except Exception:  # noqa: BLE001 - any import failure means unavailable
            _CVXPY_CACHE["module"] = None
    return _CVXPY_CACHE["module"]


def cvxpy_available() -> bool:
    return cvxpy_module() is not None


def cvxpy_solver_installed(name: str) -> bool:
    """Whether a specific CVXPY solver backend (e.g. ``ECOS``) is installed."""
    cp = cvxpy_module()
    if cp is None:
        return False
    try:
        return name.upper() in set(cp.installed_solvers())
    except Exception:  # noqa: BLE001 - treat probe failure as unavailable
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Formulation Classification and Solver Resolution
# ═══════════════════════════════════════════════════════════════════════════════


def convex_formulation(spec: ProblemSpec) -> Optional[str]:
    """Classify the convex problem class for a spec.

    Returns ``"qp"`` for quadratic programs, ``"conic"`` for second-order-cone
    programs, ``"fractional_qp"`` for the Max Sharpe / Max Diversification
    reformulation, or ``None`` when the target can only be solved as a general
    nonlinear program without changing its meaning.
    """
    if spec.target == "max_return":
        if spec.regularization_active and spec.regularization_method == "smooth_l1":
            return "conic"
        return "qp"
    if spec.target == "min_volatility":
        # Without a penalty, minimizing variance and minimizing volatility
        # share the same argmin, so the plain QP is exact.  With a penalty the
        # objective must stay vol + penalty, which is an SOCP.
        return "qp" if not spec.regularization_active else "conic"
    if spec.target in ("max_sharpe", "max_diversification"):
        if spec.regularization_active:
            # The regularization penalty is not positively homogeneous, so the
            # fractional reformulation would change the target meaning.
            return None
        if spec.target == "max_sharpe":
            excess = spec.mu - spec.risk_free_rate
            positive_excess = excess > 0 if spec.long_only else excess != 0
            if not bool(np.any(positive_excess)):
                # No feasible portfolio has positive excess return, so the
                # reformulation's normalization constraint is infeasible.
                return None
        return "fractional_qp"
    return None  # risk_parity


@dataclass
class SolverChoice:
    solver: str
    formulation: str  # "qp" | "conic" | "fractional_qp" | "nonlinear"
    reason: str


def _scipy_choice(spec: ProblemSpec, reason: str) -> SolverChoice:
    if spec.num_assets <= SLSQP_ASSET_LIMIT:
        return SolverChoice("scipy-slsqp", "nonlinear", reason)
    return SolverChoice(
        "scipy-trust-constr",
        "nonlinear",
        reason + f" ({spec.num_assets} assets exceeds the "
        f"{SLSQP_ASSET_LIMIT}-asset SLSQP limit)",
    )


def resolve_solver(spec: ProblemSpec) -> SolverChoice:
    """Select the solver backend and formulation for a problem spec.

    Explicit solver modes are honored when they can express the target and
    rejected with a clear error otherwise; ``auto`` prefers CVXPY for
    convex-expressible targets and sizes the SciPy method to the problem.
    """
    formulation = convex_formulation(spec)

    if spec.solver_mode == "scipy-slsqp":
        return SolverChoice("scipy-slsqp", "nonlinear", "explicitly requested")
    if spec.solver_mode == "scipy-trust-constr":
        return SolverChoice(
            "scipy-trust-constr", "nonlinear", "explicitly requested"
        )
    if spec.solver_mode.startswith("cvxpy-"):
        if formulation is None:
            raise OptimizerError(
                f"Solver mode {spec.solver_mode!r} cannot express the "
                f"{TARGET_LABELS[spec.target]} target"
                + (
                    " with regularization enabled"
                    if spec.regularization_active
                    else ""
                )
                + " without changing its meaning. Use solver mode 'auto', "
                "'scipy-slsqp', or 'scipy-trust-constr'."
            )
        if not cvxpy_available():
            raise OptimizerError(
                f"Solver mode {spec.solver_mode!r} requires the optional "
                "cvxpy package, which is not installed. Install cvxpy or use "
                "solver mode 'auto'."
            )
        if spec.solver_mode == "cvxpy-osqp" and formulation == "conic":
            raise OptimizerError(
                "OSQP cannot solve the second-order-cone formulation required "
                f"by this configuration of {TARGET_LABELS[spec.target]}. Use "
                "'cvxpy-ecos', 'cvxpy-scs', or 'auto'."
            )
        return SolverChoice(spec.solver_mode, formulation, "explicitly requested")

    # Auto-selection.
    if formulation is not None and cvxpy_available():
        if formulation == "conic":
            solver = "cvxpy-ecos" if cvxpy_solver_installed("ECOS") else "cvxpy-scs"
            return SolverChoice(solver, formulation, "convex conic target")
        if spec.num_assets > SCS_ASSET_THRESHOLD:
            return SolverChoice(
                "cvxpy-scs", formulation, "very large convex target"
            )
        return SolverChoice("cvxpy-osqp", formulation, "convex quadratic target")

    if formulation is not None:
        return _scipy_choice(
            spec, "convex target solved with SciPy (cvxpy not installed)"
        )
    return _scipy_choice(spec, "nonlinear target")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Shared Objective Mathematics (weights space)
# Mirrors the historical allolabs.py objective definitions so SciPy results
# stay bit-compatible with previous releases.
# ═══════════════════════════════════════════════════════════════════════════════


def _penalty(spec: ProblemSpec, weights: np.ndarray) -> float:
    if not spec.regularization_active:
        return 0.0
    delta = weights - spec.equal_weight
    if spec.regularization_method == "l2":
        return float(spec.regularization_strength * np.dot(delta, delta))
    if spec.regularization_method == "smooth_l1":
        smoothing = 1e-4
        smooth_absolute = np.sqrt(delta * delta + smoothing * smoothing) - smoothing
        return float(spec.regularization_strength * smooth_absolute.sum())
    raise ValueError(
        f"Unsupported regularization method: {spec.regularization_method}"
    )


def _penalty_gradient(spec: ProblemSpec, weights: np.ndarray) -> np.ndarray:
    if not spec.regularization_active:
        return np.zeros_like(weights, dtype=float)
    delta = weights - spec.equal_weight
    if spec.regularization_method == "l2":
        return 2.0 * spec.regularization_strength * delta
    if spec.regularization_method == "smooth_l1":
        smoothing = 1e-4
        return spec.regularization_strength * delta / np.sqrt(
            delta * delta + smoothing * smoothing
        )
    raise ValueError(
        f"Unsupported regularization method: {spec.regularization_method}"
    )


def _ratio_objective(
    spec: ProblemSpec, numerator: np.ndarray, shift: float
) -> Tuple[Callable, Callable]:
    """Objective/gradient pair for -(numerator·w - shift) / vol(w) + penalty."""

    Sigma = spec.Sigma

    def objective(weights: np.ndarray) -> float:
        variance = max(float(weights.dot(Sigma.dot(weights))), 1e-16)
        risk = float(np.sqrt(variance))
        ratio = (float(weights.dot(numerator)) - shift) / risk
        return -ratio + _penalty(spec, weights)

    def gradient(weights: np.ndarray) -> np.ndarray:
        covariance_times_weights = Sigma.dot(weights)
        variance = max(float(weights.dot(covariance_times_weights)), 1e-16)
        risk = float(np.sqrt(variance))
        excess = float(weights.dot(numerator)) - shift
        ratio_gradient = (
            numerator / risk
            - excess * covariance_times_weights / (risk ** 3)
        )
        return -ratio_gradient + _penalty_gradient(spec, weights)

    return objective, gradient


def _nonlinear_objective(spec: ProblemSpec) -> Tuple[Callable, Callable]:
    """Return (objective, gradient) callables in weight space for a target."""
    Sigma = spec.Sigma

    if spec.target == "max_sharpe":
        return _ratio_objective(spec, spec.mu, spec.risk_free_rate)

    if spec.target == "max_diversification":
        asset_vols = np.sqrt(np.clip(np.diag(Sigma), 1e-16, None))
        return _ratio_objective(spec, asset_vols, 0.0)

    if spec.target == "min_volatility":

        def objective(weights: np.ndarray) -> float:
            variance = float(weights.dot(Sigma.dot(weights)))
            return float(np.sqrt(max(variance, 0.0))) + _penalty(spec, weights)

        def gradient(weights: np.ndarray) -> np.ndarray:
            covariance_times_weights = Sigma.dot(weights)
            variance = max(float(weights.dot(covariance_times_weights)), 1e-16)
            return covariance_times_weights / np.sqrt(variance) + _penalty_gradient(
                spec, weights
            )

        return objective, gradient

    if spec.target == "max_return":
        mu = spec.mu

        def objective(weights: np.ndarray) -> float:
            return -float(weights.dot(mu)) + _penalty(spec, weights)

        def gradient(weights: np.ndarray) -> np.ndarray:
            return -mu + _penalty_gradient(spec, weights)

        return objective, gradient

    if spec.target == "risk_parity":
        budget = 1.0 / spec.num_assets

        def objective(weights: np.ndarray) -> float:
            covariance_times_weights = Sigma.dot(weights)
            variance = max(float(weights.dot(covariance_times_weights)), 1e-16)
            contributions = weights * covariance_times_weights / variance
            residual = contributions - budget
            return float(residual.dot(residual)) + _penalty(spec, weights)

        def gradient(weights: np.ndarray) -> np.ndarray:
            covariance_times_weights = Sigma.dot(weights)
            variance = max(float(weights.dot(covariance_times_weights)), 1e-16)
            contributions = weights * covariance_times_weights / variance
            residual = contributions - budget
            weighted_residual = residual * weights
            return (2.0 / variance) * (
                residual * covariance_times_weights
                + Sigma.dot(weighted_residual)
                - 2.0
                * covariance_times_weights
                * float(residual.dot(weights * covariance_times_weights))
                / variance
            ) + _penalty_gradient(spec, weights)

        return objective, gradient

    raise ValueError(f"Unsupported optimization target: {spec.target}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Weight Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validated_weights(
    spec: ProblemSpec, raw_weights: np.ndarray, label: str, *, tolerance: float
) -> np.ndarray:
    """Validate, clean, and renormalize a candidate weight vector."""
    weights = np.asarray(raw_weights, dtype=float).copy()
    if not np.all(np.isfinite(weights)):
        raise OptimizerError(f"{label} optimization returned non-finite weights.")
    weights[np.abs(weights) < 1e-12] = 0.0
    if spec.long_only:
        if np.any(weights < -tolerance):
            raise OptimizerError(f"{label} optimization returned a negative weight.")
        weights = np.clip(weights, 0.0, None)
    total = float(weights.sum())
    if abs(total) <= 1e-12:
        raise OptimizerError(f"{label} optimization returned zero net weight.")
    if not np.isclose(total, 1.0, atol=max(tolerance, 1e-6)):
        raise OptimizerError(
            f"{label} optimization weights sum to {total:.8f}, not one."
        )
    weights /= total
    if np.any(np.abs(weights) > spec.max_position_weight + tolerance):
        largest = float(np.abs(weights).max())
        raise OptimizerError(
            f"{label} optimization exceeded the {spec.max_position_weight:.1%} "
            f"absolute position limit with a {largest:.1%} holding."
        )
    if spec.max_sector_weight < 1.0:
        for sector, indices in spec.sector_indices.items():
            sector_weight = float(weights[indices].sum())
            if abs(sector_weight) > spec.max_sector_weight + tolerance:
                raise OptimizerError(
                    f"{label} optimization exceeded the "
                    f"{spec.max_sector_weight:.1%} absolute {sector} sector "
                    f"limit with {sector_weight:.1%}."
                )
    return weights


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: SciPy Backend
# SLSQP with multi-start restarts (small problems) and trust-constr (large
# constrained nonlinear problems).
# ═══════════════════════════════════════════════════════════════════════════════


def _corner_start(spec: ProblemSpec) -> Optional[np.ndarray]:
    """Max-return corner portfolio via linear programming, as a warm start."""
    n = spec.num_assets
    a_ub_rows: List[np.ndarray] = []
    b_ub: List[float] = []
    if spec.max_sector_weight < 1.0:
        for indices in spec.sector_indices.values():
            row = np.zeros(n)
            row[indices] = 1.0
            a_ub_rows.append(row)
            b_ub.append(spec.max_sector_weight)
            if not spec.long_only:
                a_ub_rows.append(-row)
                b_ub.append(spec.max_sector_weight)
    try:
        result = linprog(
            c=-spec.mu,
            A_ub=np.vstack(a_ub_rows) if a_ub_rows else None,
            b_ub=np.asarray(b_ub) if b_ub else None,
            A_eq=np.ones((1, n)),
            b_eq=np.array([1.0]),
            bounds=[(spec.lower_bound, spec.max_position_weight)] * n,
            method="highs",
        )
    except Exception:  # noqa: BLE001 - warm start is best-effort only
        return None
    if not result.success:
        return None
    return np.asarray(result.x, dtype=float)


def _inverse_volatility_start(spec: ProblemSpec) -> np.ndarray:
    asset_vols = np.sqrt(np.clip(np.diag(spec.Sigma), 1e-16, None))
    weights = 1.0 / asset_vols
    weights /= weights.sum()
    return np.clip(weights, 0.0, spec.max_position_weight)


def _scipy_starting_points(spec: ProblemSpec) -> List[np.ndarray]:
    starts: List[np.ndarray] = []

    def add(candidate: Optional[np.ndarray]) -> None:
        if candidate is None:
            return
        candidate = np.asarray(candidate, dtype=float)
        if candidate.shape != (spec.num_assets,):
            return
        if any(np.allclose(candidate, existing) for existing in starts):
            return
        starts.append(candidate)

    if spec.initial_guess is not None:
        add(spec.initial_guess)
    for point in spec.starting_points:
        add(point)
    add(spec.equal_weight)
    if spec.target in ("max_sharpe", "max_diversification"):
        corner = _corner_start(spec)
        if corner is not None and starts:
            add(0.5 * (starts[0] + corner))
        add(corner)
    if spec.target == "risk_parity":
        add(_inverse_volatility_start(spec))
    return starts


def _slsqp_constraints(spec: ProblemSpec) -> List[dict]:
    constraints: List[dict] = [
        {
            "type": "eq",
            "fun": lambda x: np.sum(x) - 1,
            "jac": lambda x: np.ones_like(x),
        }
    ]
    if spec.max_sector_weight < 1.0:
        for indices in spec.sector_indices.values():
            upper_gradient = np.zeros(spec.num_assets)
            upper_gradient[indices] = -1.0
            constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda x, idx=indices: (
                        spec.max_sector_weight - float(x[idx].sum())
                    ),
                    "jac": lambda x, gradient=upper_gradient: gradient,
                }
            )
            if not spec.long_only:
                constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda x, idx=indices: (
                            spec.max_sector_weight + float(x[idx].sum())
                        ),
                        "jac": lambda x, gradient=-upper_gradient: gradient,
                    }
                )
    return constraints


def _trust_constr_constraints(spec: ProblemSpec) -> List[LinearConstraint]:
    n = spec.num_assets
    constraints = [LinearConstraint(np.ones((1, n)), 1.0, 1.0)]
    if spec.max_sector_weight < 1.0 and spec.sector_indices:
        rows = []
        for indices in spec.sector_indices.values():
            row = np.zeros(n)
            row[indices] = 1.0
            rows.append(row)
        lower = -spec.max_sector_weight if not spec.long_only else -np.inf
        constraints.append(
            LinearConstraint(np.vstack(rows), lower, spec.max_sector_weight)
        )
    return constraints


def _solve_scipy(spec: ProblemSpec, choice: SolverChoice) -> OptimizationOutcome:
    objective, gradient = _nonlinear_objective(spec)
    label = TARGET_LABELS[spec.target]
    starting_points = _scipy_starting_points(spec)
    if choice.solver == "scipy-trust-constr":
        # Each trust-constr solve on a large universe is expensive (dense
        # interior-point factorizations), so restarts are capped at two.
        starting_points = starting_points[:2]
    failures: List[str] = []
    for attempt, starting_point in enumerate(starting_points, start=1):
        if choice.solver == "scipy-slsqp":
            result = minimize(
                fun=objective,
                jac=gradient,
                x0=np.asarray(starting_point, dtype=float),
                method="SLSQP",
                bounds=spec.scipy_bounds(),
                constraints=_slsqp_constraints(spec),
                options={"maxiter": 3000, "ftol": 1e-10},
            )
        else:
            with warnings.catch_warnings():
                # trust-constr emits advisory warnings (quasi-Newton Hessian,
                # delta_grad == 0) that would clutter the run console.
                warnings.simplefilter("ignore")
                result = minimize(
                    fun=objective,
                    jac=gradient,
                    x0=np.asarray(starting_point, dtype=float),
                    method="trust-constr",
                    bounds=spec.scipy_bounds(),
                    constraints=_trust_constr_constraints(spec),
                    options={"maxiter": 500, "gtol": 1e-7, "xtol": 1e-10},
                )
        try:
            weights = validated_weights(
                spec, np.asarray(result.x, dtype=float), label, tolerance=1e-6
            )
            if not result.success and choice.solver == "scipy-slsqp":
                raise OptimizerError(
                    f"{label} optimization failed: {result.message}"
                )
        except OptimizerError as exc:
            failures.append(f"attempt {attempt}: {exc}")
            continue
        message = ""
        if attempt > 1:
            message = f"converged on recovery attempt {attempt}"
        if not result.success:
            # trust-constr can stop at the iteration cap with a feasible,
            # near-optimal iterate; the validated weights above are usable.
            message = (message + "; " if message else "") + (
                "trust-constr stopped at the iteration limit with a feasible "
                "validated iterate"
            )
        return OptimizationOutcome(
            target=spec.target,
            weights=weights,
            solver=choice.solver,
            formulation=choice.formulation,
            message=message,
        )
    raise OptimizerError(
        f"{label} optimization failed after {len(failures)} attempts using "
        f"{choice.solver}. " + " | ".join(failures)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: CVXPY Backend
# Convex QP/SOCP formulations, including the fractional-programming
# reformulation used for unregularized Max Sharpe and Max Diversification.
# ═══════════════════════════════════════════════════════════════════════════════

_CVXPY_SOLVER_NAMES = {
    "cvxpy-osqp": "OSQP",
    "cvxpy-ecos": "ECOS",
    "cvxpy-scs": "SCS",
}

_CVXPY_SOLVER_OPTIONS = {
    "OSQP": {"eps_abs": 1e-8, "eps_rel": 1e-8, "max_iter": 200000},
    "ECOS": {"abstol": 1e-9, "reltol": 1e-9},
    "SCS": {"eps": 1e-8, "max_iters": 100000},
    "CLARABEL": {},
}


def _covariance_root(Sigma: np.ndarray) -> np.ndarray:
    """Return R with R.T @ R == Sigma (eigen square root, PSD-clipped)."""
    eigenvalues, eigenvectors = np.linalg.eigh((Sigma + Sigma.T) / 2.0)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    return (eigenvectors * np.sqrt(eigenvalues)).T


def _cvxpy_penalty(cp, spec: ProblemSpec, weights_expr):
    if not spec.regularization_active:
        return 0.0
    delta = weights_expr - spec.equal_weight
    if spec.regularization_method == "l2":
        return spec.regularization_strength * cp.sum_squares(delta)
    if spec.regularization_method == "smooth_l1":
        smoothing = 1e-4
        stacked = cp.vstack(
            [
                cp.reshape(delta, (1, spec.num_assets), order="C"),
                np.full((1, spec.num_assets), smoothing),
            ]
        )
        smooth_absolute = cp.norm(stacked, 2, axis=0) - smoothing
        return spec.regularization_strength * cp.sum(smooth_absolute)
    raise ValueError(
        f"Unsupported regularization method: {spec.regularization_method}"
    )


def _cvxpy_standard_constraints(cp, spec: ProblemSpec, weights_expr):
    constraints = [
        cp.sum(weights_expr) == 1,
        weights_expr <= spec.max_position_weight,
        weights_expr >= spec.lower_bound,
    ]
    if spec.max_sector_weight < 1.0:
        for indices in spec.sector_indices.values():
            sector_sum = cp.sum(weights_expr[list(indices)])
            constraints.append(sector_sum <= spec.max_sector_weight)
            if not spec.long_only:
                constraints.append(sector_sum >= -spec.max_sector_weight)
    return constraints


def _cvxpy_problem(cp, spec: ProblemSpec, formulation: str):
    """Build (problem, recover) where recover(values) -> raw weight vector."""
    n = spec.num_assets

    if formulation == "fractional_qp":
        # Standard fractional-programming reformulation: substitute y = k*w
        # (k > 0), which turns the ratio objective into a convex QP because
        # every constraint is positively homogeneous.
        numerator = (
            spec.mu - spec.risk_free_rate
            if spec.target == "max_sharpe"
            else np.sqrt(np.clip(np.diag(spec.Sigma), 1e-16, None))
        )
        y = cp.Variable(n)
        k = cp.Variable(nonneg=True)
        constraints = [
            numerator @ y == 1,
            cp.sum(y) == k,
            y <= spec.max_position_weight * k,
            y >= spec.lower_bound * k,
            k >= 1e-9,
        ]
        if spec.max_sector_weight < 1.0:
            for indices in spec.sector_indices.values():
                sector_sum = cp.sum(y[list(indices)])
                constraints.append(sector_sum <= spec.max_sector_weight * k)
                if not spec.long_only:
                    constraints.append(sector_sum >= -spec.max_sector_weight * k)
        objective = cp.Minimize(cp.quad_form(y, cp.psd_wrap(spec.Sigma)))
        problem = cp.Problem(objective, constraints)

        def recover() -> np.ndarray:
            scale = float(k.value)
            if not np.isfinite(scale) or scale <= 1e-12:
                raise OptimizerError(
                    f"{TARGET_LABELS[spec.target]} reformulation produced an "
                    "invalid scale factor."
                )
            return np.asarray(y.value, dtype=float) / scale

        return problem, recover

    w = cp.Variable(n)
    constraints = _cvxpy_standard_constraints(cp, spec, w)
    penalty = _cvxpy_penalty(cp, spec, w)

    if spec.target == "min_volatility":
        if spec.regularization_active:
            root = _covariance_root(spec.Sigma)
            objective = cp.Minimize(cp.norm(root @ w, 2) + penalty)
        else:
            objective = cp.Minimize(cp.quad_form(w, cp.psd_wrap(spec.Sigma)))
    elif spec.target == "max_return":
        objective = cp.Minimize(-(spec.mu @ w) + penalty)
    else:
        raise OptimizerError(
            f"No convex formulation is available for {spec.target}."
        )
    problem = cp.Problem(objective, constraints)

    def recover() -> np.ndarray:
        return np.asarray(w.value, dtype=float)

    return problem, recover


def _solve_cvxpy(spec: ProblemSpec, choice: SolverChoice) -> OptimizationOutcome:
    cp = cvxpy_module()
    if cp is None:  # pragma: no cover - resolve_solver guards this already
        raise OptimizerError("cvxpy is not installed.")
    label = TARGET_LABELS[spec.target]
    problem, recover = _cvxpy_problem(cp, spec, choice.formulation)

    requested = _CVXPY_SOLVER_NAMES[choice.solver]
    attempts: List[str] = [requested]
    # Mathematically valid fallbacks: the identical convex problem handed to a
    # different numerical engine.  The target meaning never changes.
    for fallback in ("CLARABEL", "SCS"):
        if fallback not in attempts:
            attempts.append(fallback)

    failures: List[str] = []
    for solver_name in attempts:
        if not cvxpy_solver_installed(solver_name):
            failures.append(f"{solver_name}: not installed")
            continue
        if solver_name == "OSQP" and choice.formulation == "conic":
            failures.append("OSQP: cannot solve conic formulations")
            continue
        try:
            problem.solve(
                solver=solver_name, **_CVXPY_SOLVER_OPTIONS.get(solver_name, {})
            )
        except Exception as exc:  # noqa: BLE001 - collect and try next engine
            failures.append(f"{solver_name}: {exc}")
            continue
        if problem.status not in ("optimal", "optimal_inaccurate"):
            failures.append(f"{solver_name}: status {problem.status}")
            continue
        try:
            weights = validated_weights(
                spec, recover(), label, tolerance=1e-5
            )
        except OptimizerError as exc:
            failures.append(f"{solver_name}: {exc}")
            continue
        message = ""
        if solver_name != requested:
            message = (
                f"requested {requested} unavailable or failed; solved the "
                f"identical convex problem with {solver_name}"
            )
        solver_id = f"cvxpy-{solver_name.lower()}"
        return OptimizationOutcome(
            target=spec.target,
            weights=weights,
            solver=solver_id,
            formulation=choice.formulation,
            message=message,
        )
    raise OptimizerError(
        f"{label} optimization failed on every CVXPY engine. "
        + " | ".join(failures)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Public Entry Points
# ═══════════════════════════════════════════════════════════════════════════════


def optimize_portfolio(spec: ProblemSpec) -> OptimizationOutcome:
    """Solve one portfolio optimization problem with the resolved backend."""
    choice = resolve_solver(spec)
    if choice.solver.startswith("cvxpy-"):
        try:
            return _solve_cvxpy(spec, choice)
        except OptimizerError as exc:
            if spec.solver_mode != "auto":
                raise
            # Auto mode may fall back to the general nonlinear formulation of
            # the same target, which preserves its meaning exactly.
            fallback = _scipy_choice(spec, "CVXPY fallback")
            outcome = _solve_scipy(spec, fallback)
            outcome.message = (
                f"CVXPY path failed ({exc}); solved the same target with "
                f"{outcome.solver}. " + outcome.message
            ).strip()
            return outcome
    return _solve_scipy(spec, choice)


def optimize_targets(
    targets: Sequence[str],
    *,
    mu: np.ndarray,
    Sigma: np.ndarray,
    risk_free_rate: float = 0.0,
    long_only: bool = True,
    max_position_weight: float = 1.0,
    max_sector_weight: float = 1.0,
    sector_indices: Optional[Dict[str, np.ndarray]] = None,
    regularization_method: str = "none",
    regularization_strength: float = 0.0,
    solver_mode: str = "auto",
    initial_guess: Optional[np.ndarray] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, OptimizationOutcome]:
    """Compute exactly the requested targets, in a stable order.

    Min Volatility is always computed first when requested so its solution can
    warm-start the ratio targets, matching historical solver behavior.  The
    returned dict preserves the caller's requested display order.
    """
    for target in targets:
        if target not in OPTIMIZATION_TARGETS:
            raise ValueError(f"Unsupported optimization target {target!r}.")
    if not targets:
        raise ValueError("At least one optimization target is required.")

    compute_order = [t for t in ("min_volatility",) if t in targets]
    compute_order += [t for t in targets if t not in compute_order]

    outcomes: Dict[str, OptimizationOutcome] = {}
    warm_starts: List[np.ndarray] = []
    for target in compute_order:
        spec = ProblemSpec(
            target=target,
            mu=mu,
            Sigma=Sigma,
            risk_free_rate=risk_free_rate,
            long_only=long_only,
            max_position_weight=max_position_weight,
            max_sector_weight=max_sector_weight,
            sector_indices=dict(sector_indices or {}),
            regularization_method=regularization_method,
            regularization_strength=regularization_strength,
            solver_mode=solver_mode,
            initial_guess=initial_guess,
            starting_points=tuple(warm_starts),
        )
        if progress is not None:
            choice = resolve_solver(spec)
            progress(
                f"{TARGET_LABELS[target]} -> {choice.solver} "
                f"({choice.formulation}; {choice.reason})"
            )
        outcome = optimize_portfolio(spec)
        outcomes[target] = outcome
        warm_starts.append(outcome.weights)

    return {target: outcomes[target] for target in targets}

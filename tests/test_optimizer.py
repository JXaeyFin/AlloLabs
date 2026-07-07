"""Tests for the modular optimizer layer (allolabs_optimizer).

Covers solver auto-selection (including the large Max Sharpe SLSQP avoidance
that fixes the "positive directional derivative for linesearch" known issue),
explicit solver validation, only-requested-target computation, and small
end-to-end solves for every supported target.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

import allolabs_optimizer as optimizer


def synthetic_problem(num_assets: int = 12, seed: int = 7):
    rng = np.random.default_rng(seed)
    factors = rng.normal(size=(num_assets, 3))
    Sigma = factors @ factors.T * 0.004 + np.diag(rng.uniform(0.01, 0.06, num_assets))
    mu = rng.uniform(0.02, 0.18, size=num_assets)
    return mu, Sigma


def spec_for(target: str, num_assets: int = 12, **overrides) -> optimizer.ProblemSpec:
    mu, Sigma = synthetic_problem(num_assets)
    settings = dict(
        target=target,
        mu=mu,
        Sigma=Sigma,
        risk_free_rate=0.0268,
        long_only=True,
        max_position_weight=0.25,
    )
    settings.update(overrides)
    return optimizer.ProblemSpec(**settings)


class TargetParsingTests(unittest.TestCase):
    def test_default_targets_preserve_classic_pair(self):
        self.assertEqual(
            optimizer.parse_targets(None), ["max_sharpe", "min_volatility"]
        )
        self.assertEqual(
            optimizer.parse_targets(""), ["max_sharpe", "min_volatility"]
        )

    def test_parse_targets_orders_and_dedupes(self):
        self.assertEqual(
            optimizer.parse_targets("risk_parity, max_sharpe,risk_parity"),
            ["risk_parity", "max_sharpe"],
        )

    def test_parse_targets_rejects_unknown_values(self):
        with self.assertRaisesRegex(ValueError, "Unsupported optimization target"):
            optimizer.parse_targets("max_sharpe,momentum")


class SolverResolutionTests(unittest.TestCase):
    def test_small_portfolios_can_still_use_slsqp(self):
        # Nonlinear small problem in auto mode resolves to SLSQP.
        spec = spec_for(
            "max_sharpe",
            num_assets=50,
            regularization_method="l2",
            regularization_strength=0.1,
        )
        with patch.dict(optimizer._CVXPY_CACHE, {"module": None}):
            self.assertEqual(optimizer.resolve_solver(spec).solver, "scipy-slsqp")
        # Explicit SLSQP is honored regardless of problem size.
        spec = spec_for("max_sharpe", num_assets=50, solver_mode="scipy-slsqp")
        self.assertEqual(optimizer.resolve_solver(spec).solver, "scipy-slsqp")

    def test_large_max_sharpe_never_defaults_to_slsqp(self):
        mu = np.linspace(0.02, 0.20, 947)
        Sigma = np.eye(947) * 0.04
        for method, strength in (("none", 0.0), ("l2", 0.1), ("smooth_l1", 0.1)):
            spec = optimizer.ProblemSpec(
                target="max_sharpe",
                mu=mu,
                Sigma=Sigma,
                risk_free_rate=0.0268,
                regularization_method=method,
                regularization_strength=strength,
            )
            choice = optimizer.resolve_solver(spec)
            self.assertNotEqual(
                choice.solver,
                "scipy-slsqp",
                f"auto mode picked SLSQP for a 947-asset Max Sharpe "
                f"(regularization={method})",
            )
            with patch.dict(optimizer._CVXPY_CACHE, {"module": None}):
                fallback_choice = optimizer.resolve_solver(spec)
            self.assertNotEqual(fallback_choice.solver, "scipy-slsqp")

    def test_convex_targets_prefer_cvxpy_when_available(self):
        if not optimizer.cvxpy_available():
            self.skipTest("cvxpy is not installed")
        for target in ("min_volatility", "max_return"):
            choice = optimizer.resolve_solver(spec_for(target, num_assets=300))
            self.assertTrue(
                choice.solver.startswith("cvxpy-"),
                f"{target} resolved to {choice.solver}",
            )
        # Unregularized Max Sharpe uses the convex fractional reformulation.
        choice = optimizer.resolve_solver(spec_for("max_sharpe", num_assets=300))
        self.assertTrue(choice.solver.startswith("cvxpy-"))
        self.assertEqual(choice.formulation, "fractional_qp")

    def test_conic_formulations_avoid_osqp(self):
        if not optimizer.cvxpy_available():
            self.skipTest("cvxpy is not installed")
        spec = spec_for(
            "min_volatility",
            regularization_method="l2",
            regularization_strength=0.1,
        )
        choice = optimizer.resolve_solver(spec)
        self.assertIn(choice.solver, ("cvxpy-ecos", "cvxpy-scs"))
        spec.solver_mode = "cvxpy-osqp"
        with self.assertRaisesRegex(optimizer.OptimizerError, "OSQP"):
            optimizer.resolve_solver(spec)

    def test_risk_parity_is_nonlinear_only(self):
        spec = spec_for("risk_parity")
        self.assertIsNone(optimizer.convex_formulation(spec))
        spec.solver_mode = "cvxpy-osqp"
        with self.assertRaisesRegex(optimizer.OptimizerError, "cannot express"):
            optimizer.resolve_solver(spec)
        with self.assertRaisesRegex(ValueError, "long-only"):
            spec_for("risk_parity", long_only=False)

    def test_missing_cvxpy_fails_clearly_for_explicit_modes(self):
        spec = spec_for("min_volatility", solver_mode="cvxpy-osqp")
        with patch.dict(optimizer._CVXPY_CACHE, {"module": None}):
            with self.assertRaisesRegex(optimizer.OptimizerError, "cvxpy"):
                optimizer.resolve_solver(spec)

    def test_unknown_targets_and_modes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported optimization target"):
            spec_for("momentum")
        with self.assertRaisesRegex(ValueError, "Unsupported solver mode"):
            spec_for("max_sharpe", solver_mode="gradient-descent")


class EndToEndSolveTests(unittest.TestCase):
    def assert_valid_weights(self, spec, outcome):
        self.assertAlmostEqual(float(outcome.weights.sum()), 1.0, places=6)
        self.assertLessEqual(
            float(np.abs(outcome.weights).max()),
            spec.max_position_weight + 1e-5,
        )
        if spec.long_only:
            self.assertGreaterEqual(float(outcome.weights.min()), -1e-9)

    def test_every_target_solves_on_a_small_problem(self):
        for target in optimizer.OPTIMIZATION_TARGETS:
            spec = spec_for(target)
            outcome = optimizer.optimize_portfolio(spec)
            self.assertEqual(outcome.target, target)
            self.assert_valid_weights(spec, outcome)

    def test_risk_parity_equalizes_risk_contributions(self):
        spec = spec_for("risk_parity", max_position_weight=1.0)
        outcome = optimizer.optimize_portfolio(spec)
        contributions = outcome.weights * (spec.Sigma @ outcome.weights)
        contributions /= contributions.sum()
        self.assertLess(float(contributions.max() - contributions.min()), 1e-4)

    def test_cvxpy_and_slsqp_agree_on_max_sharpe(self):
        if not optimizer.cvxpy_available():
            self.skipTest("cvxpy is not installed")
        spec = spec_for("max_sharpe")
        convex = optimizer.optimize_portfolio(spec)
        self.assertTrue(convex.solver.startswith("cvxpy-"))
        nonlinear = optimizer._solve_scipy(
            spec_for("max_sharpe", solver_mode="scipy-slsqp"),
            optimizer.SolverChoice("scipy-slsqp", "nonlinear", "test"),
        )
        self.assertLess(
            float(np.abs(convex.weights - nonlinear.weights).max()), 1e-3
        )

    def test_sector_caps_are_respected_across_backends(self):
        sector_indices = {"Tech": np.arange(0, 6)}
        for solver_mode in ("auto", "scipy-slsqp"):
            spec = spec_for(
                "max_sharpe",
                sector_indices=sector_indices,
                max_sector_weight=0.35,
                solver_mode=solver_mode,
            )
            outcome = optimizer.optimize_portfolio(spec)
            self.assertLessEqual(
                float(outcome.weights[:6].sum()), 0.35 + 1e-5
            )

    def test_only_requested_targets_are_computed(self):
        mu, Sigma = synthetic_problem()
        calls = []
        original = optimizer.optimize_portfolio

        def tracking(spec):
            calls.append(spec.target)
            return original(spec)

        with patch.object(optimizer, "optimize_portfolio", side_effect=tracking):
            outcomes = optimizer.optimize_targets(
                ["max_sharpe"],
                mu=mu,
                Sigma=Sigma,
                risk_free_rate=0.0268,
                max_position_weight=0.25,
            )
        self.assertEqual(calls, ["max_sharpe"])
        self.assertEqual(list(outcomes), ["max_sharpe"])

    def test_optimize_targets_preserves_request_order_with_min_vol_warm_start(self):
        mu, Sigma = synthetic_problem()
        outcomes = optimizer.optimize_targets(
            ["max_sharpe", "min_volatility"],
            mu=mu,
            Sigma=Sigma,
            risk_free_rate=0.0268,
            max_position_weight=0.25,
        )
        self.assertEqual(list(outcomes), ["max_sharpe", "min_volatility"])

    def test_labels_and_context_lines_cover_all_targets(self):
        for target in optimizer.OPTIMIZATION_TARGETS:
            self.assertIn(target, optimizer.TARGET_LABELS)
            self.assertIn(target, optimizer.TARGET_FORMAL_LABELS)
            self.assertIn(target, optimizer.TARGET_COLUMN_KEYS)
            self.assertIn(target, optimizer.TARGET_RISK_POSTURES)
        lines = optimizer.ai_context_lines(
            ["max_sharpe", "min_volatility"], "cvxpy-osqp"
        )
        self.assertIn("Max Sharpe Ratio", lines[0])
        self.assertIn("Min Volatility", lines[0])
        self.assertEqual(lines[1], "Solver mode: cvxpy-osqp")


if __name__ == "__main__":
    unittest.main()

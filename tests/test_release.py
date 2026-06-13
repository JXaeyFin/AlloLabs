from __future__ import annotations

import ast
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from dashboard import runner, server

try:
    import wealthgpt_report
except ModuleNotFoundError:
    wealthgpt_report = None


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_asset_universe():
    source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ASSET_UNIVERSE" for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def dashboard_config(**overrides):
    config = {
        "trainingYears": 1,
        "oosMonths": 6,
        "maxPositionPercent": 20,
        "longOnly": True,
        "maxSectorPercent": 100,
        "regularization": "none",
        "regularizationStrength": 0.0,
        "universe": "curated",
        "gptViews": False,
        "researchProvider": "openai",
        "researchModel": "gpt-5.4",
        "auditViews": False,
        "auditProvider": "openai",
        "auditModel": "gpt-5.5",
        "refreshCache": False,
    }
    config.update(overrides)
    return config


class ConfigurationTests(unittest.TestCase):
    def test_dashboard_config_maps_to_environment(self):
        environment = runner.configuration_environment(
            dashboard_config(
                trainingYears=2.5,
                oosMonths=12,
                maxPositionPercent=15,
                longOnly=False,
                maxSectorPercent=30,
                regularization="l2",
                regularizationStrength=0.25,
                universe="canada",
                gptViews=True,
                researchProvider="anthropic",
                researchModel="claude-sonnet-4-6",
                auditViews=True,
                auditProvider="gemini",
                auditModel="gemini-3.1-pro-preview",
            )
        )
        self.assertEqual(environment["WEALTHGPT_TRAINING_YEARS"], "2.5")
        self.assertEqual(environment["WEALTHGPT_OOS_YEARS"], "1.0")
        self.assertEqual(environment["WEALTHGPT_MAX_POSITION_WEIGHT"], "0.15")
        self.assertEqual(environment["WEALTHGPT_LONG_ONLY"], "0")
        self.assertEqual(environment["WEALTHGPT_MAX_SECTOR_WEIGHT"], "0.3")
        self.assertEqual(environment["WEALTHGPT_REGULARIZATION"], "l2")
        self.assertEqual(environment["WEALTHGPT_RESEARCH_PROVIDER"], "anthropic")
        self.assertEqual(environment["WEALTHGPT_RESEARCH_MODEL"], "claude-sonnet-4-6")
        self.assertEqual(environment["WEALTHGPT_AUDIT_PROVIDER"], "gemini")
        self.assertEqual(environment["WEALTHGPT_GPT_AUDIT_MODEL"], "gemini-3.1-pro-preview")
        self.assertEqual(environment["WEALTHGPT_GPT_VIEWS"], "1")
        self.assertEqual(environment["WEALTHGPT_GPT_AUDIT"], "1")
        self.assertIn("RY.TO", json.loads(environment["WEALTHGPT_RESEARCH_TICKERS"]))

    def test_server_rejects_coerced_boolean_values(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            server.validate_config(
                dashboard_config(gptViews="false")
            )
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            server.validate_config(
                dashboard_config(longOnly="false")
            )

    def test_server_rejects_fractional_whole_number_fields(self):
        with self.assertRaisesRegex(ValueError, "whole numbers"):
            server.validate_config(
                dashboard_config(oosMonths=6.5)
            )

    def test_server_rejects_audit_without_gpt_views(self):
        with self.assertRaisesRegex(ValueError, "requires AI-assisted views"):
            server.validate_config(
                dashboard_config(auditViews=True)
            )

    def test_server_rejects_unknown_or_mismatched_ai_model(self):
        with self.assertRaisesRegex(ValueError, "research model is not allowlisted"):
            server.validate_config(dashboard_config(researchModel="imaginary-model"))
        with self.assertRaisesRegex(ValueError, "research model is not allowlisted"):
            server.validate_config(
                dashboard_config(
                    researchProvider="anthropic",
                    researchModel="gpt-5.4",
                )
            )

    def test_provider_response_extractors(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            "extract_anthropic_response_text",
            "extract_gemini_response_text",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in function_names
        ]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "wealthgpt.py", "exec"), namespace)
        self.assertEqual(
            namespace["extract_anthropic_response_text"]({
                "content": [{"type": "text", "text": '{"views":[]}'}],
                "stop_reason": "end_turn",
            }),
            '{"views":[]}',
        )
        self.assertEqual(
            namespace["extract_gemini_response_text"]({
                "candidates": [{
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": '{"views":[]}'}]},
                }],
            }),
            '{"views":[]}',
        )

    def test_regularization_penalties_are_zero_at_target(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "regularization_penalty"
        )
        namespace = {"np": np}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "wealthgpt.py", "exec"), namespace)
        target = np.array([0.5, 0.5])
        concentrated = np.array([0.9, 0.1])
        penalty = namespace["regularization_penalty"]
        self.assertEqual(penalty(target, target, "l2", 1.0), 0.0)
        self.assertGreater(penalty(concentrated, target, "l2", 1.0), 0.0)
        self.assertGreater(penalty(concentrated, target, "smooth_l1", 1.0), 0.0)

    def test_optimizer_covariance_and_gradients_are_numerically_stable(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            "stabilize_covariance",
            "portfolio_performance",
            "regularization_penalty",
            "regularization_gradient",
            "negative_sharpe",
            "negative_sharpe_gradient",
            "portfolio_variance",
            "portfolio_variance_gradient",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in function_names
        ]
        namespace = {"np": np, "Tuple": tuple}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "wealthgpt.py", "exec"), namespace)

        singular = np.array([
            [0.04, 0.04, 0.02],
            [0.04, 0.04, 0.02],
            [0.02, 0.02, 0.01],
        ])
        covariance = namespace["stabilize_covariance"](singular)
        self.assertGreater(float(np.linalg.eigvalsh(covariance).min()), 0.0)
        np.testing.assert_allclose(covariance, covariance.T)

        weights = np.array([0.40, 0.35, 0.25])
        target = np.ones(3) / 3
        expected_returns = np.array([0.12, 0.08, 0.05])
        epsilon = 1e-6

        objective_cases = [
            (
                namespace["negative_sharpe"],
                namespace["negative_sharpe_gradient"],
                (expected_returns, covariance, 0.0268, target, "l2", 0.2),
            ),
            (
                namespace["portfolio_variance"],
                namespace["portfolio_variance_gradient"],
                (covariance, target, "smooth_l1", 0.2),
            ),
        ]
        for objective, gradient, arguments in objective_cases:
            numerical = np.zeros_like(weights)
            for index in range(len(weights)):
                step = np.zeros_like(weights)
                step[index] = epsilon
                numerical[index] = (
                    objective(weights + step, *arguments)
                    - objective(weights - step, *arguments)
                ) / (2 * epsilon)
            np.testing.assert_allclose(
                gradient(weights, *arguments),
                numerical,
                rtol=1e-5,
                atol=1e-6,
            )

        self.assertIn("run_slsqp_with_restarts", source)
        self.assertIn('"maxiter": 3000', source)

    def test_optimizer_validation_allows_shorts_only_when_configured(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "validated_optimizer_weights"
        )
        namespace = {
            "np": np,
            "long_only": False,
            "max_position_weight": 0.75,
            "max_sector_weight": 1.0,
            "optimizer_sector_indices": {},
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "wealthgpt.py", "exec"), namespace)
        result = SimpleNamespace(
            success=True,
            message="ok",
            x=np.array([-0.2, 0.6, 0.6]),
        )
        validated = namespace["validated_optimizer_weights"](result, "Test")
        self.assertAlmostEqual(float(validated.sum()), 1.0)
        self.assertLess(float(validated.min()), 0.0)

        namespace["long_only"] = True
        with self.assertRaisesRegex(RuntimeError, "negative weight"):
            namespace["validated_optimizer_weights"](result, "Test")

    def test_audit_summary_detects_cross_set_edits(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "compare_audited_views"
        )
        namespace = {"re": re}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "wealthgpt.py", "exec"), namespace)
        original = [
            {"ticker": "AAA", "industry": "Banking", "view": "Stable.", "expected_return": 0.10, "confidence": 0.70},
            {"ticker": "BBB", "industry": "Software", "view": "Mixed.", "expected_return": -0.02, "confidence": 0.55},
        ]
        audited = [
            {"ticker": "AAA", "industry": "Banking", "view": "Stable.", "expected_return": 0.07, "confidence": 0.65},
            {"ticker": "BBB", "industry": "Technology", "view": "Risk adjusted.", "expected_return": -0.02, "confidence": 0.55},
        ]
        summary = namespace["compare_audited_views"](original, audited)
        self.assertEqual(summary["inputCount"], 2)
        self.assertEqual(summary["adjustedCount"], 2)
        self.assertEqual(summary["industryChangedCount"], 1)
        self.assertEqual(summary["rationaleChangedCount"], 1)
        self.assertEqual(summary["meanRationaleWords"], 1.5)
        self.assertEqual(summary["minRationaleWords"], 1)
        self.assertEqual(summary["maxRationaleWords"], 2)

    def test_global_audit_prompt_requires_detailed_longer_rationales(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_global_audit_prompt"
        )
        namespace = {"json": json}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "wealthgpt.py", "exec"),
            namespace,
        )
        prompt = namespace["build_global_audit_prompt"]([
            {
                "ticker": "AAA",
                "industry": "Software",
                "view": "Existing rationale.",
                "expected_return": 0.08,
                "confidence": 0.65,
            }
        ])
        self.assertIn("45-75 words", prompt)
        self.assertIn("probability-weighted 12-month total-return", prompt)
        self.assertIn("systematic optimism or pessimism", prompt)
        self.assertIn("primary downside risk", prompt)
        self.assertIn('"ticker":"AAA"', prompt)

    def test_view_schema_can_describe_audit_rationale_quality(self):
        source = (REPOSITORY_ROOT / "wealthgpt.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_views_schema"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "wealthgpt.py", "exec"),
            namespace,
        )
        schema = namespace["build_views_schema"](
            ["AAA"],
            view_description="Detailed audit rationale.",
        )
        view_schema = schema["properties"]["views"]["items"]["properties"]["view"]
        self.assertEqual(view_schema["description"], "Detailed audit rationale.")

    def test_default_model_path_is_repository_local(self):
        self.assertEqual(server.DEFAULT_SCRIPT, REPOSITORY_ROOT / "wealthgpt.py")

    def test_bundled_dashboard_snapshot_is_available(self):
        payload = json.loads(server.DEFAULT_RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(payload["dataMode"], "example")
        self.assertFalse(payload["config"]["auditViews"])
        self.assertTrue(payload["portfolios"]["max"]["holdings"])
        self.assertTrue(payload["portfolios"]["min"]["holdings"])
        self.assertGreater(len(payload["research"]), 100)
        self.assertTrue(server.DEFAULT_PDF.is_file())
        self.assertTrue(server.DEFAULT_CHART.is_file())

    def test_dashboard_consolidates_run_controls_in_console(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="remote-audit"', markup)
        self.assertIn('id="remote-research-provider"', markup)
        self.assertIn('id="remote-audit-provider"', markup)
        self.assertIn('id="remote-gpt-model"', markup)
        self.assertIn('id="remote-regularization"', markup)
        self.assertNotIn('id="remote-sector-cap-enabled"', markup)
        self.assertIn('id="remote-sector-cap" type="number" min="5" max="100" step="1" value="100"', markup)
        self.assertIn('id="remote-long-only"', markup)
        self.assertNotIn('id="remote-long-only" type="checkbox" checked disabled', markup)
        self.assertNotIn('id="settings-view"', markup)
        self.assertIn("auditViews: remoteAuditToggle.checked", script)
        self.assertIn("researchProvider: remoteResearchProvider.value", script)
        self.assertIn("longOnly: longOnlyToggle.checked", script)
        self.assertIn('id="run-progress-track"', markup)
        self.assertIn('role="progressbar"', markup)
        self.assertIn("buildRunProgressPlan", script)
        self.assertIn("estimatedUniverseSize", script)
        self.assertIn("config.auditViews", script)
        self.assertIn("config.refreshCache", script)
        self.assertIn("Sending .* request for tickers", script)
        self.assertIn("Global AI audit complete", script)
        self.assertIn("finishRunProgress", script)

    def test_project_logo_is_used_for_dashboard_and_readme(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        stylesheet = (REPOSITORY_ROOT / "dashboard" / "terminal-theme.css").read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        logo = REPOSITORY_ROOT / "resources" / "wealthgpt-logo.png"
        self.assertTrue(logo.is_file())
        self.assertGreater(logo.stat().st_size, 1000)
        self.assertIn("data-project-logo", markup)
        self.assertIn("brand-mark-fallback", markup)
        self.assertNotIn('<span class="brand-mark">WG</span>', markup)
        self.assertIn(".brand-mark img", stylesheet)
        self.assertIn("activateProjectLogo", (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8"))
        self.assertGreaterEqual(server.API_VERSION, 13)
        self.assertIn('src="resources/wealthgpt-logo.png"', readme)
        self.assertEqual(server.RESOURCES_DIR, REPOSITORY_ROOT / "resources")

    def test_model_guide_reports_only_masked_provider_key_status(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="provider-key-status"', markup)
        self.assertIn("renderProviderKeyStatus", script)
        self.assertIn("providerKeyStatusSignature", script)
        self.assertIn("data-copy-provider-command", script)
        self.assertIn("Restart dashboard (connected server is API v", script)
        self.assertIn('"Detected" : "Not detected"', script)
        self.assertGreaterEqual(server.API_VERSION, 14)

        keys = {
            "OPENAI_API_KEY": "sk-proj-example-secret-1234",
            "ANTHROPIC_API_KEY": "",
            "GEMINI_API_KEY": "short",
        }
        with patch.dict(os.environ, keys, clear=False):
            status = server.provider_key_status()
        encoded = json.dumps(status)
        self.assertTrue(status["openai"]["active"])
        self.assertEqual(status["openai"]["preview"], "sk-proj********1234")
        self.assertEqual(status["openai"]["source"], "Dashboard process")
        self.assertFalse(status["anthropic"]["active"])
        self.assertIsNone(status["anthropic"]["preview"])
        self.assertEqual(status["gemini"]["preview"], "********")
        for secret in keys.values():
            if secret:
                self.assertNotIn(secret, encoded)

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False), patch.object(
            server,
            "windows_environment_value",
            return_value=("persisted-openai-secret", "Windows user environment"),
        ):
            value, source = server.resolved_api_key("OPENAI_API_KEY")
        self.assertEqual(value, "persisted-openai-secret")
        self.assertEqual(source, "Windows user environment")

    def test_portfolio_holdings_open_company_detail_modal(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        company_source = (REPOSITORY_ROOT / "wealthgpt_company.py").read_text(encoding="utf-8")
        self.assertIn('id="company-modal"', markup)
        self.assertIn('id="company-modal-close"', markup)
        self.assertIn('role="dialog"', markup)
        self.assertIn("data-company-ticker", script)
        self.assertIn('class="research-ticker"', script)
        self.assertIn('data-company-context="research"', script)
        self.assertIn("research_company_details", script)
        self.assertIn('getElementById("research-list").addEventListener("click"', script)
        self.assertIn("Math.abs(weight) > 0.01", script)
        self.assertIn("Holdings above 0.01%", markup)
        self.assertIn("/api/company?ticker=", script)
        self.assertIn("Same inputs supplied to AI research", script)
        self.assertIn("/resources/company-logos/", script)
        self.assertNotIn("https://img.logo.dev/ticker/", script)
        self.assertNotIn("LOGO_DEV_PUBLISHABLE_KEY", script)
        self.assertIn("Locally cached logos provided by Logo.dev", script)
        self.assertIn('id="company-logo"', script)
        self.assertGreaterEqual(server.API_VERSION, 16)
        self.assertEqual(
            server.COMPANY_LOGOS_DIR,
            REPOSITORY_ROOT / "resources" / "company-logos",
        )
        logo_cache_script = REPOSITORY_ROOT / "scripts" / "cache-company-logos.py"
        self.assertTrue(logo_cache_script.is_file())
        cache_source = logo_cache_script.read_text(encoding="utf-8")
        self.assertIn("ASSET_UNIVERSE", cache_source)
        self.assertIn("LOGO_DEV_PUBLISHABLE_KEY", cache_source)
        self.assertIn("manifest.json", cache_source)
        self.assertIn('("404", "company"), ("monogram", "monogram")', cache_source)
        self.assertNotIn("pk_", cache_source)

        manifest_path = server.COMPANY_LOGOS_DIR / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest["logos"]
        self.assertEqual(manifest["tickerCount"], 285)
        self.assertEqual(len(records), 285)
        self.assertFalse([record for record in records if record["status"] == "failed"])
        for record in records:
            logo_path = server.COMPANY_LOGOS_DIR / record["file"]
            self.assertTrue(logo_path.is_file(), record["ticker"])
            self.assertTrue(logo_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("P/E (TTM)", company_source)
        self.assertIn("EV/EBITDA", company_source)
        self.assertIn("max_news: int = 5", company_source)
        self.assertIn('"url": _news_url(item, content)', company_source)
        self.assertIn("safeNewsUrl", script)
        self.assertIn('class="company-news-link"', script)
        self.assertIn('rel="noopener noreferrer"', script)

    def test_company_detail_endpoint_only_allows_portfolio_tickers(self):
        results = {
            "portfolios": {
                "max": {"holdings": [{"ticker": "AAA"}, {"ticker": "BBB.TO"}]},
                "min": {"holdings": [{"ticker": "CCC"}]},
            },
            "research": [{"ticker": "DDD"}, {"ticker": "EEE.L"}],
        }
        self.assertEqual(
            server.result_company_tickers(results),
            {"AAA", "BBB.TO", "CCC", "DDD", "EEE.L"},
        )
        self.assertTrue(server.TICKER_PATTERN.fullmatch("BRK-B"))
        self.assertFalse(server.TICKER_PATTERN.fullmatch("../secret"))

    def test_model_guide_covers_every_selectable_ai_model(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        selectable_models = {
            model
            for stage in server.ALLOWED_AI_MODELS.values()
            for models in stage.values()
            for model in models
        }
        dropdown_catalog = script.split("const MODEL_GUIDE", 1)[0]
        self.assertIn('id="models-view"', markup)
        self.assertIn('data-shortcut-view="models"', markup)
        self.assertIn("Context", script)
        self.assertIn("Weakness", script)
        for model in selectable_models:
            self.assertIn(f'["{model}",', dropdown_catalog)
            self.assertIn(f'id: "{model}"', script)

    def test_every_supported_model_is_selectable_at_both_ai_stages(self):
        self.assertEqual(
            server.ALLOWED_AI_MODELS["research"],
            server.ALLOWED_AI_MODELS["audit"],
        )
        self.assertEqual(
            len(server.ALLOWED_AI_MODELS["research"]["gemini"]),
            7,
        )

    def test_asset_universe_has_no_duplicates_or_stale_symbols(self):
        universe = load_asset_universe()
        self.assertEqual(len(universe), len(set(universe)))
        self.assertTrue({"CDNS", "STLAM.MI", "RHHBY", "BNY"}.issubset(universe))
        self.assertTrue({"ANSS", "STLA.MI", "ROG.SW", "BK", "SHOP"}.isdisjoint(universe))

    def test_asset_universe_covers_material_global_omissions(self):
        universe = set(load_asset_universe())
        expected = {
            "AMAT", "GEV", "INTU", "LMT", "NOW", "UBER",
            "CLS.TO", "IFC.TO", "IMO.TO",
            "BAE.L", "RR.L",
            "ALV.DE", "SU.PA", "TTE.PA", "IBE.MC", "ITX.MC",
            "BHP", "NVO", "SONY", "TM", "TSM",
        }
        self.assertTrue(expected.issubset(universe))


class MetadataTests(unittest.TestCase):
    def test_listing_metadata_cache_is_reused(self):
        fixtures = {
            "TD.TO": {
                "exchange": "TOR",
                "country": "Canada",
                "currency": "CAD",
                "quoteType": "EQUITY",
            },
            "MSFT": {
                "exchange": "NMS",
                "country": "United States",
                "currency": "USD",
                "quoteType": "EQUITY",
            },
        }
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "listing.json"

            def fake_fetch(ticker):
                return ticker, runner.normalize_listing(ticker, fixtures[ticker])

            with patch.object(runner, "fetch_listing", side_effect=fake_fetch) as fetch:
                first = runner.resolve_listing_metadata(fixtures, cache_path)
                second = runner.resolve_listing_metadata(fixtures, cache_path)

            self.assertEqual(fetch.call_count, len(fixtures))
            self.assertEqual(first, second)
            self.assertEqual(first["TD.TO"]["currency"], "CAD")

    @unittest.skipIf(wealthgpt_report is None, "Scientific reporting dependencies are unavailable.")
    def test_sector_resolution_uses_research_before_yahoo(self):
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "sector_cache.json"
            sectors = wealthgpt_report.resolve_sectors(
                ["TEST"],
                np.array([1.0]),
                np.array([1.0]),
                {"TEST": {"industry": "Semiconductor Equipment"}},
                cache_path,
            )
            self.assertEqual(sectors["TEST"], "Information Technology")


class ReportTests(unittest.TestCase):
    @unittest.skipIf(wealthgpt_report is None, "Scientific reporting dependencies are unavailable.")
    def test_optional_research_percentages_render_safely(self):
        self.assertEqual(wealthgpt_report._format_optional_percent(None), "N/A")
        self.assertEqual(wealthgpt_report._format_optional_percent(float("nan")), "N/A")
        self.assertEqual(wealthgpt_report._format_optional_percent("invalid"), "N/A")
        self.assertEqual(wealthgpt_report._format_optional_percent(0.1234), "12.3%")

    @unittest.skipIf(wealthgpt_report is None, "Scientific reporting dependencies are unavailable.")
    def test_report_builds_without_research_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            output_path = Path(folder) / "report.pdf"
            missing_analysis = Path(folder) / "missing.json"
            wealthgpt_report.create_portfolio_pdf(
                output_path=output_path,
                tickers=["AEM.TO", "RY.TO"],
                max_weights=np.array([0.6, 0.4]),
                min_weights=np.array([0.4, 0.6]),
                max_metrics={"return": 0.10, "volatility": 0.15, "sharpe": 0.49},
                min_metrics={"return": 0.07, "volatility": 0.10, "sharpe": 0.43},
                analysis_path=missing_analysis,
                training_start="2025-01-01",
                training_end="2025-12-31",
            )
            self.assertTrue(output_path.is_file())
            self.assertGreater(output_path.stat().st_size, 1_000)


if __name__ == "__main__":
    unittest.main()

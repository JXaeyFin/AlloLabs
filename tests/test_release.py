from __future__ import annotations

import ast
import io
import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import allolabs_paths
import allolabs_guide
from dashboard import runner, server

try:
    import allolabs_report
except ModuleNotFoundError:
    allolabs_report = None


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_asset_universe():
    source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
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
        "analystSeedPrompt": "",
        "auditorSeedPrompt": "",
    }
    config.update(overrides)
    return config


class ConfigurationTests(unittest.TestCase):
    def test_repository_uses_only_allolabs_branding(self):
        retired_names = ("wealth" + "gpt", "wealth" + "opt")
        excluded_directories = {
            "_local_archive", "__pycache__", ".git", ".desktop-build",
            "build", "dist", "release", "tmp", "webview-profile",
        }
        text_suffixes = {
            ".py", ".js", ".html", ".css", ".md", ".json", ".txt",
            ".yml", ".yaml", ".ps1", ".bat", ".example", ".gitignore",
        }
        stale_files = []
        stale_text = []
        for path in REPOSITORY_ROOT.rglob("*"):
            if any(part in excluded_directories for part in path.parts):
                continue
            if any(name in path.name.lower() for name in retired_names):
                stale_files.append(str(path.relative_to(REPOSITORY_ROOT)))
            if not path.is_file():
                continue
            if path.suffix.lower() not in text_suffixes and path.name not in {
                ".env.example",
                ".gitignore",
            }:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(name in content for name in retired_names):
                stale_text.append(str(path.relative_to(REPOSITORY_ROOT)))

        self.assertEqual(stale_files, [])
        self.assertEqual(stale_text, [])
        self.assertTrue((REPOSITORY_ROOT / "allolabs.py").is_file())
        self.assertTrue((REPOSITORY_ROOT / "resources" / "allolabs-logo.png").is_file())
        self.assertGreaterEqual(server.API_VERSION, 17)

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
                analystSeedPrompt="- Tech beats defensives",
                auditorSeedPrompt="- Check overconfidence",
            )
        )
        self.assertEqual(environment["ALLOLABS_TRAINING_YEARS"], "2.5")
        self.assertEqual(environment["ALLOLABS_OOS_YEARS"], "1.0")
        self.assertEqual(environment["ALLOLABS_MAX_POSITION_WEIGHT"], "0.15")
        self.assertEqual(environment["ALLOLABS_LONG_ONLY"], "0")
        self.assertEqual(environment["ALLOLABS_MAX_SECTOR_WEIGHT"], "0.3")
        self.assertEqual(environment["ALLOLABS_REGULARIZATION"], "l2")
        self.assertEqual(environment["ALLOLABS_RESEARCH_PROVIDER"], "anthropic")
        self.assertEqual(environment["ALLOLABS_RESEARCH_MODEL"], "claude-sonnet-4-6")
        self.assertEqual(environment["ALLOLABS_AUDIT_PROVIDER"], "gemini")
        self.assertEqual(environment["ALLOLABS_GPT_AUDIT_MODEL"], "gemini-3.1-pro-preview")
        self.assertEqual(environment["ALLOLABS_GPT_VIEWS"], "1")
        self.assertEqual(environment["ALLOLABS_GPT_AUDIT"], "1")
        self.assertEqual(environment["ALLOLABS_ANALYST_SEED_PROMPT"], "- Tech beats defensives")
        self.assertEqual(environment["ALLOLABS_AUDITOR_SEED_PROMPT"], "- Check overconfidence")
        self.assertIn("RY.TO", json.loads(environment["ALLOLABS_RESEARCH_TICKERS"]))

    def test_server_rejects_coerced_boolean_values(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            server.validate_config(
                dashboard_config(gptViews="false")
            )
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            server.validate_config(
                dashboard_config(longOnly="false")
            )

    def test_custom_universe_is_validated_and_scopes_the_pipeline(self):
        selected = ["AAPL", "RY.TO", "AZN.L"]
        config = server.validate_config(
            dashboard_config(universe="custom", selectedTickers=selected)
        )
        self.assertEqual(config["universe"], "custom")
        self.assertEqual(config["selectedTickers"], selected)
        environment = runner.configuration_environment(config)
        self.assertEqual(json.loads(environment["ALLOLABS_ASSET_UNIVERSE_TICKERS"]), selected)
        self.assertEqual(json.loads(environment["ALLOLABS_RESEARCH_TICKERS"]), selected)

        with self.assertRaisesRegex(ValueError, "at least two"):
            server.validate_config(
                dashboard_config(universe="custom", selectedTickers=["AAPL"])
            )
        with self.assertRaisesRegex(ValueError, "unsupported tickers"):
            server.validate_config(
                dashboard_config(universe="custom", selectedTickers=["AAPL", "FAKE"])
            )

    def test_universe_catalog_covers_every_pipeline_asset_once(self):
        grouped = [
            ticker
            for group in server.UNIVERSE_CATALOG["groups"]
            for ticker in group["tickers"]
        ]
        # The dashboard catalog is the working universe; the pipeline's
        # built-in ASSET_UNIVERSE fallback must remain selectable within it.
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertTrue(set(load_asset_universe()).issubset(set(grouped)))

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
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function_names = {
            "extract_anthropic_response_text",
            "extract_deepseek_response_text",
            "extract_gemini_response_text",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in function_names
        ]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "allolabs.py", "exec"), namespace)
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
        self.assertEqual(
            namespace["extract_deepseek_response_text"]({
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"views":[]}'},
                }],
            }),
            '{"views":[]}',
        )

    def test_deepseek_is_wired_across_pipeline_server_and_frontend(self):
        config = server.validate_config(dashboard_config(
            gptViews=True,
            researchProvider="deepseek",
            researchModel="deepseek-chat",
            auditViews=True,
            auditProvider="deepseek",
            auditModel="deepseek-reasoner",
        ))
        environment = runner.configuration_environment(config)
        self.assertEqual(environment["ALLOLABS_RESEARCH_PROVIDER"], "deepseek")
        self.assertEqual(environment["ALLOLABS_RESEARCH_MODEL"], "deepseek-chat")
        self.assertEqual(environment["ALLOLABS_AUDIT_PROVIDER"], "deepseek")
        self.assertEqual(environment["ALLOLABS_GPT_AUDIT_MODEL"], "deepseek-reasoner")
        self.assertEqual(server.AI_PROVIDER_KEYS["deepseek"][1], "DEEPSEEK_API_KEY")

        pipeline = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('url = "https://api.deepseek.com/chat/completions"', pipeline)
        self.assertIn('"response_format": {"type": "json_object"}', pipeline)
        self.assertGreaterEqual(markup.count('<option value="deepseek">DeepSeek</option>'), 3)
        self.assertIn('deepseek: [', script)
        self.assertIn('deepseek:    "deepseek-chat"', script)
        self.assertIn('["OpenAI", "Anthropic", "Google", "DeepSeek"]', script)

    def test_deepseek_pipeline_builds_json_mode_chat_requests(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"build_views_schema", "extract_deepseek_response_text", "ai_views_request"}
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted
        ]
        namespace = {
            "json": json,
            "time": __import__("time"),
            "urllib": urllib,
            "AI_API_KEY_ENV": {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
            },
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "allolabs.py", "exec"), namespace)
        provider_response = io.BytesIO(json.dumps({
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"views":[]}'},
            }],
        }).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=provider_response) as urlopen:
            result = namespace["ai_views_request"](
                "Return JSON matching the supplied schema.",
                "secret",
                ["AAPL"],
                provider="deepseek",
                model="deepseek-chat",
                max_tokens=9000,
                attempts=1,
            )
        self.assertEqual(result, '{"views":[]}')
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["max_tokens"], 8192)
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_ai_seed_prompts_are_bounded_and_injected(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        self.assertIn("ALLOLABS_ANALYST_SEED_PROMPT", source)
        self.assertIn("ALLOLABS_AUDITOR_SEED_PROMPT", source)
        self.assertIn("INVESTMENT MANDATE", source)
        self.assertIn("INVESTMENT MANDATE — THESIS ALIGNMENT AUDIT", source)
        self.assertIn("This mandate is investment policy, not an optional hint.", source)
        self.assertIn("Do not flatten mandate-consistent differentiation", source)

    def test_regularization_penalties_are_zero_at_target(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "regularization_penalty"
        )
        namespace = {"np": np}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "allolabs.py", "exec"), namespace)
        target = np.array([0.5, 0.5])
        concentrated = np.array([0.9, 0.1])
        penalty = namespace["regularization_penalty"]
        self.assertEqual(penalty(target, target, "l2", 1.0), 0.0)
        self.assertGreater(penalty(concentrated, target, "l2", 1.0), 0.0)
        self.assertGreater(penalty(concentrated, target, "smooth_l1", 1.0), 0.0)

    def test_optimizer_covariance_and_gradients_are_numerically_stable(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
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
        exec(compile(ast.Module(body=functions, type_ignores=[]), "allolabs.py", "exec"), namespace)

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
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
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
        exec(compile(ast.Module(body=[function], type_ignores=[]), "allolabs.py", "exec"), namespace)
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
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "compare_audited_views"
        )
        namespace = {"re": re}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "allolabs.py", "exec"), namespace)
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
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "build_audit_calibration_context",
                "build_global_audit_prompt",
            }
        ]
        namespace = {"json": json}
        exec(
            compile(ast.Module(body=functions, type_ignores=[]), "allolabs.py", "exec"),
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
        self.assertIn("GLOBAL CALIBRATION CONTEXT", prompt)
        self.assertIn('"universe_count":1', prompt)
        self.assertIn('"ticker":"AAA"', prompt)

    def test_global_audit_batches_large_universes_and_retries_empty_output(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "audit_gpt_views"
        )
        tickers = [f"T{index:03d}" for index in range(678)]
        originals = {
            ticker: {
                "ticker": ticker,
                "industry": "Software",
                "view": f"Original rationale for {ticker}.",
                "expected_return": 0.05,
                "confidence": 0.65,
            }
            for ticker in tickers
        }
        calls = []

        def validate_batch(payload, expected_tickers):
            views = payload.get("views") if isinstance(payload, dict) else None
            views = views if isinstance(views, list) else []
            found = [view.get("ticker") for view in views if isinstance(view, dict)]
            if found != list(expected_tickers):
                missing = sorted(set(expected_tickers) - set(found))
                raise ValueError(f"Incomplete view batch; missing={missing}, duplicates=none.")
            return views

        def request_stub(prompt, api_key, batch_tickers, **kwargs):
            calls.append({"tickers": list(batch_tickers), "prompt": prompt, **kwargs})
            if len(calls) == 1:
                return '{"views":[]}'
            return json.dumps({"views": [originals[ticker] for ticker in batch_tickers]})

        summary = {
            "inputCount": len(tickers),
            "adjustedCount": 0,
            "meanRationaleWords": 4,
            "minRationaleWords": 4,
            "maxRationaleWords": 4,
        }
        namespace = {
            "AI_API_KEY_ENV": {"openai": "OPENAI_API_KEY"},
            "ai_views_request": request_stub,
            "auditor_seed_prompt": "",
            "build_audit_calibration_context": lambda views: {"universe_count": len(views)},
            "build_global_audit_prompt": lambda views, seed, **kwargs: "audit prompt",
            "compare_audited_views": lambda original, audited: summary,
            "np": np,
            "parse_json_from_text": json.loads,
            "print": lambda *args, **kwargs: None,
            "validate_view_batch": validate_batch,
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "allolabs.py", "exec"),
            namespace,
        )
        audited, result_summary = namespace["audit_gpt_views"](
            list(originals.values()),
            tickers,
            "test-key",
            batch_size=40,
        )
        self.assertEqual([view["ticker"] for view in audited], tickers)
        self.assertEqual(result_summary, summary)
        self.assertEqual([len(call["tickers"]) for call in calls], [40] * 17 + [38])
        self.assertIn("RETRY CORRECTION", calls[1]["prompt"])
        self.assertEqual(calls[-1]["schema_name"], "allolabs_global_view_audit_17")

        for invalid_batch_size in (True, 40.5, float("inf"), "forty"):
            with self.subTest(batch_size=invalid_batch_size):
                with self.assertRaisesRegex(ValueError, "whole number"):
                    namespace["audit_gpt_views"](
                        list(originals.values()),
                        tickers,
                        "test-key",
                        batch_size=invalid_batch_size,
                    )

    def test_view_schema_can_describe_audit_rationale_quality(self):
        source = (REPOSITORY_ROOT / "allolabs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_views_schema"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), "allolabs.py", "exec"),
            namespace,
        )
        schema = namespace["build_views_schema"](
            ["AAA"],
            view_description="Detailed audit rationale.",
        )
        view_schema = schema["properties"]["views"]["items"]["properties"]["view"]
        self.assertEqual(view_schema["description"], "Detailed audit rationale.")
        self.assertEqual(schema["properties"]["views"]["minItems"], 1)
        self.assertEqual(schema["properties"]["views"]["maxItems"], 1)

    def test_default_model_path_is_repository_local(self):
        self.assertEqual(server.DEFAULT_SCRIPT, REPOSITORY_ROOT / "allolabs.py")

    def test_desktop_infrastructure_is_packaged_and_uses_writable_data_dir(self):
        desktop_source = (REPOSITORY_ROOT / "desktop" / "app.py").read_text(encoding="utf-8")
        worker_source = (REPOSITORY_ROOT / "desktop" / "worker.py").read_text(encoding="utf-8")
        packaging_source = (REPOSITORY_ROOT / "packaging" / "allolabs.spec").read_text(encoding="utf-8")
        server_source = (REPOSITORY_ROOT / "dashboard" / "server.py").read_text(encoding="utf-8")
        runner_source = (REPOSITORY_ROOT / "dashboard" / "runner.py").read_text(encoding="utf-8")
        browser_source = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")

        self.assertTrue((REPOSITORY_ROOT / "packaging" / "allolabs.spec").is_file())
        self.assertTrue((REPOSITORY_ROOT / "packaging" / "allolabs.iss").is_file())
        self.assertTrue((REPOSITORY_ROOT / "scripts" / "build-desktop.ps1").is_file())
        self.assertIn("root = Path(SPECPATH).parent", packaging_source)
        self.assertNotIn("Path(SPECPATH).parent.parent", packaging_source)
        self.assertIn('name="AlloLabsWorker"', packaging_source)
        self.assertIn("console=True", packaging_source)
        self.assertIn("RunnerServer((\"127.0.0.1\", 0)", desktop_source)
        self.assertIn("def bundled_worker_path", desktop_source)
        self.assertIn('"AlloLabsWorker.exe" if os.name == "nt" else "AlloLabsWorker"', desktop_source)
        self.assertIn('arguments[0] == "--run"', worker_source)
        self.assertIn("worker_executable", server_source)
        self.assertIn("ALLOLABS_DATA_DIR", server_source)
        self.assertIn('namespace.get("DATA_DIR"', runner_source)
        self.assertIn('desktopParameters.get("desktopToken")', browser_source)
        self.assertTrue((REPOSITORY_ROOT / "scripts" / "build-portable.sh").is_file())
        self.assertTrue((REPOSITORY_ROOT / "scripts" / "verify-portable.py").is_file())
        self.assertTrue((REPOSITORY_ROOT / "requirements-desktop-macos.txt").is_file())
        self.assertTrue((REPOSITORY_ROOT / "requirements-desktop-linux.txt").is_file())
        self.assertTrue(
            (REPOSITORY_ROOT / ".github" / "workflows" / "portable-unix-release.yml").is_file()
        )

    def test_explicit_data_directory_is_created_and_resolved(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "generated"
            with patch.dict(os.environ, {"ALLOLABS_DATA_DIR": str(target)}):
                self.assertEqual(allolabs_paths.user_data_dir(), target.resolve())
                self.assertTrue(target.is_dir())

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
        self.assertIn('id="remote-analyst-seed"', markup)
        self.assertIn('id="remote-auditor-seed"', markup)
        self.assertNotIn('id="remote-long-only" type="checkbox" checked disabled', markup)
        self.assertIn('id="universe-view"', markup)
        self.assertIn('id="universe-groups"', markup)
        self.assertIn('data-shortcut-view="universe"', markup)
        self.assertNotIn('id="remote-universe"', markup)
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
        self.assertIn("analystSeedPrompt", script)
        self.assertIn("auditorSeedPrompt", script)
        self.assertIn("selectedTickers: orderedUniverseSelection()", script)
        self.assertIn("loadUniverseCatalog", script)
        self.assertIn("Sending .* request for tickers", script)
        self.assertIn("Global AI audit complete", script)
        self.assertIn("finishRunProgress", script)

    def test_guide_mode_toggle_dock_and_highlight_infrastructure(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        stylesheet = (REPOSITORY_ROOT / "dashboard" / "terminal-theme.css").read_text(encoding="utf-8")

        self.assertIn('id="guide-mode-toggle"', markup)
        self.assertIn('id="tape-mode"', markup)
        self.assertIn('id="guide-inline-anchor"', markup)
        self.assertIn('id="allo-dock"', markup)
        self.assertIn('id="allo-dock-header"', markup)
        self.assertIn('id="allo-dock-body"', markup)
        self.assertIn("const GUIDE_MODE_KEY", script)
        self.assertIn("function setGuideMode", script)
        self.assertIn("function alloDockMount", script)
        self.assertIn("function alloDockRestore", script)
        self.assertIn("function alloApplyHighlights", script)
        self.assertIn("guideMode: guideModeEnabled", script)
        self.assertIn('guideModeEnabled && viewName !== "guide"', script)
        self.assertIn('data-view="${entry.view}"', script)
        self.assertIn(".guide-mode-toggle", stylesheet)
        self.assertIn(".allo-dock", stylesheet)
        self.assertIn(".allo-glow", stylesheet)
        self.assertIn("@keyframes allo-glow-pulse", stylesheet)

    def test_project_logo_is_used_by_dashboard_assets(self):
        markup = (REPOSITORY_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        stylesheet = (REPOSITORY_ROOT / "dashboard" / "terminal-theme.css").read_text(encoding="utf-8")
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        logo = REPOSITORY_ROOT / "resources" / "allolabs-logo.png"
        self.assertTrue(logo.is_file())
        self.assertGreater(logo.stat().st_size, 1000)
        self.assertIn('class="splash-logo"', markup)
        self.assertIn('id="brand-logo"', markup)
        self.assertNotIn('<span class="brand-mark">WG</span>', markup)
        self.assertIn(".brand-logo-svg", stylesheet)
        self.assertGreaterEqual(server.API_VERSION, 13)
        self.assertNotIn('src="resources/allolabs-logo.png"', readme)
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
            "OPENAI_API_KEY": "openai-test-secret-1234",
            "ANTHROPIC_API_KEY": "",
            "GEMINI_API_KEY": "short",
            "DEEPSEEK_API_KEY": "deepseek-test-secret-9876",
        }
        with patch.dict(os.environ, keys, clear=False):
            status = server.provider_key_status()
        encoded = json.dumps(status)
        self.assertTrue(status["openai"]["active"])
        self.assertEqual(status["openai"]["preview"], "openai-********1234")
        self.assertEqual(status["openai"]["source"], "Dashboard process")
        self.assertFalse(status["anthropic"]["active"])
        self.assertIsNone(status["anthropic"]["preview"])
        self.assertEqual(status["gemini"]["preview"], "********")
        self.assertTrue(status["deepseek"]["active"])
        self.assertEqual(status["deepseek"]["preview"], "deepsee********9876")
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
        company_source = (REPOSITORY_ROOT / "allolabs_company.py").read_text(encoding="utf-8")
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
        self.assertIn('id="report-view"', markup)
        self.assertIn('id="model-guide"', markup)
        self.assertIn('data-shortcut-view="reference"', markup)
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
            "BA.L", "RR.L",
            "ALV.DE", "SU.PA", "TTE.PA", "IBE.MC", "ITX.MC",
            "BHP", "NVO", "SONY", "TM", "TSM",
        }
        self.assertTrue(expected.issubset(universe))


class GuideTests(unittest.TestCase):
    def test_catalog_tools_inject_only_when_relevant(self):
        self.assertTrue(allolabs_guide.needs_catalog_context(
            "Build me a Canadian energy stock universe"
        ))
        self.assertFalse(allolabs_guide.needs_catalog_context(
            "Explain the Black-Litterman posterior formula"
        ))

        catalog = allolabs_guide.format_catalog_block([
            {"label": "Canada", "tickers": ["RY.TO", "CNQ.TO"]},
        ])
        self.assertIn("FULL AVAILABLE TICKER CATALOG", catalog)
        self.assertIn("RY.TO CNQ.TO", catalog)
        messages = [{"role": "user", "content": "Suggest Canadian energy stocks"}]
        injected = allolabs_guide.inject_app_context(
            messages,
            {"selectedTickers": ["RY.TO"], "runStatus": "idle"},
            catalog,
        )
        self.assertEqual(injected[-1], messages[0])
        self.assertIn("[APP STATE SNAPSHOT]", injected[0]["content"])
        self.assertIn("FULL AVAILABLE TICKER CATALOG", injected[0]["content"])

    def test_guide_response_parser_repairs_common_open_model_json(self):
        raw = (
            "Ready to load.\n"
            "<<<ALLO_META>>>\n"
            '{"mode":"run_config","runConfig":{"long_only":True,},}\n'
            "<<<END_META>>>\nTrailing courtesy text"
        )
        reply, mode, config = allolabs_guide.parse_guide_response(raw)
        self.assertEqual(reply, "Ready to load.")
        self.assertEqual(mode, "run_config")
        self.assertEqual(config, {"long_only": True})

    def test_guide_response_parser_extracts_highlights(self):
        raw = (
            "Click the Console tab.\n"
            "<<<ALLO_META>>>"
            '{"mode":"normal","runConfig":null,"highlights":["tab-console","run-button"]}'
            "<<<END_META>>>"
        )
        parsed = allolabs_guide.parse_guide_response_full(raw)
        self.assertEqual(parsed["text"], "Click the Console tab.")
        self.assertEqual(parsed["mode"], "normal")
        self.assertIsNone(parsed["runConfig"])
        self.assertEqual(parsed["highlights"], ["tab-console", "run-button"])
        # The legacy tuple wrapper stays intact for existing callers.
        reply, mode, config = allolabs_guide.parse_guide_response(raw)
        self.assertEqual(
            (reply, mode, config), ("Click the Console tab.", "normal", None)
        )
        # Malformed highlight payloads degrade to an empty list.
        no_highlights = allolabs_guide.parse_guide_response_full(
            '<<<ALLO_META>>>{"mode":"normal","highlights":"tab-console"}<<<END_META>>>'
        )
        self.assertEqual(no_highlights["highlights"], [])

    def test_guide_highlight_catalog_matches_frontend_registry(self):
        prompt = allolabs_guide.ALLO_SYSTEM_PROMPT
        script = (REPOSITORY_ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
        registry_keys = set(
            re.findall(r'^\s*"([a-z][a-z0-9\-]+)":\s*\{ selector:', script, re.MULTILINE)
        )
        self.assertGreaterEqual(len(registry_keys), 20)
        for key in registry_keys:
            self.assertIn(key, prompt, f"highlight key {key} missing from prompt catalog")

    def test_deepseek_guide_request_and_provider_selection(self):
        response = json.dumps({
            "choices": [{"message": {"content": "DeepSeek reply"}}],
        }).encode("utf-8")
        with patch.object(allolabs_guide, "_http_call", return_value=response) as http_call:
            reply = allolabs_guide._call_deepseek(
                "secret", "system", [{"role": "user", "content": "hello"}],
                "deepseek-chat",
            )
        self.assertEqual(reply, "DeepSeek reply")
        request = http_call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "system"})
        self.assertFalse(payload["stream"])

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret"}, clear=True), patch.object(
            allolabs_guide, "_call_deepseek", return_value="selected"
        ) as deepseek_call:
            self.assertEqual(
                allolabs_guide.call_guide_ai(
                    "system", [{"role": "user", "content": "hello"}],
                    provider="deepseek",
                ),
                "selected",
            )
        self.assertEqual(deepseek_call.call_args.args[3], "deepseek-chat")
        with self.assertRaisesRegex(ValueError, "Unknown guide provider"):
            allolabs_guide.call_guide_ai("system", [], provider="invalid")

    def test_authenticated_guide_endpoints_wire_catalog_and_compaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = server.RunState(
                REPOSITORY_ROOT / "allolabs.py",
                data_dir=Path(temp_dir),
            )
            app = server.RunnerServer(("127.0.0.1", 0), state, "test-token")
            thread = threading.Thread(target=app.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{app.server_address[1]}"

            def post(path: str, payload: dict) -> dict:
                request = urllib.request.Request(
                    base_url + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": "Bearer test-token",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    return json.load(response)

            try:
                raw_reply = (
                    "Use a broad Canadian energy basket.\n"
                    "<<<ALLO_META>>>"
                    '{"mode":"normal","runConfig":null,"highlights":["tab-universe"]}'
                    "<<<END_META>>>"
                )
                with patch.object(server, "call_guide_ai", return_value=raw_reply) as guide_call:
                    result = post("/api/guide", {
                        "provider": "deepseek",
                        "guideModel": "deepseek-chat",
                        "messages": [{
                            "role": "user",
                            "content": "Suggest Canadian energy stocks",
                        }],
                        "appContext": {"selectedTickers": ["CNQ.TO"]},
                    })
                self.assertEqual(result["reply"], "Use a broad Canadian energy basket.")
                self.assertEqual(result["mode"], "normal")
                self.assertEqual(result["highlights"], ["tab-universe"])
                llm_messages = guide_call.call_args.args[1]
                self.assertIn("FULL AVAILABLE TICKER CATALOG", llm_messages[0]["content"])
                self.assertEqual(guide_call.call_args.kwargs["provider"], "deepseek")
                self.assertEqual(guide_call.call_args.kwargs["guide_model"], "deepseek-chat")

                with patch.object(server, "call_guide_ai", return_value="compact summary") as compact_call:
                    compact = post("/api/guide-compact", {
                        "messages": [{"role": "user", "content": "First decision"}],
                    })
                self.assertEqual(compact, {"summary": "compact summary"})
                self.assertEqual(
                    compact_call.call_args.args[1][-1]["content"],
                    "Please produce a compact session summary now.",
                )

                unauthorized = urllib.request.Request(
                    base_url + "/api/guide",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(unauthorized, timeout=5)
                self.assertEqual(caught.exception.code, 401)
            finally:
                app.shutdown()
                app.server_close()
                thread.join(timeout=5)


class MetadataTests(unittest.TestCase):
    def test_catalog_metadata_covers_supported_universe(self):
        metadata_path = REPOSITORY_ROOT / "dashboard" / "catalog_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(set(metadata), set(server.SUPPORTED_TICKERS))
        self.assertGreaterEqual(sum(bool(item.get("name")) for item in metadata.values()), 650)
        for ticker, item in metadata.items():
            self.assertIsInstance(item, dict, ticker)
            self.assertEqual(
                set(item), {"name", "sector", "industry", "country", "cap"}, ticker
            )
            self.assertIn(item["cap"], {"", "small", "mid", "large", "mega"}, ticker)

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

    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_sector_resolution_uses_research_before_yahoo(self):
        with tempfile.TemporaryDirectory() as folder:
            cache_path = Path(folder) / "sector_cache.json"
            sectors = allolabs_report.resolve_sectors(
                ["TEST"],
                np.array([1.0]),
                np.array([1.0]),
                {"TEST": {"industry": "Semiconductor Equipment"}},
                cache_path,
            )
            self.assertEqual(sectors["TEST"], "Information Technology")


class ReportTests(unittest.TestCase):
    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_optional_research_percentages_render_safely(self):
        self.assertEqual(allolabs_report._format_optional_percent(None), "N/A")
        self.assertEqual(allolabs_report._format_optional_percent(float("nan")), "N/A")
        self.assertEqual(allolabs_report._format_optional_percent("invalid"), "N/A")
        self.assertEqual(allolabs_report._format_optional_percent(0.1234), "12.3%")

    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_report_flags_extreme_returns_as_unstable_inputs(self):
        frame = allolabs_report.pd.DataFrame(
            {
                "weight": [0.6, 0.4],
                "historical_return": [0.70, 0.45],
                "prior_return": [0.10, 0.08],
                "expected_return": [0.18, 0.12],
                "posterior_return": [0.50, 0.50],
                "confidence": [0.75, 0.65],
            }
        )
        diagnostics = allolabs_report._return_diagnostics(
            frame,
            {"return": 0.50, "volatility": 0.14},
        )
        self.assertTrue(diagnostics["extreme"])
        self.assertEqual(
            allolabs_report._diagnostic_label(diagnostics),
            "HIGH / UNSTABLE INPUT",
        )
        self.assertEqual(diagnostics["mode"], "black_litterman")

        historical_only = frame.assign(
            historical_return=[None, None],
            prior_return=[None, None],
            expected_return=[None, None],
        )
        historical_only["posterior_return"] = None
        historical_diagnostics = allolabs_report._return_diagnostics(
            historical_only,
            {"return": 0.32, "volatility": 0.18},
        )
        self.assertEqual(historical_diagnostics["mode"], "historical")
        self.assertEqual(historical_diagnostics["historical"], 0.32)

    def test_report_language_distinguishes_inputs_from_forecasts(self):
        source = (REPOSITORY_ROOT / "allolabs_report.py").read_text(encoding="utf-8")
        self.assertIn("Return Input Bridge", source)
        self.assertIn("Historical is descriptive, not predictive.", source)
        self.assertIn("MODEL INPUT - NOT FORECAST", source)
        self.assertIn("The posterior is an optimization input.", source)
        self.assertIn("WHY LARGE NUMBERS APPEAR", source)
        self.assertNotIn('"Expected return", f"{metrics', source)

    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_allocation_appendix_uses_threshold_and_multiple_pages(self):
        included_rows = 57
        excluded_rows = 20
        frame = allolabs_report.pd.DataFrame(
            {
                "ticker": [f"T{i:03d}" for i in range(included_rows + excluded_rows)],
                "sector": ["Industrials"] * (included_rows + excluded_rows),
                "weight": (
                    [0.00005] * included_rows
                    + [0.000049] * excluded_rows
                ),
            }
        )

        class PdfRecorder:
            def __init__(self):
                self.pages = 0

            def savefig(self, *_args, **_kwargs):
                self.pages += 1

        pdf = PdfRecorder()
        page_count = allolabs_report._allocation_appendix(pdf, frame, frame, 8)

        self.assertEqual(allolabs_report.ALLOCATION_APPENDIX_MIN_WEIGHT, 0.00005)
        self.assertEqual(allolabs_report.ALLOCATION_APPENDIX_ROWS_PER_PAGE, 28)
        self.assertEqual(page_count, 3)
        self.assertEqual(pdf.pages, 3)

    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_report_company_logo_lookup_is_local_and_rejects_unsafe_tickers(self):
        logo_path = allolabs_report._company_logo_path("AAPL")
        self.assertEqual(
            logo_path,
            REPOSITORY_ROOT / "resources" / "company-logos" / "AAPL.png",
        )
        self.assertTrue(logo_path.is_file())
        self.assertIsNone(allolabs_report._company_logo_path("../AAPL"))
        self.assertIsNone(allolabs_report._company_logo_path("NOT-A-REAL-TICKER-123"))
        report_source = (REPOSITORY_ROOT / "allolabs_report.py").read_text(encoding="utf-8")
        self.assertIn("fig.get_figwidth() / fig.get_figheight()", report_source)
        self.assertIn("logo.set_clip_path(clip)", report_source)

    @unittest.skipIf(allolabs_report is None, "Scientific reporting dependencies are unavailable.")
    def test_report_builds_without_research_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            output_path = Path(folder) / "report.pdf"
            missing_analysis = Path(folder) / "missing.json"
            allolabs_report.create_portfolio_pdf(
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

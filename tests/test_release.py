from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from dashboard import runner, server

try:
    import wealthgpt_report
except ModuleNotFoundError:
    wealthgpt_report = None


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_dashboard_config_maps_to_environment(self):
        environment = runner.configuration_environment(
            {
                "trainingYears": 2.5,
                "oosMonths": 12,
                "maxPositionPercent": 15,
                "universe": "canada",
                "gptViews": True,
                "refreshCache": False,
            }
        )
        self.assertEqual(environment["WEALTHGPT_TRAINING_YEARS"], "2.5")
        self.assertEqual(environment["WEALTHGPT_OOS_YEARS"], "1.0")
        self.assertEqual(environment["WEALTHGPT_MAX_POSITION_WEIGHT"], "0.15")
        self.assertEqual(environment["WEALTHGPT_GPT_VIEWS"], "1")
        self.assertIn("RY.TO", json.loads(environment["WEALTHGPT_RESEARCH_TICKERS"]))

    def test_server_rejects_coerced_boolean_values(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            server.validate_config(
                {
                    "trainingYears": 1,
                    "oosMonths": 6,
                    "maxPositionPercent": 20,
                    "universe": "curated",
                    "gptViews": "false",
                    "refreshCache": False,
                }
            )

    def test_server_rejects_fractional_whole_number_fields(self):
        with self.assertRaisesRegex(ValueError, "whole numbers"):
            server.validate_config(
                {
                    "trainingYears": 1,
                    "oosMonths": 6.5,
                    "maxPositionPercent": 20,
                    "universe": "curated",
                    "gptViews": False,
                    "refreshCache": False,
                }
            )

    def test_default_model_path_is_repository_local(self):
        self.assertEqual(server.DEFAULT_SCRIPT, REPOSITORY_ROOT / "wealthgpt.py")

    def test_bundled_dashboard_snapshot_is_available(self):
        payload = json.loads(server.DEFAULT_RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(payload["dataMode"], "example")
        self.assertTrue(payload["portfolios"]["max"]["holdings"])
        self.assertTrue(payload["portfolios"]["min"]["holdings"])
        self.assertGreater(len(payload["research"]), 100)
        self.assertTrue(server.DEFAULT_PDF.is_file())
        self.assertTrue(server.DEFAULT_CHART.is_file())


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

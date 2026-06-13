"""Small authenticated HTTP service for running WealthGPT from the dashboard."""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parent
RESOURCES_DIR = ROOT.parent / "resources"
COMPANY_LOGOS_DIR = RESOURCES_DIR / "company-logos"
RUNNER = ROOT / "runner.py"
COMPANY_DETAILS_HELPER = ROOT / "company_details.py"
DEFAULT_SCRIPT = ROOT.parent / "wealthgpt.py"
EXAMPLES_DIR = ROOT.parent / "examples"
DEFAULT_RESULTS = EXAMPLES_DIR / "default-run.json"
DEFAULT_PDF = EXAMPLES_DIR / "default-portfolio-report.pdf"
DEFAULT_CHART = EXAMPLES_DIR / "default-performance.png"
ALLOWED_UNIVERSES = {"curated", "canada", "full"}
ALLOWED_REGULARIZATIONS = {"none", "l2", "smooth_l1"}
AI_PROVIDER_MODELS = {
    "openai": {"gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"},
    "anthropic": {
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    },
    "gemini": {
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    },
}
AI_PROVIDER_KEYS = {
    "openai": ("OpenAI", "OPENAI_API_KEY"),
    "anthropic": ("Anthropic", "ANTHROPIC_API_KEY"),
    "gemini": ("Google Gemini", "GEMINI_API_KEY"),
}
ALLOWED_AI_MODELS = {
    stage: {
        provider: set(models)
        for provider, models in AI_PROVIDER_MODELS.items()
    }
    for stage in ("research", "audit")
}
API_VERSION = 16
REQUIRED_ANALYSIS_MODULES = ("matplotlib", "numpy", "pandas", "scipy", "yfinance")
COMPANY_DETAILS_CACHE_SECONDS = 15 * 60
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")


def masked_api_key(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 12:
        return "********"
    return f"{cleaned[:7]}********{cleaned[-4:]}"


def windows_environment_value(name: str) -> tuple[str, str] | tuple[None, None]:
    if os.name != "nt":
        return None, None
    try:
        import winreg
    except ImportError:
        return None, None

    locations = (
        ("Windows user environment", winreg.HKEY_CURRENT_USER, "Environment"),
        (
            "Windows machine environment",
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for source, hive, path in locations:
        try:
            with winreg.OpenKey(hive, path) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except (FileNotFoundError, OSError):
            continue
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned, source
    return None, None


def resolved_api_key(name: str) -> tuple[str, str] | tuple[None, None]:
    process_value = os.getenv(name, "").strip()
    if process_value:
        return process_value, "Dashboard process"
    return windows_environment_value(name)


def provider_key_status() -> dict:
    status = {}
    for provider, (label, environment_name) in AI_PROVIDER_KEYS.items():
        value, source = resolved_api_key(environment_name)
        status[provider] = {
            "label": label,
            "environment": environment_name,
            "active": bool(value),
            "preview": masked_api_key(value) if value else None,
            "source": source,
        }
    return status


def result_company_tickers(results: dict) -> set[str]:
    tickers = set()
    for portfolio in (results.get("portfolios") or {}).values():
        if not isinstance(portfolio, dict):
            continue
        for holding in portfolio.get("holdings") or []:
            if isinstance(holding, dict) and holding.get("ticker"):
                tickers.add(str(holding["ticker"]).strip().upper())
    for research in results.get("research") or []:
        if isinstance(research, dict) and research.get("ticker"):
            tickers.add(str(research["ticker"]).strip().upper())
    return tickers


def result_portfolio_tickers(results: dict) -> set[str]:
    """Backward-compatible alias for callers using the earlier helper name."""
    return result_company_tickers(results)


class RunState:
    def __init__(
        self,
        script_path: Path,
        analysis_python: Path | None = None,
        analysis_python_version: str | None = None,
        analysis_error: str | None = None,
    ) -> None:
        self.script_path = script_path
        self.analysis_python = analysis_python
        self.analysis_python_version = analysis_python_version
        self.analysis_error = analysis_error
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.status = "idle"
        self.run_id: str | None = None
        self.exit_code: int | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.config: dict | None = None
        self.next_line_id = 1
        self.logs: deque[dict] = deque(maxlen=10000)

    def add_log(self, text: str, stream: str = "stdout") -> None:
        with self.lock:
            self.logs.append({"id": self.next_line_id, "text": text.rstrip("\r\n"), "stream": stream})
            self.next_line_id += 1

    def snapshot(self) -> dict:
        with self.lock:
            live_results_available = (self.script_path.parent / "latest_run.json").is_file()
            default_results_available = DEFAULT_RESULTS.is_file()
            return {
                "api_version": API_VERSION,
                "status": self.status,
                "run_id": self.run_id,
                "exit_code": self.exit_code,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "script": self.script_path.name,
                "config": self.config,
                "results_available": live_results_available or default_results_available,
                "results_source": "live" if live_results_available else (
                    "example" if default_results_available else None
                ),
                "live_results_available": live_results_available,
                "default_results_available": default_results_available,
                "analysis_environment": {
                    "ready": self.analysis_python is not None,
                    "python": str(self.analysis_python) if self.analysis_python else None,
                    "version": self.analysis_python_version,
                    "error": self.analysis_error,
                    "required_modules": list(REQUIRED_ANALYSIS_MODULES),
                },
                "provider_keys": provider_key_status(),
                "capabilities": {
                    "results": True,
                    "artifacts": True,
                    "pdf_viewer": True,
                    "chart_viewer": True,
                    "company_details": True,
                    "research_company_details": True,
                    "provider_key_status": True,
                },
            }


def probe_analysis_python(candidate: Path) -> tuple[bool, str]:
    try:
        is_file = candidate.is_file()
    except OSError as exc:
        return False, f"cannot inspect executable: {exc}"
    if not is_file:
        return False, "executable not found"
    imports = "; ".join(f"import {module}" for module in REQUIRED_ANALYSIS_MODULES)
    command = [
        str(candidate),
        "-c",
        f"import sys; {imports}; print(sys.version.split()[0])",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return False, detail[-1] if detail else f"probe exited {result.returncode}"
    return True, result.stdout.strip() or "unknown"


def discover_analysis_python(explicit: Path | None = None) -> tuple[Path | None, str | None, str | None]:
    candidates: list[Path] = []
    environment_path = os.getenv("WEALTHGPT_ANALYSIS_PYTHON")
    if explicit:
        candidates.append(explicit.expanduser())
    if environment_path:
        candidates.append(Path(environment_path).expanduser())
    candidates.append(Path(sys.executable))
    for command in ("python", "python3"):
        executable = shutil.which(command)
        if executable:
            candidates.append(Path(executable))

    seen: set[str] = set()
    failures: list[str] = []
    for candidate in candidates:
        try:
            normalized_path = candidate.resolve() if candidate.exists() else candidate
        except OSError:
            normalized_path = candidate
        normalized = str(normalized_path).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        ready, detail = probe_analysis_python(candidate)
        if ready:
            try:
                resolved_candidate = candidate.resolve()
            except OSError:
                resolved_candidate = candidate
            return resolved_candidate, detail, None
        failures.append(f"{candidate}: {detail}")

    return None, None, "No compatible Python environment found. " + " | ".join(failures)


def validate_config(payload: dict) -> dict:
    try:
        raw_training_years = payload["trainingYears"]
        raw_oos_months = payload["oosMonths"]
        raw_max_position = payload["maxPositionPercent"]
        long_only = payload["longOnly"]
        raw_max_sector = payload["maxSectorPercent"]
        raw_regularization_strength = payload["regularizationStrength"]
        universe = str(payload["universe"])
        regularization = str(payload["regularization"])
        research_provider = str(payload.get("researchProvider", "openai"))
        research_model = str(payload.get("researchModel", payload.get("gptModel", "")))
        audit_provider = str(payload.get("auditProvider", "openai"))
        audit_model = str(payload["auditModel"])
        gpt_views = payload["gptViews"]
        audit_views = payload["auditViews"]
        refresh_cache = payload["refreshCache"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Run configuration is incomplete or invalid.") from exc

    numeric_values = (
        raw_training_years,
        raw_oos_months,
        raw_max_position,
        raw_max_sector,
        raw_regularization_strength,
    )
    if any(isinstance(value, bool) for value in numeric_values):
        raise ValueError("Numeric run settings cannot be boolean.")
    try:
        training_years = float(raw_training_years)
        oos_months_value = float(raw_oos_months)
        max_position_value = float(raw_max_position)
        max_sector_value = float(raw_max_sector)
        regularization_strength = float(raw_regularization_strength)
    except (TypeError, ValueError) as exc:
        raise ValueError("Run configuration contains a non-numeric setting.") from exc
    if not all(math.isfinite(value) for value in (
        training_years,
        oos_months_value,
        max_position_value,
        max_sector_value,
        regularization_strength,
    )):
        raise ValueError("Numeric run settings must be finite.")
    if not all(value.is_integer() for value in (
        oos_months_value, max_position_value, max_sector_value
    )):
        raise ValueError("OOS months and hard percentage limits must be whole numbers.")
    oos_months = int(oos_months_value)
    max_position = int(max_position_value)
    max_sector = int(max_sector_value)

    if not all(isinstance(value, bool) for value in (
        gpt_views, audit_views, long_only, refresh_cache
    )):
        raise ValueError(
            "AI views, global audit, long-only, and cache refresh settings must be boolean."
        )
    if audit_views and not gpt_views:
        raise ValueError("Global AI audit requires AI-assisted views.")
    if not 0.25 <= training_years <= 10:
        raise ValueError("Training lookback must be between 0.25 and 10 years.")
    if not 0 <= oos_months <= 60:
        raise ValueError("Out-of-sample window must be between 0 and 60 months.")
    if not 1 <= max_position <= 100:
        raise ValueError("Maximum position must be between 1 and 100 percent.")
    if not 5 <= max_sector <= 100:
        raise ValueError("Maximum sector weight must be between 5 and 100 percent.")
    if not 0 <= regularization_strength <= 10:
        raise ValueError("Regularization strength must be between 0 and 10.")
    if universe not in ALLOWED_UNIVERSES:
        raise ValueError("Research universe is not allowlisted.")
    if regularization not in ALLOWED_REGULARIZATIONS:
        raise ValueError("Regularization method is not allowlisted.")
    if research_provider not in ALLOWED_AI_MODELS["research"]:
        raise ValueError("Selected research provider is not allowlisted.")
    if audit_provider not in ALLOWED_AI_MODELS["audit"]:
        raise ValueError("Selected audit provider is not allowlisted.")
    if research_model not in ALLOWED_AI_MODELS["research"][research_provider]:
        raise ValueError("Selected research model is not allowlisted for its provider.")
    if audit_model not in ALLOWED_AI_MODELS["audit"][audit_provider]:
        raise ValueError("Selected audit model is not allowlisted for its provider.")

    return {
        "trainingYears": training_years,
        "oosMonths": oos_months,
        "maxPositionPercent": max_position,
        "longOnly": long_only,
        "maxSectorPercent": max_sector,
        "regularization": regularization,
        "regularizationStrength": (
            regularization_strength if regularization != "none" else 0.0
        ),
        "universe": universe,
        "gptViews": gpt_views,
        "researchProvider": research_provider,
        "researchModel": research_model,
        "auditViews": audit_views,
        "auditProvider": audit_provider,
        "auditModel": audit_model,
        "refreshCache": refresh_cache,
    }


def consume_output(state: RunState, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        state.add_log(line, "stdout")
    exit_code = process.wait()
    with state.lock:
        was_stopping = state.status == "stopping"
        state.exit_code = exit_code
        state.finished_at = time.time()
        state.status = "stopped" if was_stopping else ("completed" if exit_code == 0 else "failed")
        state.process = None
    state.add_log(
        f"[runner] Process {'stopped' if was_stopping else 'finished'} with exit code {exit_code}.",
        "system" if exit_code == 0 or was_stopping else "stderr",
    )


def start_run(state: RunState, config: dict) -> str:
    with state.lock:
        if state.process is not None:
            raise RuntimeError("A WealthGPT run is already active.")
        if not state.script_path.is_file():
            raise FileNotFoundError(f"WealthGPT script not found: {state.script_path}")
        if state.analysis_python is None:
            raise RuntimeError(
                state.analysis_error
                or "No compatible analysis Python is configured. Install the project requirements."
            )

        run_id = secrets.token_hex(4)
        state.status = "running"
        state.run_id = run_id
        state.exit_code = None
        state.started_at = time.time()
        state.finished_at = None
        state.config = config
        state.logs.clear()
        state.next_line_id = 1

        env = os.environ.copy()
        for _, environment_name in AI_PROVIDER_KEYS.values():
            value, _ = resolved_api_key(environment_name)
            if value:
                env[environment_name] = value
        env["PYTHONUTF8"] = "1"
        command = [
            str(state.analysis_python),
            "-u",
            str(RUNNER),
            str(state.script_path),
            json.dumps(config),
        ]
        process = subprocess.Popen(
            command,
            cwd=state.script_path.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        state.process = process

    state.add_log(f"[runner] Run {run_id} launched.", "system")
    threading.Thread(target=consume_output, args=(state, process), daemon=True).start()
    return run_id


class Handler(BaseHTTPRequestHandler):
    server_version = "WealthGPTRunner/1.0"

    def end_headers(self) -> None:
        cors_origin = self.allowed_cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def allowed_cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        server_host = self.app.server_address[0]
        if origin == "null" and server_host in {"127.0.0.1", "localhost", "::1"}:
            return origin
        request_host = self.headers.get("Host", "")
        parsed_origin = urlparse(origin)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.netloc == request_host:
            return origin
        return None

    def origin_allowed(self) -> bool:
        return not self.headers.get("Origin") or self.allowed_cors_origin() is not None

    @property
    def app(self) -> "RunnerServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, path: Path) -> None:
        allowed_directories = {
            ROOT.resolve(),
            RESOURCES_DIR.resolve(),
            COMPANY_LOGOS_DIR.resolve(),
        }
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        if not resolved.is_file() or resolved.parent not in allowed_directories:
            self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        body = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_artifact(self, path: Path, content_type: str) -> None:
        project_dir = self.app.state.script_path.parent.resolve()
        allowed_directories = {project_dir, EXAMPLES_DIR.resolve()}
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            self.send_json({"error": f"Artifact is not available yet: {path.name}"}, HTTPStatus.NOT_FOUND)
            return
        if resolved.parent not in allowed_directories or not resolved.is_file():
            self.send_json({"error": "Artifact path is outside the WealthGPT project."}, HTTPStatus.FORBIDDEN)
            return
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'inline; filename="{resolved.name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def results_path(self) -> tuple[Path | None, str | None]:
        live_path = self.app.state.script_path.parent / "latest_run.json"
        if live_path.is_file():
            return live_path, "live"
        if DEFAULT_RESULTS.is_file():
            return DEFAULT_RESULTS, "example"
        return None, None

    def read_results(self) -> tuple[dict, str]:
        results_path, source = self.results_path()
        if results_path is None or source is None:
            raise FileNotFoundError("No live or bundled dashboard results are available.")
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Dashboard results must be a JSON object.")
        payload["dataMode"] = source
        if source == "example":
            payload.setdefault("snapshotLabel", "Bundled example")
        return payload, source

    def fetch_company_details(self, ticker: str) -> dict:
        now = time.time()
        with self.app.company_cache_lock:
            cached = self.app.company_cache.get(ticker)
            if cached and now - cached[0] < COMPANY_DETAILS_CACHE_SECONDS:
                return cached[1]

        if self.app.state.analysis_python is None:
            raise RuntimeError(
                self.app.state.analysis_error
                or "The analysis Python environment is unavailable."
            )
        command = [
            str(self.app.state.analysis_python),
            str(COMPANY_DETAILS_HELPER),
            ticker,
        ]
        completed = subprocess.run(
            command,
            cwd=self.app.state.script_path.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "Yahoo Finance lookup failed."
            raise RuntimeError(detail)
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict) or payload.get("ticker") != ticker:
            raise ValueError("Company detail helper returned an invalid response.")
        with self.app.company_cache_lock:
            self.app.company_cache[ticker] = (now, payload)
        return payload

    def authorized(self) -> bool:
        if not self.app.token:
            return True
        supplied = self.headers.get("Authorization", "")
        return secrets.compare_digest(supplied, f"Bearer {self.app.token}")

    def require_auth(self) -> bool:
        if self.authorized():
            return True
        self.send_json({"error": "Invalid or missing runner access token."}, HTTPStatus.UNAUTHORIZED)
        return False

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 65536:
            raise ValueError("Request body is missing or too large.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self) -> None:
        if not self.origin_allowed():
            self.send_json({"error": "Browser origin is not allowed."}, HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            if self.require_auth():
                self.send_json(self.app.state.snapshot())
            return
        if parsed.path == "/api/logs":
            if not self.require_auth():
                return
            try:
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
            except ValueError:
                after = 0
            with self.app.state.lock:
                lines = [entry for entry in self.app.state.logs if entry["id"] > after]
            self.send_json({"lines": lines})
            return
        if parsed.path == "/api/results":
            if not self.require_auth():
                return
            try:
                payload, _ = self.read_results()
            except FileNotFoundError:
                self.send_json(
                    {"error": "No completed or bundled dashboard run is available."},
                    HTTPStatus.NOT_FOUND,
                )
                return
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                self.send_json({"error": f"Could not read live results: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_json(payload)
            return
        if parsed.path == "/api/company":
            if not self.require_auth():
                return
            ticker = parse_qs(parsed.query).get("ticker", [""])[0].strip().upper()
            if not TICKER_PATTERN.fullmatch(ticker):
                self.send_json({"error": "A valid portfolio ticker is required."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                results, _ = self.read_results()
                if ticker not in result_company_tickers(results):
                    self.send_json(
                        {"error": "Ticker is not present in the displayed portfolios or AI research."},
                        HTTPStatus.NOT_FOUND,
                    )
                    return
                self.send_json(self.fetch_company_details(ticker))
            except FileNotFoundError:
                self.send_json({"error": "No portfolio results are available."}, HTTPStatus.NOT_FOUND)
            except subprocess.TimeoutExpired:
                self.send_json({"error": "Yahoo Finance lookup timed out."}, HTTPStatus.GATEWAY_TIMEOUT)
            except (json.JSONDecodeError, OSError, RuntimeError, ValueError) as exc:
                self.send_json(
                    {"error": f"Could not load company details: {exc}"},
                    HTTPStatus.BAD_GATEWAY,
                )
            return
        if parsed.path == "/api/artifacts/pdf":
            if not self.require_auth():
                return
            _, source = self.results_path()
            live_pdf = self.app.state.script_path.parent / "wealthgpt_portfolio_report.pdf"
            pdf_path = live_pdf if source == "live" and live_pdf.is_file() else DEFAULT_PDF
            self.send_artifact(pdf_path, "application/pdf")
            return
        if parsed.path == "/api/artifacts/chart":
            if not self.require_auth():
                return
            try:
                results, source = self.read_results()
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
                results = {}
                source = None
            if not results.get("performance"):
                self.send_json({"error": "The latest run did not generate an OOS chart."}, HTTPStatus.NOT_FOUND)
                return
            live_chart = self.app.state.script_path.parent / "portfolio_vs_markets_oos.png"
            chart_path = live_chart if source == "live" and live_chart.is_file() else DEFAULT_CHART
            self.send_artifact(chart_path, "image/png")
            return
        static_files = {
            "/": ROOT / "index.html",
            "/index.html": ROOT / "index.html",
            "/styles.css": ROOT / "styles.css",
            "/terminal-theme.css": ROOT / "terminal-theme.css",
            "/app.js": ROOT / "app.js",
            "/resources/wealthgpt-logo.png": RESOURCES_DIR / "wealthgpt-logo.png",
        }
        if parsed.path in static_files:
            self.send_static(static_files[parsed.path])
            return
        logo_prefix = "/resources/company-logos/"
        if parsed.path.startswith(logo_prefix):
            filename = unquote(parsed.path[len(logo_prefix):])
            if re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}\.png", filename):
                self.send_static(COMPANY_LOGOS_DIR / filename)
            else:
                self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.origin_allowed():
            self.send_json({"error": "Browser origin is not allowed."}, HTTPStatus.FORBIDDEN)
            return
        if not self.require_auth():
            return
        if self.path == "/api/run":
            try:
                config = validate_config(self.read_json())
                run_id = start_run(self.app.state, config)
                self.send_json({"run_id": run_id}, HTTPStatus.ACCEPTED)
            except (ValueError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if self.path == "/api/stop":
            with self.app.state.lock:
                process = self.app.state.process
                if process is None:
                    self.send_json({"error": "No active run."}, HTTPStatus.CONFLICT)
                    return
                self.app.state.status = "stopping"
                process.terminate()
            self.send_json({"status": "stopping"}, HTTPStatus.ACCEPTED)
            return
        self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)


class RunnerServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], state: RunState, token: str | None) -> None:
        super().__init__(address, Handler)
        self.state = state
        self.token = token
        self.company_cache: dict[str, tuple[float, dict]] = {}
        self.company_cache_lock = threading.Lock()

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the constrained WealthGPT browser relay.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument(
        "--analysis-python",
        type=Path,
        default=None,
        help="Python executable used for WealthGPT model runs.",
    )
    parser.add_argument("--token", default=os.getenv("WEALTHGPT_REMOTE_TOKEN"))
    args = parser.parse_args()

    is_local = args.host in {"127.0.0.1", "localhost", "::1"}
    if not is_local and not args.token:
        parser.error("--token or WEALTHGPT_REMOTE_TOKEN is required when binding beyond localhost.")

    analysis_python, analysis_version, analysis_error = discover_analysis_python(args.analysis_python)
    state = RunState(
        args.script.resolve(),
        analysis_python=analysis_python,
        analysis_python_version=analysis_version,
        analysis_error=analysis_error,
    )
    try:
        server = RunnerServer((args.host, args.port), state, args.token)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) in {48, 98, 10048}:
            print(
                f"Port {args.port} is already in use. Run restart-wealthgpt-dashboard.bat "
                "to stop the older dashboard process and start this version.",
                file=sys.stderr,
                flush=True,
            )
            return 2
        raise
    print(f"WealthGPT runner listening on http://{args.host}:{args.port}", flush=True)
    print(f"Script: {state.script_path}", flush=True)
    if state.analysis_python:
        print(
            f"Analysis Python: {state.analysis_python} ({state.analysis_python_version})",
            flush=True,
        )
    else:
        print(f"Analysis Python: NOT READY - {state.analysis_error}", file=sys.stderr, flush=True)
    print(f"Authentication: {'enabled' if args.token else 'disabled (localhost only)'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Small authenticated HTTP service for running AlloLabs from the dashboard."""

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

try:
    from dashboard.universe import preset_id_for_selection, universe_catalog, ALL_UNIVERSE_TICKERS
except ModuleNotFoundError:  # Direct execution: python dashboard/server.py
    from universe import preset_id_for_selection, universe_catalog, ALL_UNIVERSE_TICKERS  # type: ignore[no-redef]

try:
    _guide_root = Path(__file__).resolve().parent.parent
    if str(_guide_root) not in sys.path:
        sys.path.insert(0, str(_guide_root))
    from allolabs_guide import (
        call_guide_ai,
        format_catalog_block,
        get_compact_system,
        get_guide_system,
        inject_app_context,
        needs_catalog_context,
        parse_guide_response,
    )
    _GUIDE_AVAILABLE = True
except Exception:
    _GUIDE_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Module Constants & Configuration
# File/directory pointers, allowlists, and API version stamp.
# API_VERSION is checked by the desktop client to detect out-of-date servers.
# ═══════════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parent
RESOURCES_DIR = ROOT.parent / "resources"
COMPANY_LOGOS_DIR = RESOURCES_DIR / "company-logos"
RUNNER = ROOT / "runner.py"
COMPANY_DETAILS_HELPER = ROOT / "company_details.py"
DEFAULT_SCRIPT = ROOT.parent / "allolabs.py"
EXAMPLES_DIR = ROOT.parent / "examples"
DEFAULT_RESULTS = EXAMPLES_DIR / "default-run.json"
DEFAULT_PDF = EXAMPLES_DIR / "default-portfolio-report.pdf"
DEFAULT_CHART = EXAMPLES_DIR / "default-performance.png"
UNIVERSE_CATALOG = universe_catalog(DEFAULT_SCRIPT)
SUPPORTED_TICKERS = frozenset(ALL_UNIVERSE_TICKERS)
ALLOWED_UNIVERSES = {"index-leaders", "curated", "canada", "full", "custom"}
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
    "deepseek": {"deepseek-chat", "deepseek-reasoner"},
}
AI_PROVIDER_KEYS = {
    "openai":      ("OpenAI",        "OPENAI_API_KEY"),
    "anthropic":   ("Anthropic",     "ANTHROPIC_API_KEY"),
    "gemini":      ("Google Gemini", "GEMINI_API_KEY"),
    "deepseek":    ("DeepSeek",      "DEEPSEEK_API_KEY"),
    "nvidia-nim":  ("Nvidia NIM",    "NVIDIA_NIM_API_KEY"),
}
ALLOWED_AI_MODELS = {
    stage: {
        provider: set(models)
        for provider, models in AI_PROVIDER_MODELS.items()
    }
    for stage in ("research", "audit")
}
API_VERSION = 23
# Suppresses a flashing console window when spawning subprocesses on Windows;
# a no-op flag (0) on every other platform.  Centralised so every subprocess
# launch in this module stays consistent.
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
REQUIRED_ANALYSIS_MODULES = ("matplotlib", "numpy", "pandas", "scipy", "yfinance")
COMPANY_DETAILS_CACHE_SECONDS = 15 * 60
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
HISTORY_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}/[a-z0-9][a-z0-9._\-]{0,159}$")
MAX_SEED_PROMPT_LENGTH = 12000


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: API Key Utilities
# Masks and resolves provider API keys; checks the process environment and,
# on Windows, the user/machine registry so keys set via System Properties are
# found even if the current shell session was opened before they were set.
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Run State
# Thread-safe container for the lifecycle of a single allolabs.py execution.
# Shared between the HTTP handler threads and the background log consumer.
# ═══════════════════════════════════════════════════════════════════════════════

class RunState:
    def __init__(
        self,
        script_path: Path,
        analysis_python: Path | None = None,
        analysis_python_version: str | None = None,
        analysis_error: str | None = None,
        data_dir: Path | None = None,
        worker_executable: Path | None = None,
    ) -> None:
        self.script_path = script_path
        self.analysis_python = analysis_python
        self.analysis_python_version = analysis_python_version
        self.analysis_error = analysis_error
        self.data_dir = (data_dir or script_path.parent).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.worker_executable = worker_executable
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
            live_results_available = (self.data_dir / "latest_run.json").is_file()
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
                    "ready": self.worker_executable is not None or self.analysis_python is not None,
                    "python": (
                        str(self.worker_executable)
                        if self.worker_executable
                        else (str(self.analysis_python) if self.analysis_python else None)
                    ),
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
                    "run_history": True,
                    "custom_universe": True,
                },
            }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Python Environment Discovery
# Finds a Python interpreter that has all required analysis modules installed.
# Checked in priority order: explicit arg → env var → sys.executable → PATH.
# ═══════════════════════════════════════════════════════════════════════════════

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
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return False, detail[-1] if detail else f"probe exited {result.returncode}"
    return True, result.stdout.strip() or "unknown"


def discover_analysis_python(explicit: Path | None = None) -> tuple[Path | None, str | None, str | None]:
    candidates: list[Path] = []
    environment_path = os.getenv("ALLOLABS_ANALYSIS_PYTHON")
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


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Request Validation
# Parses and validates the JSON payload from /api/run before launching a
# subprocess.  Raises ValueError with a user-facing message on any invalid
# input; never passes untrusted data to the shell.
# ═══════════════════════════════════════════════════════════════════════════════

def validate_config(payload: dict) -> dict:
    try:
        raw_training_years = payload["trainingYears"]
        raw_oos_months = payload["oosMonths"]
        raw_max_position = payload["maxPositionPercent"]
        long_only = payload["longOnly"]
        raw_max_sector = payload["maxSectorPercent"]
        raw_regularization_strength = payload["regularizationStrength"]
        universe = str(payload.get("universe", "custom"))
        regularization = str(payload["regularization"])
        research_provider = str(payload.get("researchProvider", "openai"))
        research_model = str(payload.get("researchModel", payload.get("gptModel", "")))
        audit_provider = str(payload.get("auditProvider", "openai"))
        audit_model = str(payload["auditModel"])
        gpt_views = payload["gptViews"]
        audit_views = payload["auditViews"]
        refresh_cache = payload["refreshCache"]
        analyst_seed_prompt = str(payload.get("analystSeedPrompt", "")).strip()
        auditor_seed_prompt = str(payload.get("auditorSeedPrompt", "")).strip()
        raw_max_news = payload.get("maxNewsArticles", 5)
        raw_batch_size = payload.get("researchBatchSize", 12)
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

    raw_selected_tickers = payload.get("selectedTickers")
    if raw_selected_tickers is None:
        legacy_preset = next(
            (preset for preset in UNIVERSE_CATALOG["presets"] if preset["id"] == universe),
            None,
        )
        if legacy_preset is None:
            raise ValueError("Select at least two securities for the research universe.")
        selected_tickers = list(legacy_preset["tickers"])
    else:
        if not isinstance(raw_selected_tickers, list) or not all(
            isinstance(ticker, str) and TICKER_PATTERN.fullmatch(ticker.strip().upper())
            for ticker in raw_selected_tickers
        ):
            raise ValueError("Selected tickers must be a list of valid ticker symbols.")
        selected_tickers = list(dict.fromkeys(
            ticker.strip().upper() for ticker in raw_selected_tickers
        ))
    if len(selected_tickers) < 2:
        raise ValueError("Select at least two securities for the research universe.")
    unsupported_tickers = sorted(set(selected_tickers) - SUPPORTED_TICKERS)
    if unsupported_tickers:
        raise ValueError(
            "Research universe contains unsupported tickers: "
            + ", ".join(unsupported_tickers)
        )
    universe = preset_id_for_selection(selected_tickers, UNIVERSE_CATALOG)
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
    if len(analyst_seed_prompt) > MAX_SEED_PROMPT_LENGTH:
        raise ValueError("Analyst seed prompt is too long.")
    if len(auditor_seed_prompt) > MAX_SEED_PROMPT_LENGTH:
        raise ValueError("Auditor seed prompt is too long.")
    try:
        max_news_articles = int(float(raw_max_news))
    except (TypeError, ValueError) as exc:
        raise ValueError("News articles per ticker must be a number.") from exc
    if not 1 <= max_news_articles <= 20:
        raise ValueError("News articles per ticker must be between 1 and 20.")
    try:
        research_batch_size = int(float(raw_batch_size))
    except (TypeError, ValueError) as exc:
        raise ValueError("Research batch size must be a number.") from exc
    if not 1 <= research_batch_size <= 30:
        raise ValueError("Research batch size must be between 1 and 30.")

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
        "selectedTickers": selected_tickers,
        "gptViews": gpt_views,
        "researchProvider": research_provider,
        "researchModel": research_model,
        "auditViews": audit_views,
        "auditProvider": audit_provider,
        "auditModel": audit_model,
        "refreshCache": refresh_cache,
        "analystSeedPrompt": analyst_seed_prompt,
        "auditorSeedPrompt": auditor_seed_prompt,
        "maxNewsArticles": max_news_articles,
        "researchBatchSize": research_batch_size,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Background Process Management
# consume_output() runs in a daemon thread and drains stdout from the allolabs
# subprocess into the run-state log deque.  start_run() spawns the process and
# that thread; the handler's /api/stop endpoint terminates it gracefully.
# ═══════════════════════════════════════════════════════════════════════════════

def consume_output(state: RunState, process: subprocess.Popen[str]) -> None:
    # This runs in a daemon thread; if the read loop raises (e.g. the pipe is
    # torn down mid-read) the run must still reach a terminal state instead of
    # being stuck reporting "running" forever, so the finalisation lives in a
    # finally block that always runs exactly once.
    try:
        if process.stdout is not None:
            for line in process.stdout:
                state.add_log(line, "stdout")
    finally:
        try:
            exit_code = process.wait()
        except Exception:  # noqa: BLE001 - process already gone / un-waitable
            exit_code = process.returncode if process.returncode is not None else -1
        with state.lock:
            was_stopping = state.status == "stopping"
            state.exit_code = exit_code
            state.finished_at = time.time()
            state.status = (
                "stopped" if was_stopping
                else ("completed" if exit_code == 0 else "failed")
            )
            state.process = None
        state.add_log(
            f"[runner] Process {'stopped' if was_stopping else 'finished'} with exit code {exit_code}.",
            "system" if exit_code == 0 or was_stopping else "stderr",
        )


def start_run(state: RunState, config: dict) -> str:
    with state.lock:
        if state.process is not None:
            raise RuntimeError("An AlloLabs run is already active.")
        if not state.script_path.is_file():
            raise FileNotFoundError(f"AlloLabs script not found: {state.script_path}")
        if state.worker_executable is None and state.analysis_python is None:
            raise RuntimeError(
                state.analysis_error
                or "No compatible analysis Python is configured. Install the project requirements."
            )

        run_id = secrets.token_hex(4)

        env = os.environ.copy()
        for _, environment_name in AI_PROVIDER_KEYS.values():
            value, _ = resolved_api_key(environment_name)
            if value:
                env[environment_name] = value
        env["PYTHONUTF8"] = "1"
        env["ALLOLABS_DATA_DIR"] = str(state.data_dir)
        env.setdefault("MPLBACKEND", "Agg")
        if state.worker_executable is not None:
            command = [
                str(state.worker_executable),
                "--run",
                str(state.script_path),
                json.dumps(config),
            ]
        else:
            command = [
                str(state.analysis_python),
                "-u",
                str(RUNNER),
                str(state.script_path),
                json.dumps(config),
            ]
        # Only commit the "running" state once the subprocess actually starts.
        # If Popen fails (missing interpreter, permissions, etc.) the exception
        # propagates to the caller with the run state left untouched/idle rather
        # than wedged at "running" with no live process behind it.
        try:
            process = subprocess.Popen(
                command,
                cwd=state.data_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            raise RuntimeError(f"Could not launch the analysis process: {exc}") from exc

        state.status = "running"
        state.run_id = run_id
        state.exit_code = None
        state.started_at = time.time()
        state.finished_at = None
        state.config = config
        state.logs.clear()
        state.next_line_id = 1
        state.process = process

    state.add_log(f"[runner] Run {run_id} launched.", "system")
    threading.Thread(target=consume_output, args=(state, process), daemon=True).start()
    return run_id


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: HTTP Request Handler
# Handles all GET and POST API routes plus static file serving.
# Authentication is enforced via a bearer token on every authenticated route.
# CORS is restricted to same-origin and null (file://) requests only.
# ═══════════════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    server_version = "AlloLabsRunner/1.2"

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
        allowed_directories = {
            self.app.state.script_path.parent.resolve(),
            self.app.state.data_dir.resolve(),
            EXAMPLES_DIR.resolve(),
        }
        allowed_trees = {self.app.state.data_dir.resolve() / "run-history"}
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            self.send_json({"error": f"Artifact is not available yet: {path.name}"}, HTTPStatus.NOT_FOUND)
            return
        inside_allowed_tree = any(resolved.is_relative_to(root) for root in allowed_trees)
        if (resolved.parent not in allowed_directories and not inside_allowed_tree) or not resolved.is_file():
            self.send_json({"error": "Artifact path is outside the AlloLabs project."}, HTTPStatus.FORBIDDEN)
            return
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'inline; filename="{resolved.name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def history_run_dir(self, history_id: str) -> Path:
        if not HISTORY_ID_PATTERN.fullmatch(history_id):
            raise ValueError("Invalid run history identifier.")
        history_root = (self.app.state.data_dir / "run-history").resolve()
        candidate = (history_root / Path(*history_id.split("/"))).resolve()
        if not candidate.is_relative_to(history_root) or not candidate.is_dir():
            raise FileNotFoundError("Archived run was not found.")
        return candidate

    def history_catalog(self) -> list[dict]:
        history_root = self.app.state.data_dir / "run-history"
        if not history_root.is_dir():
            return []
        runs = []
        for manifest_path in history_root.glob("????-??-??/*/manifest.json"):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict) and HISTORY_ID_PATTERN.fullmatch(str(payload.get("id", ""))):
                runs.append(payload)
        runs.sort(key=lambda item: str(item.get("generatedAt", "")), reverse=True)
        return runs

    def results_path(self, history_id: str | None = None) -> tuple[Path | None, str | None]:
        if history_id:
            return self.history_run_dir(history_id) / "run-results.json", "history"
        live_path = self.app.state.data_dir / "latest_run.json"
        if live_path.is_file():
            return live_path, "live"
        if DEFAULT_RESULTS.is_file():
            return DEFAULT_RESULTS, "example"
        return None, None

    def read_results(self, history_id: str | None = None) -> tuple[dict, str]:
        results_path, source = self.results_path(history_id)
        if results_path is None or source is None:
            raise FileNotFoundError("No live or bundled dashboard results are available.")
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Dashboard results must be a JSON object.")
        payload["dataMode"] = source
        if source == "example":
            payload.setdefault("snapshotLabel", "Bundled example")
        elif source == "history":
            payload.setdefault("snapshotLabel", "Archived run")
        return payload, source

    def fetch_company_details(self, ticker: str) -> dict:
        now = time.time()
        with self.app.company_cache_lock:
            cached = self.app.company_cache.get(ticker)
            if cached and now - cached[0] < COMPANY_DETAILS_CACHE_SECONDS:
                return cached[1]

        if self.app.state.worker_executable is None and self.app.state.analysis_python is None:
            raise RuntimeError(
                self.app.state.analysis_error
                or "The analysis Python environment is unavailable."
            )
        if self.app.state.worker_executable is not None:
            command = [
                str(self.app.state.worker_executable),
                "--company-details",
                ticker,
            ]
        else:
            command = [
                str(self.app.state.analysis_python),
                str(COMPANY_DETAILS_HELPER),
                ticker,
            ]
        completed = subprocess.run(
            command,
            cwd=self.app.state.data_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=CREATE_NO_WINDOW,
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

    def read_json_guide(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 262144:
            raise ValueError("Request body is missing or too large.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self) -> None:
        if not self.origin_allowed():
            self.send_json({"error": "Browser origin is not allowed."}, HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        self._dispatch(self._route_get)

    def do_POST(self) -> None:
        self._dispatch(self._route_post)

    def _dispatch(self, route) -> None:
        # Last line of defence: any route that raises an unanticipated error
        # returns a clean JSON 500 instead of dropping the connection with a
        # bare traceback on the console.  If the response was already partly
        # written we can no longer send status/headers, so the fallback send is
        # itself guarded and simply swallowed.
        try:
            route()
        except Exception as exc:  # noqa: BLE001 - intentional catch-all safety net
            try:
                self.send_json(
                    {"error": f"Unexpected server error: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            except Exception:  # noqa: BLE001 - response already committed
                pass

    def _route_get(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            if self.require_auth():
                self.send_json(self.app.state.snapshot())
            return
        if parsed.path == "/api/universe":
            if self.require_auth():
                self.send_json(UNIVERSE_CATALOG)
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
            history_id = parse_qs(parsed.query).get("run", [""])[0].strip() or None
            try:
                payload, _ = self.read_results(history_id)
            except (FileNotFoundError, ValueError) as exc:
                self.send_json(
                    {"error": str(exc) if history_id else "No completed or bundled dashboard run is available."},
                    HTTPStatus.NOT_FOUND,
                )
                return
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                self.send_json({"error": f"Could not read live results: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_json(payload)
            return
        if parsed.path == "/api/history":
            if not self.require_auth():
                return
            self.send_json({
                "runs": self.history_catalog(),
                "folder": str(self.app.state.data_dir / "run-history"),
            })
            return
        if parsed.path == "/api/company":
            if not self.require_auth():
                return
            ticker = parse_qs(parsed.query).get("ticker", [""])[0].strip().upper()
            history_id = parse_qs(parsed.query).get("run", [""])[0].strip() or None
            if not TICKER_PATTERN.fullmatch(ticker):
                self.send_json({"error": "A valid portfolio ticker is required."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                results, _ = self.read_results(history_id)
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
            history_id = parse_qs(parsed.query).get("run", [""])[0].strip() or None
            if history_id:
                try:
                    pdf_path = self.history_run_dir(history_id) / "portfolio-report.pdf"
                except (FileNotFoundError, ValueError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                    return
                self.send_artifact(pdf_path, "application/pdf")
                return
            _, source = self.results_path()
            live_pdf = self.app.state.data_dir / "allolabs_portfolio_report.pdf"
            pdf_path = live_pdf if source == "live" and live_pdf.is_file() else DEFAULT_PDF
            self.send_artifact(pdf_path, "application/pdf")
            return
        if parsed.path == "/api/artifacts/chart":
            if not self.require_auth():
                return
            history_id = parse_qs(parsed.query).get("run", [""])[0].strip() or None
            if history_id:
                try:
                    chart_path = self.history_run_dir(history_id) / "performance-chart.png"
                except (FileNotFoundError, ValueError) as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                    return
                self.send_artifact(chart_path, "image/png")
                return
            try:
                results, source = self.read_results()
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
                results = {}
                source = None
            if not results.get("performance"):
                self.send_json({"error": "The latest run did not generate an OOS chart."}, HTTPStatus.NOT_FOUND)
                return
            live_chart = self.app.state.data_dir / "portfolio_vs_markets_oos.png"
            chart_path = live_chart if source == "live" and live_chart.is_file() else DEFAULT_CHART
            self.send_artifact(chart_path, "image/png")
            return
        if parsed.path == "/api/history/artifact":
            if not self.require_auth():
                return
            query = parse_qs(parsed.query)
            history_id = query.get("run", [""])[0].strip()
            kind = query.get("kind", [""])[0].strip()
            artifact_names = {
                "all-tickers": "all-tickers.csv",
                "ai-opinions": "ai-opinions.csv",
                "config": "run-config.csv",
                "config-json": "run-config.json",
            }
            filename = artifact_names.get(kind)
            if not filename:
                self.send_json({"error": "Unknown archived artifact type."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                artifact_path = self.history_run_dir(history_id) / filename
            except (FileNotFoundError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                return
            content_type = "application/json" if filename.endswith(".json") else "text/csv; charset=utf-8"
            self.send_artifact(artifact_path, content_type)
            return
        static_files = {
            "/": ROOT / "index.html",
            "/index.html": ROOT / "index.html",
            "/styles.css": ROOT / "styles.css",
            "/terminal-theme.css": ROOT / "terminal-theme.css",
            "/app.js": ROOT / "app.js",
            "/resources/allolabs-logo.png": RESOURCES_DIR / "allolabs-logo.png",
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

    def _route_post(self) -> None:
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
        if self.path == "/api/guide":
            if not _GUIDE_AVAILABLE:
                self.send_json(
                    {"error": "Guide module unavailable. Check that allolabs_guide.py is present."},
                    HTTPStatus.NOT_IMPLEMENTED,
                )
                return
            try:
                payload = self.read_json_guide()
                messages = payload.get("messages") or []
                provider = str(payload.get("provider") or "").strip() or None
                guide_model = str(payload.get("guideModel") or "").strip() or None
                app_context = payload.get("appContext") if isinstance(payload.get("appContext"), dict) else None
                if not isinstance(messages, list):
                    raise ValueError("messages must be a list.")
                sanitized: list[dict] = []
                for m in messages[-40:]:
                    if not isinstance(m, dict):
                        continue
                    role = str(m.get("role", ""))
                    content = str(m.get("content", ""))
                    if role not in ("user", "assistant") or not content.strip():
                        continue
                    sanitized.append({"role": role, "content": content[:8000]})
                if not sanitized:
                    raise ValueError("No valid messages provided.")
                if sanitized[-1]["role"] != "user":
                    raise ValueError("Conversation must end with a user message.")
                # Two-stage context: if the query involves tickers/sectors, inject
                # the full catalog so Allo only suggests symbols that actually exist.
                last_user_msg = sanitized[-1]["content"]
                catalog_block: str | None = None
                if _GUIDE_AVAILABLE and needs_catalog_context(last_user_msg):
                    catalog_block = format_catalog_block(
                        UNIVERSE_CATALOG.get("groups", [])
                    )
                llm_messages = inject_app_context(sanitized, app_context, catalog_block)
                raw = call_guide_ai(
                    get_guide_system(), llm_messages,
                    provider=provider, guide_model=guide_model,
                )
                reply, mode, run_config = parse_guide_response(raw)
                self.send_json({"reply": reply, "mode": mode, "runConfig": run_config})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
            except Exception as exc:
                self.send_json({"error": f"Guide AI call failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if self.path == "/api/guide-compact":
            if not _GUIDE_AVAILABLE:
                self.send_json(
                    {"error": "Guide module unavailable."},
                    HTTPStatus.NOT_IMPLEMENTED,
                )
                return
            try:
                payload = self.read_json_guide()
                messages = payload.get("messages") or []
                provider = str(payload.get("provider") or "").strip() or None
                guide_model = str(payload.get("guideModel") or "").strip() or None
                if not isinstance(messages, list) or not messages:
                    raise ValueError("messages must be a non-empty list.")
                sanitized = []
                for m in messages:
                    if not isinstance(m, dict):
                        continue
                    role = str(m.get("role", ""))
                    content = str(m.get("content", ""))
                    if role not in ("user", "assistant") or not content.strip():
                        continue
                    sanitized.append({"role": role, "content": content[:8000]})
                if not sanitized:
                    raise ValueError("No valid messages to compact.")
                compact_request = sanitized + [{
                    "role": "user",
                    "content": "Please produce a compact session summary now.",
                }]
                summary = call_guide_ai(
                    get_compact_system(), compact_request,
                    provider=provider, guide_model=guide_model,
                )
                self.send_json({"summary": summary.strip()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except RuntimeError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
            except Exception as exc:
                self.send_json({"error": f"Compaction failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Threaded Server
# Subclasses ThreadingHTTPServer to attach application state and the company
# details cache.  SO_EXCLUSIVEADDRUSE prevents port reuse collisions on Windows.
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: CLI Entry Point
# Used by scripts/start-dashboard.ps1 (developer/browser mode) and by the
# desktop/app.py wrapper (production desktop mode, random port + auth token).
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the constrained AlloLabs browser relay.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument(
        "--analysis-python",
        type=Path,
        default=None,
        help="Python executable used for AlloLabs model runs.",
    )
    parser.add_argument("--token", default=os.getenv("ALLOLABS_REMOTE_TOKEN"))
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()

    is_local = args.host in {"127.0.0.1", "localhost", "::1"}
    if not is_local and not args.token:
        parser.error("--token or ALLOLABS_REMOTE_TOKEN is required when binding beyond localhost.")

    analysis_python, analysis_version, analysis_error = discover_analysis_python(args.analysis_python)
    state = RunState(
        args.script.resolve(),
        analysis_python=analysis_python,
        analysis_python_version=analysis_version,
        analysis_error=analysis_error,
        data_dir=args.data_dir,
    )
    try:
        server = RunnerServer((args.host, args.port), state, args.token)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) in {48, 98, 10048}:
            print(
                f"Port {args.port} is already in use. Run restart-allolabs-dashboard.bat "
                "to stop the older dashboard process and start this version.",
                file=sys.stderr,
                flush=True,
            )
            return 2
        raise
    print(f"AlloLabs runner listening on http://{args.host}:{args.port}", flush=True)
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

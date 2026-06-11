"""Small authenticated HTTP service for running WealthGPT from the dashboard."""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
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
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "runner.py"
DEFAULT_SCRIPT = ROOT.parent / "wealthgpt.py"
EXAMPLES_DIR = ROOT.parent / "examples"
DEFAULT_RESULTS = EXAMPLES_DIR / "default-run.json"
DEFAULT_PDF = EXAMPLES_DIR / "default-portfolio-report.pdf"
DEFAULT_CHART = EXAMPLES_DIR / "default-performance.png"
ALLOWED_UNIVERSES = {"curated", "canada", "full"}
API_VERSION = 5
REQUIRED_ANALYSIS_MODULES = ("matplotlib", "numpy", "pandas", "scipy", "yfinance")


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
                "capabilities": {
                    "results": True,
                    "artifacts": True,
                    "pdf_viewer": True,
                    "chart_viewer": True,
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
        universe = str(payload["universe"])
        gpt_views = payload["gptViews"]
        refresh_cache = payload["refreshCache"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Run configuration is incomplete or invalid.") from exc

    numeric_values = (raw_training_years, raw_oos_months, raw_max_position)
    if any(isinstance(value, bool) for value in numeric_values):
        raise ValueError("Numeric run settings cannot be boolean.")
    try:
        training_years = float(raw_training_years)
        oos_months_value = float(raw_oos_months)
        max_position_value = float(raw_max_position)
    except (TypeError, ValueError) as exc:
        raise ValueError("Run configuration contains a non-numeric setting.") from exc
    if not all(math.isfinite(value) for value in (
        training_years, oos_months_value, max_position_value
    )):
        raise ValueError("Numeric run settings must be finite.")
    if not oos_months_value.is_integer() or not max_position_value.is_integer():
        raise ValueError("OOS months and maximum position must be whole numbers.")
    oos_months = int(oos_months_value)
    max_position = int(max_position_value)

    if not isinstance(gpt_views, bool) or not isinstance(refresh_cache, bool):
        raise ValueError("GPT views and cache refresh settings must be boolean.")
    if not 0.25 <= training_years <= 10:
        raise ValueError("Training lookback must be between 0.25 and 10 years.")
    if not 0 <= oos_months <= 60:
        raise ValueError("Out-of-sample window must be between 0 and 60 months.")
    if not 1 <= max_position <= 100:
        raise ValueError("Maximum position must be between 1 and 100 percent.")
    if universe not in ALLOWED_UNIVERSES:
        raise ValueError("Research universe is not allowlisted.")

    return {
        "trainingYears": training_years,
        "oosMonths": oos_months,
        "maxPositionPercent": max_position,
        "universe": universe,
        "gptViews": gpt_views,
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
        if not path.is_file() or path.parent != ROOT:
            self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
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
        }
        if parsed.path in static_files:
            self.send_static(static_files[parsed.path])
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

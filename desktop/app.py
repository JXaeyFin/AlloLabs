"""Native desktop lifecycle wrapper for the existing AlloLabs dashboard."""

from __future__ import annotations

import ctypes
import os
import secrets
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlencode

if os.name == "nt":
    from ctypes import wintypes

from allolabs_paths import application_root, user_data_dir
from dashboard.server import RunState, RunnerServer, discover_analysis_python


APP_TITLE = "AlloLabs"
MUTEX_NAME = "Local\\AlloLabs.Desktop.Singleton"
ERROR_ALREADY_EXISTS = 183


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def acquire_single_instance():
    """Hold a Windows mutex for the lifetime of the desktop process."""
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise OSError("Could not create the AlloLabs application lock.")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            None,
            "AlloLabs is already running.",
            APP_TITLE,
            0x00000040,
        )
        kernel32.CloseHandle(handle)
        return False
    return handle


def release_single_instance(handle) -> None:
    if os.name == "nt" and handle not in (None, False):
        ctypes.windll.kernel32.CloseHandle(handle)


def edge_app_command(url: str, profile_dir: Path) -> list[str] | None:
    """Return a dependency-free Windows development fallback."""
    if os.name != "nt":
        return None
    candidates = [
        shutil.which("msedge"),
        Path(os.getenv("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.getenv("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return [
                str(candidate),
                f"--app={url}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
            ]
    return None


def stop_active_run(state: RunState) -> None:
    with state.lock:
        process = state.process
        if process is not None and process.poll() is None:
            state.status = "stopping"
            process.terminate()
    if process is not None:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()


def bundled_worker_path() -> Path:
    executable = Path(sys.executable).resolve()
    worker_name = "AlloLabsWorker.exe" if os.name == "nt" else "AlloLabsWorker"
    return executable.with_name(worker_name)


def desktop_icon(root: Path) -> Path:
    return root / "resources" / (
        "allolabs.ico" if os.name == "nt" else "allolabs-logo.png"
    )


def run_desktop() -> int:
    lock = acquire_single_instance()
    if lock is False:
        return 0

    root = application_root()
    data_dir = user_data_dir()
    os.environ["ALLOLABS_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("MPLBACKEND", "Agg")
    script_path = root / "allolabs.py"
    token = secrets.token_urlsafe(32)

    if is_frozen():
        analysis_python = None
        analysis_version = "Bundled AlloLabs runtime"
        worker_executable = bundled_worker_path()
        analysis_error = None if worker_executable.is_file() else (
            f"Bundled analysis worker was not found: {worker_executable}"
        )
    else:
        analysis_python, analysis_version, analysis_error = discover_analysis_python()
        worker_executable = None

    state = RunState(
        script_path,
        analysis_python=analysis_python,
        analysis_python_version=analysis_version,
        analysis_error=analysis_error,
        data_dir=data_dir,
        worker_executable=worker_executable,
    )
    server = RunnerServer(("127.0.0.1", 0), state, token)
    server_thread = threading.Thread(
        target=server.serve_forever,
        name="allolabs-local-server",
        daemon=True,
    )
    server_thread.start()
    port = server.server_address[1]
    query = urlencode({"desktop": "1", "desktopToken": token})
    url = f"http://127.0.0.1:{port}/?{query}"

    try:
        try:
            import webview
        except ModuleNotFoundError:
            command = edge_app_command(url, data_dir / "webview-profile")
            if command is None:
                raise RuntimeError(
                    "The desktop window requires pywebview or a supported system webview. "
                    "Install requirements-desktop.txt."
                )
            completed = subprocess.run(command, check=False)
            return completed.returncode

        webview.create_window(
            APP_TITLE,
            url=url,
            width=1440,
            height=920,
            min_size=(1060, 680),
            background_color="#05070A",
            confirm_close=False,
        )
        webview.start(
            debug=os.getenv("ALLOLABS_DESKTOP_DEBUG") == "1",
            private_mode=False,
            storage_path=str(data_dir / "webview"),
            icon=str(desktop_icon(root)),
        )
        return 0
    finally:
        stop_active_run(state)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        release_single_instance(lock)


def main() -> int:
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())

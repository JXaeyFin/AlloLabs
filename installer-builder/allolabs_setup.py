from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

APP_NAME = "AlloLabs"
VERSION = "1.3.2"
ZIP_NAME = "AlloLabs-v1.3.2-Windows-x64.zip"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def show_message(title: str, message: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        if error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        print(f"{title}: {message}")


def run_quiet(command: list[str]) -> None:
    subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def create_shortcut(path: Path, target: Path, working_directory: Path) -> None:
    ps = textwrap.dedent(f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{str(path).replace("'", "''")}')
    $Shortcut.TargetPath = '{str(target).replace("'", "''")}'
    $Shortcut.WorkingDirectory = '{str(working_directory).replace("'", "''")}'
    $Shortcut.IconLocation = '{str(target).replace("'", "''")}'
    $Shortcut.Description = 'AlloLabs v{VERSION}'
    $Shortcut.Save()
    """)
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def install() -> int:
    if "--self-test" in sys.argv:
        payload = resource_path(ZIP_NAME)
        if not payload.is_file():
            print(f"missing payload: {payload}")
            return 2
        with zipfile.ZipFile(payload) as archive:
            names = set(archive.namelist())
        required = {"AlloLabs.exe", "AlloLabsWorker.exe"}
        missing = sorted(name for name in required if name not in names)
        if missing:
            print("missing from payload: " + ", ".join(missing))
            return 3
        print("installer self-test ok")
        return 0

    payload = resource_path(ZIP_NAME)
    if not payload.is_file():
        raise FileNotFoundError(f"Installer payload was not found: {payload}")

    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_root = local_app_data / "Programs" / APP_NAME
    temp_target = install_root.with_name(f"{APP_NAME}.new")
    old_target = install_root.with_name(f"{APP_NAME}.old")

    run_quiet(["taskkill.exe", "/IM", "AlloLabs.exe", "/F"])
    run_quiet(["taskkill.exe", "/IM", "AlloLabsWorker.exe", "/F"])

    install_root.parent.mkdir(parents=True, exist_ok=True)
    if temp_target.exists():
        shutil.rmtree(temp_target)
    temp_target.mkdir(parents=True)
    with zipfile.ZipFile(payload) as archive:
        archive.extractall(temp_target)

    exe = temp_target / "AlloLabs.exe"
    worker = temp_target / "AlloLabsWorker.exe"
    if not exe.is_file() or not worker.is_file():
        raise RuntimeError("Extracted app is incomplete: AlloLabs.exe or AlloLabsWorker.exe is missing.")

    if old_target.exists():
        shutil.rmtree(old_target)
    if install_root.exists():
        install_root.rename(old_target)
    temp_target.rename(install_root)
    if old_target.exists():
        shutil.rmtree(old_target)

    exe = install_root / "AlloLabs.exe"
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    start_menu.mkdir(parents=True, exist_ok=True)
    desktop = Path.home() / "Desktop"
    create_shortcut(start_menu / "AlloLabs.lnk", exe, install_root)
    create_shortcut(desktop / "AlloLabs.lnk", exe, install_root)

    uninstall_script = install_root / "Uninstall-AlloLabs.ps1"
    uninstall_script.write_text(
        textwrap.dedent(f"""
        $ErrorActionPreference = "Stop"
        taskkill.exe /IM AlloLabs.exe /F 2>$null
        taskkill.exe /IM AlloLabsWorker.exe /F 2>$null
        Remove-Item -LiteralPath "{install_root}" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath "{start_menu}" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath "{desktop / 'AlloLabs.lnk'}" -Force -ErrorAction SilentlyContinue
        """),
        encoding="utf-8",
    )

    subprocess.Popen([str(exe)], cwd=str(install_root))
    show_message("AlloLabs Installer", f"AlloLabs v{VERSION} was installed to:\n{install_root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(install())
    except Exception as exc:
        show_message("AlloLabs Installer", str(exc), error=True)
        raise SystemExit(1)

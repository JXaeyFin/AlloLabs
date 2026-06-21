"""Verify a native AlloLabs portable directory without network access."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def executable_paths(portable: Path, platform_name: str) -> tuple[Path, Path]:
    if platform_name == "macos":
        macos_dir = portable / "AlloLabs.app" / "Contents" / "MacOS"
        return macos_dir / "AlloLabs", macos_dir / "AlloLabsWorker"
    suffix = ".exe" if platform_name == "windows" else ""
    return portable / f"AlloLabs{suffix}", portable / f"AlloLabsWorker{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("portable", type=Path)
    parser.add_argument(
        "--platform",
        choices=("windows", "macos", "linux"),
        default={"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"),
    )
    args = parser.parse_args()
    portable = args.portable.resolve()
    app, worker = executable_paths(portable, args.platform)

    missing = [str(path) for path in (app, worker) if not path.is_file()]
    if args.platform != "macos":
        assets = [
            portable / "_internal" / "allolabs.py",
            portable / "_internal" / "dashboard" / "index.html",
            portable / "_internal" / "resources" / "allolabs-logo.png",
            portable / "_internal" / "examples" / "default-run.json",
        ]
        missing.extend(str(path) for path in assets if not path.is_file())
    if missing:
        raise SystemExit("Portable build is incomplete:\n" + "\n".join(missing))

    completed = subprocess.run(
        [str(worker), "--self-test"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"Worker self-test failed ({completed.returncode}):\n{completed.stderr}"
        )
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    if result.get("status") != "ok" or result.get("apiVersion", 0) < 19:
        raise SystemExit(f"Invalid worker self-test result: {result}")

    files = [path for path in portable.rglob("*") if path.is_file()]
    size_mb = sum(path.stat().st_size for path in files) / 1024 / 1024
    print(
        f"AlloLabs {args.platform} portable build verified: "
        f"{len(files)} files, {size_mb:.2f} MB, Python {result['python']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Console-capable worker entry point bundled beside the AlloLabs desktop app."""

from __future__ import annotations

import sys


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Self-Test
# Verifies that all analysis dependencies are importable and prints a JSON
# status payload.  Called by the desktop app at startup to confirm the worker
# bundle is intact before accepting user runs.
# ═══════════════════════════════════════════════════════════════════════════════

def self_test() -> int:
    import json

    import matplotlib
    import numpy
    import pandas
    import scipy
    import webview
    import yfinance
    from dashboard import runner, server

    print(json.dumps({
        "status": "ok",
        "python": sys.version.split()[0],
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "matplotlib": matplotlib.__version__,
        "yfinance": yfinance.__version__,
        "webview": getattr(webview, "__version__", "bundled"),
        "apiVersion": server.API_VERSION,
        "runner": runner.__name__,
    }))
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION: Entry Point
# Dispatches to the appropriate worker mode based on the first CLI argument.
# Three modes: --run (pipeline), --self-test (dependency check),
# --company-details (single-ticker context fetch).
# ═══════════════════════════════════════════════════════════════════════════════

def _dispatch(arguments: list[str]) -> int:
    if arguments[0] == "--run":
        if len(arguments) != 3:
            raise SystemExit(
                "Usage: AlloLabsWorker --run PATH_TO_ALLOLABS CONFIG_JSON"
            )
        from dashboard import runner

        sys.argv = ["runner.py", arguments[1], arguments[2]]
        return runner.main()

    if arguments[0] == "--self-test":
        return self_test()

    if arguments[0] == "--company-details":
        if len(arguments) != 2:
            raise SystemExit("Usage: AlloLabsWorker --company-details TICKER")
        from dashboard import company_details

        sys.argv = ["company_details.py", arguments[1]]
        return company_details.main()

    raise SystemExit(f"Unknown AlloLabs worker mode: {arguments[0]}")


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        raise SystemExit("Usage: AlloLabsWorker --run ... | --company-details ...")

    # SystemExit (usage messages) and KeyboardInterrupt propagate untouched.
    # Anything else — a missing bundled dependency, an import-time failure —
    # becomes a single readable error line plus a non-zero exit code so the
    # desktop shell never surfaces a raw traceback from the worker process.
    try:
        return _dispatch(arguments)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:  # noqa: BLE001 - top-level worker safety net
        print(
            f"AlloLabs worker failed ({arguments[0]}): {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

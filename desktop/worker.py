"""Console-capable worker entry point bundled beside the AlloLabs desktop app."""

from __future__ import annotations

import sys


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


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        raise SystemExit("Usage: AlloLabsWorker --run ... | --company-details ...")

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


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_submodules


root = Path(SPECPATH).parent
is_macos = sys.platform == "darwin"
app_icon = root / "resources" / (
    "allolabs.ico" if os.name == "nt" else "allolabs-logo.png"
)
allowed_webview_platforms = (
    {"cocoa"} if is_macos
    else ({"edgechromium", "mshtml", "win32", "winforms"} if os.name == "nt" else {"qt"})
)


def include_webview_module(name):
    prefix = "webview.platforms."
    if not name.startswith(prefix):
        return True
    platform_name = name[len(prefix):].split(".", 1)[0]
    return platform_name in allowed_webview_platforms


app_hidden_imports = collect_submodules("webview", filter=include_webview_module)
worker_hidden_imports = collect_submodules("yfinance") + [
    "allolabs",
    "allolabs_company",
    "allolabs_paths",
    "allolabs_report",
    "dashboard.company_details",
    "dashboard.runner",
    "matplotlib.backends.backend_agg",
    "scipy.optimize",
    "scipy.stats",
]

app_analysis = Analysis(
    [str(root / "desktop" / "app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "allolabs.py"), "."),
        (str(root / "dashboard" / "index.html"), "dashboard"),
        (str(root / "dashboard" / "app.js"), "dashboard"),
        (str(root / "dashboard" / "styles.css"), "dashboard"),
        (str(root / "dashboard" / "terminal-theme.css"), "dashboard"),
        (str(root / "resources"), "resources"),
        (str(root / "examples"), "examples"),
    ],
    hiddenimports=app_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

worker_analysis = Analysis(
    [str(root / "desktop" / "worker.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=worker_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

app_pyz = PYZ(app_analysis.pure)
worker_pyz = PYZ(worker_analysis.pure)

app_exe = EXE(
    app_pyz,
    app_analysis.scripts,
    [],
    exclude_binaries=True,
    name="AlloLabs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(app_icon),
)

worker_exe = EXE(
    worker_pyz,
    worker_analysis.scripts,
    [],
    exclude_binaries=True,
    name="AlloLabsWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=str(app_icon),
)

collection = COLLECT(
    app_exe,
    worker_exe,
    app_analysis.binaries,
    app_analysis.datas,
    worker_analysis.binaries,
    worker_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AlloLabsBundle" if is_macos else "AlloLabs",
)

if is_macos:
    app = BUNDLE(
        collection,
        name="AlloLabs.app",
        icon=str(app_icon),
        bundle_identifier="com.allolabs.desktop",
        info_plist={
            "CFBundleDisplayName": "AlloLabs",
            "CFBundleShortVersionString": "1.3.2",
            "CFBundleVersion": "1.3.2",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        },
    )

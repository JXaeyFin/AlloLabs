# AlloLabs v1.3.2 Portable

AlloLabs is an AI-assisted global asset-allocation research application.

## Launch

- **Windows:** open `AlloLabs.exe`.
- **macOS:** open `AlloLabs.app`. On first launch, Control-click the app and
  select **Open** if Gatekeeper warns that the unsigned publisher is unknown.
- **Linux:** run `./AlloLabs`. If necessary, first run
  `chmod +x AlloLabs AlloLabsWorker`.

Keep every file in this directory together. The worker executable is launched
automatically and should not normally be opened directly.

## Requirements

- Internet access for current market data and optional AI requests.
- Optional provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or
  `GEMINI_API_KEY`.
- Linux desktop environments require working X11 or Wayland graphics support.

## User Data

Generated reports, results, and caches are stored outside this folder:

- Windows: `%LOCALAPPDATA%\AlloLabs`
- macOS: `~/Library/Application Support/AlloLabs`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/AlloLabs`

AlloLabs is educational research software, not financial advice.

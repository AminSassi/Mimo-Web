# MiMo Auto Installer v2.0

Production-grade Windows installer ecosystem for MiMo Auto.

## Architecture (4 Layers)

```
┌─────────────────────────────────────┐
│  Layer 1: Inno Setup Installer      │
│  MiMoSetup.iss → MiMoSetup.exe     │
│  Trusted Windows layer              │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Layer 2: MiMoBootstrapper.exe      │
│  First-run setup + dependencies     │
│  Health check + auto-repair         │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Layer 3: mimo_launch.exe           │
│  Self-healing runtime               │
│  Every launch: health → repair      │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Layer 4: State + Portable Mode     │
│  install_state.json tracking        │
│  portable.flag for self-contained   │
└─────────────────────────────────────┘
```

## Components

| File | Purpose |
|------|---------|
| `mimo_installer_v2.py` | Full GUI installer (customtkinter) |
| `bootstrapper/MiMoBootstrapper.py` | Backend engine — health check, repair, dependency install |
| `launcher/mimo_launch.py` | Self-healing launcher — runs health check on every launch |
| `MiMoSetup.iss` | Inno Setup script for production MSI/EXE |
| `preflight.cmd` | Zero-dependency system check |
| `build_installer.py` | Build script for all EXEs |

## Features

- **Inno Setup production installer** — trusted Windows layer, proper uninstall entry
- **Bootstrapper engine** — detects & installs Node.js, Git, npm
- **Self-healing runtime** — auto-repairs on every launch via mimo_launch.exe
- **State tracking** — `install_state.json` prevents reinstall loops
- **Portable mode** — `portable.flag` disables registry/PATH changes
- **Diagnostic export** — non-blocking ZIP export with system info, logs, state
- **Repair mode** — full diagnostic + auto-repair from GUI
- **SHA-256 verification** — all downloaded installers verified
- **PATH refresh** — re-reads registry after MSI installs

## Build

```bash
pip install pyinstaller customtkinter
python build_installer.py
```

Then compile `MiMoSetup.iss` with Inno Setup 6+.

## CLI Usage

```bash
# First-run setup
MiMoBootstrapper.exe --first-run --install-dir "C:\MiMo Auto"

# Health check
MiMoBootstrapper.exe --health-check --json

# Repair
MiMoBootstrapper.exe --repair

# Portable mode
echo. > portable.flag
```

## State File

```json
{
  "version": "2.0.0",
  "install_dir": "C:\\MiMo Auto",
  "installed_at": "2026-06-18T12:00:00",
  "last_health_check": "2026-06-18T12:05:00",
  "last_health_result": "healthy",
  "deps": {
    "node": {"status": "ok", "version": "v20.15.1"},
    "npm": {"status": "ok", "version": "10.7.0"},
    "git": {"status": "ok", "version": "git version 2.45.2"}
  },
  "mimo": {"status": "ok", "version": "2.0.0"},
  "portable": false,
  "launches": 5,
  "repairs": 1
}
```

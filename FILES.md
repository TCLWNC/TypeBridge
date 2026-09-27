# What every file is

TypeBridge — cross-screen input (跨屏输入). This page explains the repository file by file.

## Root

| Path | What it is |
| --- | --- |
| `README.md` | Start here: download, quick start, features, troubleshooting, build steps |
| `main.py` | PC entry point (`python main.py`); all flags are parsed here |
| `Start-TypeBridge.bat` | Double-click to start the PC app with its window |
| `Start-TypeBridge-Tray.bat` | Start hidden in the tray (use this from Windows startup) |
| `Allow-Firewall-AsAdmin.bat` | Opens inbound TCP+UDP `8788-8800`; asks for admin once |
| `Remove-Firewall-Rules.bat` | Deletes those firewall rules |
| `TypeBridge-1.0.0-release.zip` | One-file copy of everything (app + source + docs) |
| `FILES.md` | This file |
| `HOW-TO-PUSH.md` | How the local folder is wired to the GitHub repo, and how to push |
| `.gitignore` | Keeps regeneratable build output out of the repository |

## `crosslink/` — PC source (Python)

| File | What it does |
| --- | --- |
| `__init__.py` | App name/title/version constants |
| `app.py` | Application lifecycle: server, injector, watchers, window, tray, title bar & icon |
| `server.py` | HTTP endpoints (`/api/hello`, `/api/op`, `/api/events`, `/api/state`, `/api/qr.png`, `/api/pc/*`) and the device registry |
| `config.py` | Config load/save (`%APPDATA%\CrossLink\config.json`) |
| `discovery.py` | UDP device discovery responder (answers the phone's broadcast) |
| `winapi.py` | Windows layer: `SendInput` Unicode typing, keys/combos, clipboard, firewall rules, autostart |
| `uia.py` | Reads the focused window's title/process and the text in its edit box (drives the "Input target" card) |
| `web/` | The web UI (also served to phones): `index.html`, `app.js`, `base.css`, `mobile.html`, `mobile.js` |
| `assets/` | Icons (`icon.ico`, `icon.png`, `icon-512.png`) |
| `native.py` | Optional tkinter UI (`--native`) |
| `qtui.py` | Optional Qt UI (`--qt`) |
| `selftest.py` | `--selftest` report |

## `android/` — Android source (Kotlin)

| Path | What it is |
| --- | --- |
| `app/src/main/kotlin/com/crosslink/app/MainActivity.kt` | The whole phone UI: device list, typing page, logs, settings, dialogs |
| `app/src/main/kotlin/com/crosslink/app/Client.kt` | HTTP/SSE client (OkHttp) |
| `app/src/main/kotlin/com/crosslink/app/Discovery.kt` | UDP broadcast discovery + /24 subnet HTTP scan |
| `app/src/main/res/` | Icons, colors, strings, theme |
| `app/build.gradle.kts` | App id `com.crosslink.app`, minSdk 26, targetSdk 34 |

## `apk/`

The built Android package, ready to install.

## Language

The UI ships in **English and Chinese** (中文). Switch it in
**Settings → Language** on the PC, or **Settings → 界面语言** in the Android app.
Left untouched, it follows the system language of the PC / phone.

## Not in the repository

`dist-*/`, `_internal/`, the packaged exe folder and the preview screenshots are build
output — they can be regenerated with the commands in `README.md`, so they are git-ignored.

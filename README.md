# TypeBridge — Cross-Screen Input (跨屏输入)

**跨屏输入**：手机当电脑的无线键盘。
Type on your phone and the text appears in whatever window has focus on the PC
(Notepad, Word, a browser, an IDE…). Chinese, English, emoji, Enter, Backspace,
arrow keys and Ctrl shortcuts all work.

The app is bilingual — **English and 中文**, switchable in Settings.
Product name: **TypeBridge** in English, **跨屏输入** in Chinese.

---

## Download

Files are attached to the release page: <https://github.com/TCLWNC/TypeBridge/releases>

| Platform | File | Notes |
| --- | --- | --- |
| Phone | `TypeBridge-1.1.0-android.apk` | Android 8.0+ (minSdk 26), install directly |
| PC | `TypeBridge-1.1.0-Setup.exe` | Windows installer — **bundles the 228 MB speech model**, so voice input works with no extra download |
| PC | `TypeBridge-1.1.0-win64.zip` | Portable Windows build — unzip and run, no install |

The installer puts everything under `%LOCALAPPDATA%\TypeBridge` (no admin rights needed),
creates shortcuts, can set up tray autostart, and **already contains the offline speech
model** — it installs that to `%APPDATA%\CrossLink\asr\sense-voice` (skipped if it is
already there), so voice typing works right after installing, with no internet.
The zip is the portable alternative: unzip anywhere and run `TypeBridge-PC.exe`.
For the portable build, run `Get-Voice-Model.bat` once to fetch the model.
Either way there is no Python to install.

---

## Screenshots

| PC — input page | PC — settings | PC — about |
| --- | --- | --- |
| ![PC input](preview/pc-input.png) | ![PC settings](preview/pc-settings.png) | ![PC about](preview/pc-about.png) |

| Phone — devices | Phone — typing | Phone — settings |
| --- | --- | --- |
| ![Phone devices](preview/phone-devices.png) | ![Phone typing](preview/phone-input.png) | ![Phone settings](preview/phone-settings.png) |

Both ends now share a version number; older releases used separate numbers.

---

## Quick start

| Step | What to do |
| --- | --- |
| 1 | On the PC, double-click **`Start-TypeBridge.bat`** (or run `TypeBridge-PC.exe`) |
| 2 | On the phone, install the APK and join the **same Wi-Fi**. (No app? Scan the QR code in the PC window and use the phone browser instead.) |
| 3 | Click into the program you want to type into on the PC (e.g. put the caret in Notepad) |
| 4 | Type on the phone — the text appears on the PC as you type |

The first run asks for administrator rights once: click **Yes** so the app can open inbound
ports `8788-8800`. Without that, phones cannot find the computer.

---

## Features

**PC side (Python, `crosslink/`)**

- HTTP + SSE server (default port `8788`; moves up automatically when the port is taken)
- Device discovery over UDP broadcast, plus a subnet-scan fallback
- **Offline voice typing**: click *Voice input* in the window, speak, and the text is
  recognised on this machine and typed into the focused window (no cloud, no account)
- Three ways to show the UI: embedded window (default), system browser (`--browser`),
  or tray-only with no window (`--tray`)
- Closing the window keeps it in the tray. Tray menu: Show window / Copy phone link /
  Keyboard injection on-off / Quit
- Injects received text into the focused window with Windows `SendInput` (Unicode), or
  optionally by clipboard paste for apps that ignore Unicode injection

**Phone side (Kotlin, native Android views)**

- Bottom navigation: Send (device list) / Logs / Settings
- Finds the PC two ways: UDP broadcast discovery + HTTP scan of your /24 subnet
- Typing page with Delete / Restore / Enter, a live character counter and a status line
- Tapping **Enter** sends the key and clears the phone input box; the PC keeps the text.
  **Restore** brings the last sent text back so you can fix a typo and send again
- Optional 4-digit pairing code for new phones (custom rounded dialog, auto-connect at 4 digits)
- Connection animation when a device is picked; a phone that is killed or swiped away
  disappears from the PC device list within about 6 seconds
- **Voice input**: the mic button next to the PC name turns the phone into a wireless
  microphone — record, send the clip to the PC, and the recognised text comes back into
  the phone's input box (then it syncs to the PC like anything else you type there)

---

## How it works

```
   Phone (app or browser)                 PC (TypeBridge-PC.exe)
 ┌────────────────────┐                 ┌──────────────────────────────┐
 │ type text          │ ──POST /api/op─►│ command queue (single thread) │
 │ whole text, 250 ms │                 │ SendInput → focused window    │
 │ device list        │ ◄──SSE──────────│ /api/events: state, devices   │
 └────────────────────┘                 └──────────────────────────────┘
            ▲                                        │
            └──────── UDP broadcast discovery ────────┘
```

The phone sends the **whole text** of its input box (debounced by 250 ms) instead of
character deltas; the PC then makes the target window match that text. This avoids the
misplaced-character problems delta algorithms cause when the caret moves.

HTTP API (JSON):

| Direction | Endpoint | Purpose |
| --- | --- | --- |
| Phone → PC | `POST /api/hello` | Register the device (optional pairing code), returns a session id |
| Phone → PC | `POST /api/op` | `sync` whole text / `key` a key / `combo` a shortcut / `ping` heartbeat / `bye` goodbye |
| PC → both | `GET /api/events` | SSE stream: state, devices, logs, focused window, setting changes |
| Phone → PC | `GET /api/state` | One-shot state (used by the subnet scan fallback) |
| PC → phone | `GET /api/qr.png` | QR code that opens the phone web UI |
| Local UI | `POST /api/pc/*` | Settings, roll the pairing code, disconnect a device, allow firewall, quit (localhost only) |

Discovery protocol (UDP, same port as HTTP):

```
phone  → broadcast  "CROSSLINK?"
PC     → unicast    {"t":"crosslink","v":1,"name":"MY-PC","port":8788,
                     "pin":false,"version":"1.0.0","id":"..."}
```

---

## Settings worth knowing

- **Injection method** — `Direct` (default, fastest, never touches the clipboard) or
  `Clipboard paste` (Ctrl+V; more reliable for RDP sessions and some Java apps).
- **Voice input** (the mic button in the top bar) — click it, speak, and it stops by
  itself after a short pause. It lives under **Settings → Voice input**, and the first
  use needs the speech model: run
  `Get-Voice-Model.bat` once (≈228 MB, downloaded to
  `%APPDATA%\CrossLink\asr\sense-voice`). It is **SenseVoice-Small**, Apache-2.0,
  running fully offline on the CPU — Mandarin, Cantonese, English, Japanese, Korean.
  Recognition is roughly 8× faster than real time (a 5.6 s clip takes 0.7 s).
  - **Global hotkey** (default `F9`) triggers it from any program, and the key is
    rebindable. Two trigger modes: **hold to talk** (record while held, stop and type
    on release) or **press to start** (press once to start, press again to stop).
  - While recording, a **waveform appears near the bottom of the screen** — nine white
    bars driven by the microphone's FFT spectrum, on a fully transparent background.
  - The phone can dictate too: hold the Enter key for 0.5 s to record, release to stop.
- **Inter-character delay** — default 0 ms; raise to 5–20 ms for old programs that drop keys.
- **Topmost** — keep the window above everything else.
- **Run at login / Tray** — close-button behavior and Windows startup.
- **Require pairing code** — when on, a new phone must enter the 4-digit code shown in the PC window.
- **Language** — switch the interface between English and 中文.

---

## Command-line flags

```
TypeBridge-PC.exe                     open the UI (default)
TypeBridge-PC.exe --tray              stay in the tray, window hidden (use this at login)
TypeBridge-PC.exe --browser           run the UI in your default browser
TypeBridge-PC.exe --headless          server only, no window and no tray
TypeBridge-PC.exe --selftest          self-test; writes a report next to the config
TypeBridge-PC.exe --port 9000         use a different port (default 8788)
TypeBridge-PC.exe --name "Office-PC"  change the name phones see
TypeBridge-PC.exe --pin 2468          fix the pairing code
TypeBridge-PC.exe --no-pin            disable pairing code checking
TypeBridge-PC.exe --no-inject         receive but do not type (debugging)
TypeBridge-PC.exe --native            use the tkinter UI instead of the web UI
TypeBridge-PC.exe --qt                use the Qt UI instead of the web UI
```

Config lives in `%APPDATA%\CrossLink\config.json`.

---

## Troubleshooting

**The phone cannot find the PC**

1. Both on the same Wi-Fi? Mobile data being on, or a router with "AP isolation" or a guest
   network, blocks discovery.
2. Windows Firewall not opened yet → click **Allow firewall** in the PC window
   (or run `Allow-Firewall-AsAdmin.bat`).
3. VPN or several network adapters → type the address manually on the phone's Settings tab,
   e.g. `192.168.1.20:8788`.

**Connected, but nothing is typed on the PC**

- Check the **Input target** card. If it points at the TypeBridge window itself, click into
  the program you actually want to type into.
- The target runs as administrator (Task Manager, some games) → run `TypeBridge-PC.exe`
  as administrator too.
- The target ignores Unicode injection → switch the method to **Clipboard paste**.
- An old program drops characters → set the inter-character delay to 5–20 ms.
- Injection also fails while the PC is locked or an RDP session is disconnected.

**Port already in use** — the app moves to the next free port (`8788 → 8789 …`) and the
address in the window and QR code follows automatically.

---

## Repository layout

| Path | What it is |
| --- | --- |
| `crosslink/` | PC source (Python 3.10+, standard library + pywebview/pystray/qrcode/Pillow) |
| `main.py` | PC entry point |
| `android/` | Android source (Kotlin, native views, Gradle project) |
| `apk/` | Built Android package |
| `Start-TypeBridge.bat` | Double-click to start with a window |
| `Start-TypeBridge-Tray.bat` | Start hidden in the tray (for Windows startup) |
| `Allow-Firewall-AsAdmin.bat` | Open inbound ports `8788-8800` (asks for admin once) |
| `Remove-Firewall-Rules.bat` | Undo the firewall rules |
| `FILES.md` | Every file explained |
| `HOW-TO-PUSH.md` | How this repo is wired to GitHub and how to push |

Regeneratable build output (`dist-*/`, the packaged `_internal/` folder, ~200 MB) is
intentionally not committed.

---

## Build from source

**PC**

```powershell
pip install pywebview pystray qrcode pillow pyinstaller
python -m PyInstaller --noconfirm --onedir --windowed --name TypeBridge-PC `
  --icon crosslink\assets\icon.ico `
  --add-data "crosslink\web;crosslink\web" `
  --add-data "crosslink\assets;crosslink\assets" `
  --hidden-import qrcode.image.pil --hidden-import crosslink.qtui --hidden-import crosslink.native main.py
```

Use `--onedir`, not `--onefile`: a single-file build makes WebView2's .NET initialization
stall — the window appears and then ignores every click (Windows marks it "Not Responding").
With `--onedir` the same sampling showed **0 unresponsive events over 36 seconds**.

**Android**

```bash
cd android
gradle assembleDebug        # needs JDK 17 + Android SDK 34
```

---

## What has actually been verified

Measured on real hardware during development, not estimated:

| Check | Result |
| --- | --- |
| Android device discovery | Phone finds the PC on the same Wi-Fi (UDP broadcast); list shows name + address |
| Live typing | Text typed on the phone appears in the PC's focused window while typing |
| Enter button clears the phone box | On device: box returns to the placeholder, counter back to 0, PC keeps the text |
| Restore button | On device: the last sent text comes back into the box |
| Phone killed / swiped away | PC device list clears in **5.5 s** |
| PC responsiveness | `/api/state` answers in **~4 ms**; no pywebview error storm |
| Pairing-code dialog | Custom rounded dialog, auto-connects at 4 digits, shakes on short input |
| Chinese input | Whole Chinese sentences arrive identical in the target window |
| Emoji / accented characters | Identical |

Known limitations:

- Multiple phones are injected in arrival order; there is no per-device caret model.
- The app talks plain HTTP inside your LAN; do not expose it to the internet.

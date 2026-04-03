# <img src="assets/RyujinxLauncherPNG.png" alt="Ryujinx Launcher Logo" width="24"> Ryujinx Launcher

***Version 1.0.1***

# <img src="https://repository-images.githubusercontent.com/1152064244/0948360e-bad3-48bb-be30-f2db1aeb4d71" alt="Ryujinx Launcher">
---

**A controller-first configuration interface for Ryujinx.**

Ryujinx Launcher is standalone middleware designed to eliminate the Keyboard and Mouse dependency in HTPC and Couch Gaming setups. It solves the frustration of shifting controller IDs by allowing you to visually assign physical controllers to Player Slots (1-8) using only a gamepad immediately before launch.

With features like hot-plug detection and a controller-based "Kill Combo" for exiting, it maintains complete immersion by removing the need to ever reach for a mouse or keyboard to fix configs or close the emulator.

**Note:** This project is a **companion utility/launcher**. It does not replace, fork, or modify the original Ryujinx emulator; it is intended to be used alongside it to streamline the input configuration process.

---

## Why use Ryujinx Launcher?
**No More Controller Shuffling:** Fixed the frustration of shifting controller IDs. If your Bluetooth controller connects in a different order, you can re-map it in seconds using only your gamepad.

**Total Immersion:** Designed specifically for HTPCs, Handheld PCs (Steam Deck/ROG Ally), and Couch Gaming where reaching for a mouse is a literal chore.

**The "Emergency Exit":** Beyond just launching, it adds a controller-based "Kill Combo." If Ryujinx hangs or you're done playing, you can force-close the emulator without ever leaving your seat.

**Visual & Intuitive:** Features a high-contrast side-rail UI with persistent pastel color-coding so you always know which controller belongs to which player at a glance.

**Verified on Windows 11 and Ubuntu 24.04 (VM). Tested with Ryujinx versions v1.1.1403 through v1.3.3, including Canary builds v1.3.205 and v1.3.252.**

---

## ⚠️ Important Usage Note
While you *can* run this launcher directly to set up your controllers before launching Ryujinx, **game selection will still require a mouse to navigate.**

**The ideal use cases:** 
1) **Middleware**: Use this launcher as Middleware for frontends like **Playnite, Moonlight, Artemis**. When used this way, the frontend handles game selection, and this launcher handles the controller setup, creating a seamless, mouse-free experience from start to finish.
2) **Drop-in Replacement**: This launcher works as a direct replacement for any script, shortcut, command line argument or any other frontend that supports custom emulator paths. Wherever you currently use: `Ryujinx.exe <GamePath>`. You can simply replace it with: `RyujinxLauncher.exe <GamePath>`

---

## ✨ Features

* **Gamepad-First UI:** Assign up to 8 controllers without touching a keyboard or mouse.
* **Visual Identity:** Controllers are assigned persistent, unique pastel colors for easy identification.
* **Side-Rail Interface:** Clean, high-contrast UI with visual indicators for active status.
* **Hot-Plug Support:** Connect or disconnect controllers in real-time with automatic reconnection.
* **Emergency Kill Combo:** Hold **Back** + **L** + **R** (Select + LB + RB) on *any* connected controller to force-kill the emulator if it freezes.
* **Smart Persistence:** Uses HID paths to remember specific controllers even if they reconnect in a different order.
* **Frontend Ready:** Seamlessly passes command-line arguments (Playnite, Moonlight, Artemis).
* **Portable:** Single-file EXE with embedded assets.

---

## 🎮 Controls

| Action | Button (Xbox/Generic) |
| :--- | :--- |
| **Assign Player** | `Ⓐ` Button |
| **Remove Player** | `Ⓑ` Button |
| **Launch Game/Ryujinx** | `☰` Button |
| **Exit Launcher** | `⧉` |
| **Force Kill Emulator** | Hold `⧉` + `LB` + `RB` (approx. 1 sec) |

---

## 🚀 Installation & Setup

### 1. Standard Method (Recommended)

Simply place `RyujinxLauncher.exe` inside your main Ryujinx directory (the same folder where `Ryujinx.exe` is located).

```text
C:\Games\Ryujinx\
    ├── Ryujinx.exe
    ├── RyujinxLauncher.exe  <-- Place here
    ├── Ryujinx.SDL2.Common.dll.config
    └── SDL2.dll

```
### 2. Advanced Method (Custom Path)

If you prefer to keep the launcher in a different folder than your emulator, you can manually link them:

1. Create a new text file named `RyujinxPath.config` in the same folder as the launcher.
    - Important: You must delete the .txt extension. The final file name must be exactly `RyujinxPath.config` (not `RyujinxPath.config.txt`).
2. Open it and paste the full path to your Ryujinx folder inside.
3. Save the file.

Example `RyujinxPath.config` content: `D:\emulators\Ryujinx`

**⚠️ Warning**: If you are unsure what this means, please use the **Standard Method above**. This step is only for users who need a specific custom folder structure.

---

## 🚧 Testing & Compatibility Status

- **Supported:** Stable **v1.1.1403**, **v1.3.x**, and Canary builds **v1.3.x**.

| Platform | Status | Tested Versions |
| :--- | :--- | :--- |
| **Windows 11** | ✅ **Verified** | **Old Stable:** v1.1.1403 <Br>**Stable:** v1.3.3 / v1.3.2 / v1.3.1 <br>**Canary:** v1.3.x |
| **Windows 10** | ✅ Should Work | *Not explicitly tested, but architecture is identical.* |
| **macOS 13+** | ⚠️ Untested | *Need testers!* |
| **Linux** |  ✅ **Basic test(VM)** | **Old Stable:** v1.1.1403 <Br>**Stable:** v1.3.3 / v1.3.2 / v1.3.1 <br>**Canary:** v1.3.x <Br>*Need testers!* |

---
## 🤝 Integration Guide

### Playnite

This launcher is designed to replace the default executable in Playnite.

1. Open Playnite and go to **Library > Configure Emulators**.
2. Select **Ryujinx**.
3. Add Custom profile.
4. Click **General**.
5. Ensure the following fields have the proper values:
    1. **Executable**:`<RyujinxLauncher Path>\RyujinxLauncher.exe`.
    2. **Arguments**:`"{ImagePath}"`
    3. **Working Directory**: `"{EmulatorDir}"`
    4. **Tracking Mode**: `Default`
    5. For **Supported Platform(s)** & **Supported File Types** refer to the default profile.
6. Remove any previously added Ryujinx games from your library. Then, **Rescan your library** using this new profile to re-import your games with the correct launcher settings.


### Moonlight/Artemis & Sunshine/Apollo (Streaming)

Perfect for streaming to TV or mobile devices.

1. Open Sunshine Web GUI.
2. Add a new **Application**.
3. **Application Name**: Game Name
4. **Command**: `"<Path of Ryujinx>/RyujinxLauncher.exe" "<Path of Game file (.nsp/.xci/.nro/.nca)>`
    * *Example:* `"D:\emulators\Ryujinx\RyujinxLauncher.exe" "D:\Roms\GameName.xci"`
5. **Working Directory**: The folder containing the launcher.
    * *Example:* `"D:\emulators\Ryujinx\"`
6. Now, when you launch via Moonlight, you can use the controller to set up inputs before the game loads.

---

## 🛠️ Building from Source

If you wish to modify the code or build the executable yourself.

### Prerequisites
* Python 3.10+
* Install dependencies: `pip install -r requirements.txt`

### Directory Structure
Ensure your source folder looks like this before building:

```text
ProjectRoot/
├── assets/
│   ├── RyujinxLauncherIcon.ico
│   └── RyujinxLauncherPNG.png
├── src/
│   └── RyujinxLauncher.py
└── requirements.txt
```

### Build Command

Run this command from the ProjectRoot terminal to create a standalone EXE/BIN/APP with bundled assets:

### Windows

`pyinstaller --noconsole --onefile --name "RyujinxLauncher" --icon="assets\RyujinxLauncherIcon.ico" --add-data "assets;assets" --collect-all customtkinter src\RyujinxLauncher.py`

### MacOS

`pyinstaller --noconsole --onefile --name "RyujinxLauncher" --icon="assets/RyujinxLauncherIcon.ico" --add-data "assets:assets" --collect-all customtkinter src/RyujinxLauncher.py`

### Linux

`pyinstaller --noconsole --onefile --name "RyujinxLauncher" --icon="assets/RyujinxLauncherPNG.png" --add-data "assets:assets" --collect-all customtkinter src/RyujinxLauncher.py`

The resulting `RyujinxLauncher` executable will be in the `dist/` folder.

---

## 📜 License

**CC BY-NC 4.0 (Attribution-NonCommercial 4.0 International)**

You are free to:
* **Share** — copy and redistribute the material in any medium or format.
* **Adapt** — remix, transform, and build upon the material.

Under the following terms:
* **Attribution** — You must give appropriate credit.
* **NonCommercial** — You may not use the material for commercial purposes.

---

## ❓ FAQ

   **Q: Does this replace Ryujinx?**  
   A: No, it's a companion launcher. You still need Ryujinx installed.

   **Q: Will this work with other emulators?**  
   A: No, it's specifically designed for Ryujinx's config format.

   **Q: Does this work with LaunchBox/RetroBat/EmulationStation?**  
   A: Yes! Just point the emulator path to `RyujinxLauncher.exe` instead of `Ryujinx.exe`.

---

## 🔧 Troubleshooting

**Controllers Not Detected**  
✅ Ensure SDL2.dll/SDL3.dll is in the same folder as Ryujinx.exe  
✅ Try unplugging and reconnecting controllers  
✅ Check Windows Device Manager for "Unknown USB Device"

**Launcher Crashes on Start**  
✅ Missing Config.json → Launch Ryujinx normally once to generate it  
✅ Missing SDL2.dll/SDL3.dll → Ensure it's in the same folder as Ryujinx.exe

**Kill Combo Not Working**  
✅ Hold all 3 buttons (⧉ + LB + RB) for ~1 second  
✅ Works on ANY connected controller, not just Player 1

**UI Too Small/Large**  
✅ The launcher auto-scales based on resolution  
✅ If scaling is wrong: Windows Settings → Display → Scale → 100%

---

## ⚠️ Disclaimer

This software is a utility tool intended for use with legally obtained software.
* The author (Artomos) does not condone piracy.
* This project is not affiliated with, endorsed by, or connected to the Ryujinx Team or any console manufacturers.

---

## 📞 Contact

**Author:** Artomos

**Email:** artomos.main@gmail.com
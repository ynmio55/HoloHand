# HoloHand

Real-time hand gesture tracking and interactive camera effects built with **Python, MediaPipe, OpenCV and NumPy**.

## Features
- Tracks up to **two hands** using a webcam
- Neon-green hand bounding boxes with position smoothing
- Hand landmark overlay and live FPS HUD
- Hold a **pinch** for 0.55 seconds to toggle a negative-camera filter
- **Fist** activates a spotlight centered on the hand
- **Peace sign** activates edge vision
- **Open palm** displays the normal tracking overlay
- Keyboard screenshot capture, mirror toggle and reset

> This is an original implementation inspired by the reference concept, not an exact reproduction of every effect in the reference video. Performance depends on the webcam, lighting and hardware.

## Requirements
- Python **3.11 or 3.12** (recommended: 3.11)
- A webcam
- Windows or Linux (including Fedora)
- A desktop session capable of opening an OpenCV window

## Installation

### Windows (PowerShell)
```powershell
git clone https://github.com/ynmio55/HoloHand.git
cd HoloHand
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe main.py` without activating the environment.

### Fedora Linux
Install Python 3.11 and Git using the system package manager if not already present.

```bash
git clone https://github.com/ynmio55/HoloHand.git
cd HoloHand
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If OpenCV cannot load the camera or window, ensure that you are running a graphical desktop session and that camera access is enabled. Install missing system graphical libraries through Fedora's package manager as needed.

## Controls

| Gesture or key | Action |
|---|---|
| Open palm | Neon tracking overlay |
| Pinch thumb and index, hold | Toggle negative filter |
| Fist | Spotlight |
| Peace (index + middle raised) | Edge vision |
| Q or Esc | Quit |
| M | Toggle camera mirroring |
| S | Save screenshot in `screenshots/` |
| R | Disable negative effect |

## Options

```bash
python main.py --camera 1
python main.py --width 640 --height 480 --max-hands 1
```

Use `--camera 1` if your webcam isn't available as camera 0. At low light or when fingers overlap, gestures may be misclassified. A steady, well-lit setup improves results.

## Notes
- All camera processing runs **locally**. The program does not upload video.
- The `screenshots/` directory is excluded from Git.
- On recent Fedora releases, the default Python may be newer than the MediaPipe-compatible version. Prefer Python 3.11 as above.
- The implementation is a working codebase but has not yet been validated against your own webcam/hardware.

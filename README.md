# Hikvision-SDK-Python

A lightweight Python wrapper around the **Hikvision HCNetSDK** for communicating with Hikvision NVRs and IP cameras.

The project provides a simple Python interface for:

* 📷 Capture JPEG frames
* 🎥 Live video streaming
* 🔍 Scan active NVR channels
* 🗺 Build Camera IP → Channel mapping
* 🔄 Multi-NVR session management
* ⚡ High-performance frame acquisition for AI pipelines

Designed for production computer vision systems where thousands of frame capture requests must be handled efficiently.

---

## Features

* Single login per NVR with session reuse
* Multi-NVR support
* Thread-safe SDK wrapper
* Capture frames directly into memory
* Capture frames through JPEG files
* Live preview / RealPlay streaming
* Automatic camera channel discovery
* Camera IP → Channel lookup
* Simple Python API
* Production-ready architecture

---

# Repository Structure

```text
.
├── app/
│   ├── config/
│   │   ├── config.cfg
│   │   ├── camera_channel_mapping.json # Run nvr_camera_channel_mapping.py to generate this file.
│   │   └── config.py
│   │
│   ├── examples/
│   │   └── playback_extractor.py
│   │
│   ├── gui_images/
│   │   └── nvr_playback_downloader.png
|   |
│   ├── hikvision_sdk_package/
│   │   ├── bin/
│   │   │   ├── ClientDemoDll/
│   │   │   ├── HCNetSDKCom/
│   │   │   ├── HCNetSDK.dll
│   │   │   ├── PlayCtrl.dll
│   │   │   └── ...
│   │   │
│   │   ├── sdk_wrapper.py
│   │   ├── hikvision_sdk.py
│   │   └── nvr_camera_channel_mapping.py
│   │
│   └── utils/
│       └── helper_functions.py
│
├── run_examples/
│   └── run_playback_extractor.bat
│
├── LICENSE
├── README.md
├── requirements.txt
└── .gitignore
```

---

# Installation

Clone the repository

```bash
git clone https://github.com/Maqbool-Ahmed-1208/Hikvision-SDK-Python.git

cd Hikvision-SDK-Python
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Edit

```text
app/config/config.cfg
```

Example

```ini
[PATHS]
ROOT = Hikvision-SDK-Python # Modify it, if needed.
HCNetSDK = app\hikvision_sdk_package\bin\HCNetSDK.dll
CHANNEL_MAPPING_PATH = app\config\camera_channel_mapping.json

[NVR]
IP = 192.168.100.10
PORT = 8000
USERNAME = admin
PASSWORD = your_password
```

---

# Project Modules

| Module                          | Description                 |
| ------------------------------- | --------------------------- |
| `sdk_wrapper.py`                | Main SDK wrapper            |
| `hikvision_sdk.py`              | SDK features                |
| `nvr_camera_channel_mapping.py` | Camera IP ↔ Channel mapping |
| `helper_functions.py`           | Utility functions           |
| `playback_extractor.py`         | GUI based Playback extractor|
| `config.py`                     | Configuration loader        |

---

# Usage

## 1. Build Camera Channel Mapping

Builds a lookup table mapping camera IP addresses to Hikvision channel numbers.

```python
from app.config.config import AppConfig
from app.hikvision_sdk_package.nvr_camera_channel_mapping import (
    build_camera_channel_mapping,
    get_camera_channel,
)

cfg = AppConfig()

ip = cfg.get("NVR", "IP")
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")

build_camera_channel_mapping(
    nvr_ip=ip,
    username=username,
    password=password,
)

channel = get_camera_channel(
    nvr_ip=ip,
    camera_ip="192.168.100.116",
)

print(channel)
```

---

## 2. Scan Active Channels

Lists available channels on the NVR.

```python
import cv2
from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
cfg = AppConfig()

ip = cfg.get("NVR","IP")
port = cfg.get("NVR", "PORT", cast=int)
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip,
        "port": port,
        "username": username,
        "password": password
    }]
)

print("Session established.")

hik.scan_channels(ip, 1, 64)
```

---

## 3. Live View (RealPlay)

Display live video frames from a camera channel.

```python
import cv2
from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
cfg = AppConfig()

ip = cfg.get("NVR","IP")
port = cfg.get("NVR", "PORT", cast=int)
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip,
        "port": port,
        "username": username,
        "password": password
    }]
)

print("Session established.")

for frame in hik.live_stream(ip, 33):

    cv2.imshow("Live", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cv2.destroyAllWindows()

hik.close()
```

---

## 4. Play Back Video Downloader

Download recorded video from a camera channel.

```python
import cv2
from app.config.config import AppConfig
cfg = AppConfig()

ip = cfg.get("NVR", "IP")
port = cfg.get("NVR", "PORT", cast=int)
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")
root_path = cfg.get("PATHS", "ROOT")

print(f"""
        NVR IP: {ip}\n
        NVR PORT: {port}\n
        NVR USERNAME: {username}\n
        NVR PASSWORD: {password}\n
        """)

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip,
        "port": port,
        "username": username,
        "password": password
    }]
)

print("Session established.")

# --- download a recording by time range (no client-side decode) ---
channel = 33

start_time = "09:00"   # "hh:mm" -> paired with `date` below
end_time = "09:05"
date = "27-07-2026"    # "dd-mm-yyyy" -> pull recordings from this day
save_path = os.path.join(
    root_path,
    "nvr_downloads",
    f"test_channel{channel}_{date.replace('-', '')}.mp4"
)

handle = hik.get_recording(
    nvr_ip=ip,
    channel=channel,
    start_time=start_time,
    end_time=end_time,
    date=date,
    save_path=save_path
)

if handle < 0:
    print("Failed to start recording download.")
else:
    print(f"Download started, handle={handle}. Waiting for completion...")

    # poll manually instead of using wait_for_recording(), just to show
    # the progress values as they come in
    while True:
        percent, path = hik.get_download_progress(ip, channel)

        if percent < 0:
            print(f"Download error/stopped, pos={percent}")
            break

        print(f"Download progress: {percent}%")

        if percent >= 100:
            hik.stop_download(ip, channel)
            print(f"Download complete -> {path}")
            break

        time.sleep(1)

hik.close()
print("Session closed.")

```
<p align="center">
  <img src="app\gui_images\nvr_playback_downloader.png" width="800">
</p>

---

## 5. Capture Frame (Memory Buffer)

Captures a frame directly into a NumPy array without saving to disk.

```python
import cv2
from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
cfg = AppConfig()

ip = cfg.get("NVR","IP")
port = cfg.get("NVR", "PORT", cast=int)
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip,
        "port": port,
        "username": username,
        "password": password
    }]
)

print("Session established.")

ret, frame = hik.capture_frame_buffer(
    nvr_ip=ip,
    channel=33,
)

if ret:

    print(frame.shape)

    cv2.imshow("Captured", frame)

    cv2.waitKey(0)

hik.close()
```

---

## 6. Capture Frame (JPEG File)

Captures a JPEG image using the SDK and loads it into memory.

```python
import cv2
from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
cfg = AppConfig()

ip = cfg.get("NVR","IP")
port = cfg.get("NVR", "PORT", cast=int)
username = cfg.get("NVR", "USERNAME")
password = cfg.get("NVR", "PASSWORD")

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip,
        "port": port,
        "username": username,
        "password": password
    }]
)

print("Session established.")

ret, frame = hik.capture_frame_file(
    nvr_ip=ip,
    channel=33,
)

if ret:

    print(frame.shape)

    cv2.imshow("Captured", frame)

    cv2.waitKey(0)

hik.close()
```

---

# Multi-NVR Support

The SDK automatically manages independent sessions for multiple NVRs.

```python
import cv2
from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
cfg = AppConfig()

ip_1 = cfg.get("NVR_1","IP")
port_1 = cfg.get("NVR_1", "PORT", cast=int)
username_1 = cfg.get("NVR_1", "USERNAME")
password_1 = cfg.get("NVR_1", "PASSWORD")

ip_2 = cfg.get("NVR_2","IP")
port_2 = cfg.get("NVR_2", "PORT", cast=int)
username_2 = cfg.get("NVR_2", "USERNAME")
password_2 = cfg.get("NVR_2", "PASSWORD")

hik = HikvisionSDK(
    nvrs=[{
        "ip": ip_1,
        "port": port_1,
        "username": username_1,
        "password": password_1
    },
    {
        "ip": ip_2,
        "port": port_2,
        "username": username_2,
        "password": password_2
    }]
)

print("Session established.")

hik.capture_frame_file(
    nvr_ip=ip_1,
    channel=5,
)

hik.capture_frame_buffer(
    nvr_ip=ip_2,
    channel=5,
)
```

Each NVR maintains:

* Independent login session
* Session reuse
* Thread-safe capture
* Automatic reconnect

---

# Typical AI Pipeline

```text
               NVR
                │
                ▼
            Login Once
                │
                ▼
            Session Cache
                │
        ├───────────────┐
        │               │
    Capture        Live Stream
        │               │
        ▼               ▼
    OpenCV Frame   NumPy Frame
        ├───────│───────│
                │
                ▼      
YOLO / OCR / Face Recognition / AI Models
```

---

# Requirements

* Python 3.10+
* Windows/Linux
* Hikvision HCNetSDK
* OpenCV
* NumPy

---

# Acknowledgements

This project is built on the official Hikvision HCNetSDK.

SDK Download:

https://www.hikvision.com/us-en/support/download/sdk/

---

# License

This project is released under the MIT License.

---

# Author

**Maqbool Ahmed**

* AI Engineer
* Computer Vision
* Generative AI
* LLM Applications
* Production AI Systems

GitHub: [https://github.com/Maqbool-Ahmed-1208](https://github.com/Maqbool-Ahmed-1208)

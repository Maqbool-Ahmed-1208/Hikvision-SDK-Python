# Hikvision-SDK-Python

A lightweight Python wrapper around the Hikvision HCNetSDK for interacting with Hikvision NVRs and IP cameras.

The library provides a simple interface for:

- 📷 Capture JPEG frames directly from cameras
- 🎥 Live video streaming
- 🔍 Scan active NVR channels
- 🔄 Multi-NVR session management
- ⚡ High-performance frame acquisition using the native Hikvision SDK

---

# Features

- Native Hikvision HCNetSDK integration
- Single login reused across multiple capture requests
- Supports multiple NVRs simultaneously
- Thread-safe frame capture
- Live preview using OpenCV
- Capture frames directly into memory
- Capture frames through temporary JPEG files
- Automatic SDK initialization and cleanup
- Channel scanning utilities

---

# Project Structure

```
Hikvision-SDK-Python
│
├── app
│   ├── config
│   │   ├── config.cfg
│   │   └── config.py
│   │
│   ├── hikvision_sdk_package
│   │   ├── bin
│   │   │   ├── HCNetSDK.dll
│   │   │   ├── HCNetSDKCom
│   │   │   ├── ClientDemoDll
│   │   │   └── ...
│   │   │
│   │   ├── hikvision_sdk.py
│   │   └── nvr_camera_channel_mapping.py
│   │
│   └── utils
│       └── helper_functions.py
│
├── requirements.txt
├── LICENSE
└── README.md
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

# Requirements

- Python 3.10+
- Windows/Linux
- Hikvision HCNetSDK
- OpenCV
- NumPy

The required SDK binaries are already included inside

```
app/hikvision_sdk_package/bin/
```

---

# Configuration

Edit

```
app/config/config.cfg
```

Example

```ini
[NVR]
IP = 192.168.100.10
PORT = 8000
USERNAME = admin
PASSWORD = your_password
```

---

# Initialize

```python
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK

hik = HikvisionSDK()
```

---

# Scan Active Channels

```python
hik.scan_channels(
    nvr_ip="192.168.100.10",
    start_channel=1,
    end_channel=64
)
```

Example output

```
Channel 1   Active
Channel 2   Active
Channel 3   Offline
...
```

---

# Live Stream

```python
import cv2

for frame in hik.live_stream(
    nvr_ip="192.168.100.10",
    channel=33
):
    cv2.imshow("Live", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cv2.destroyAllWindows()
hik.close()
```

Press **ESC** to stop streaming.

---

# Capture Frame (Memory Buffer)

Returns a NumPy image without writing to disk.

```python
ret, frame = hik.capture_frame_buffer(
    nvr_ip="192.168.100.10",
    channel=33
)

if ret:
    print(frame.shape)
```

Display the image

```python
cv2.imshow("Frame", frame)
cv2.waitKey(0)
```

---

# Capture Frame (JPEG File)

Captures a JPEG using the SDK and loads it into OpenCV.

```python
ret, frame = hik.capture_frame_file(
    nvr_ip="192.168.100.10",
    channel=33
)

if ret:
    cv2.imshow("Frame", frame)
    cv2.waitKey(0)
```

---

# Multi-NVR Support

The SDK maintains independent sessions for each NVR.

```python
hik.capture_frame_buffer(
    nvr_ip="192.168.100.10",
    channel=12
)

hik.capture_frame_buffer(
    nvr_ip="192.168.100.20",
    channel=8
)
```

Sessions are automatically reused, avoiding repeated login operations.

---

# Supported Functions

| Function | Description |
|----------|-------------|
| `scan_channels()` | Detect active channels |
| `capture_frame_buffer()` | Capture image directly into memory |
| `capture_frame_file()` | Capture image using temporary JPEG |
| `live_stream()` | Real-time video preview |
| `close()` | Logout and release SDK resources |

---

# Example

```python
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
import cv2

hik = HikvisionSDK()

ret, frame = hik.capture_frame_buffer(
    nvr_ip="192.168.100.10",
    channel=33
)

if ret:
    cv2.imshow("Frame", frame)
    cv2.waitKey(0)

hik.close()
```

---

# Performance Notes

- One login per NVR
- Session reuse across requests
- Thread-safe frame capture
- Supports concurrent access to multiple NVRs
- Designed for high-throughput AI and computer vision pipelines

---

# Dependencies

- OpenCV
- NumPy
- ctypes
- Hikvision HCNetSDK

---

# License

This project is licensed under the MIT License.

---

# Acknowledgements

This project is built on the official Hikvision HCNetSDK.

SDK Download:

https://www.hikvision.com/us-en/support/download/sdk/

---

## Author

**Maqbool Ahmed**

- AI Engineer
- Computer Vision
- Generative AI
- Industrial AI Systems

GitHub:

https://github.com/Maqbool-Ahmed-1208
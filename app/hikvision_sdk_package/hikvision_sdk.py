import os, sys
import cv2
import time
import tempfile
import threading
import numpy as np
from ctypes import *

class NET_DVR_DEVICEINFO_V30(Structure):
    _fields_ = [
        ("sSerialNumber", c_byte * 48),
        ("byAlarmInPortNum", c_byte),
        ("byAlarmOutPortNum", c_byte),
        ("byDiskNum", c_byte),
        ("byDVRType", c_byte),
        ("byChanNum", c_byte),
        ("byStartChan", c_byte),
        ("byAudioChanNum", c_byte),
        ("byIPChanNum", c_byte),
        ("byZeroChanNum", c_byte),
        ("byMainProto", c_byte),
        ("bySubProto", c_byte),
        ("bySupport", c_byte),
        ("bySupport1", c_byte),
        ("bySupport2", c_byte),
        ("wDevType", c_ushort),
    ]


class NET_DVR_JPEGPARA(Structure):
    _fields_ = [
        ("wPicSize", c_ushort),
        ("wPicQuality", c_ushort),
    ]


# ---------------------------------------------------------------------------
# Live view / real play structures — mirrors the C# reference
# (CHCNetSDK.NET_DVR_PREVIEWINFO / NET_DVR_RealPlay_V40 / NET_DVR_StopRealPlay)
# ---------------------------------------------------------------------------

class NET_DVR_PREVIEWINFO(Structure):
    _fields_ = [
        ("lChannel", c_long),           # lChannel Preview device channel
        ("dwStreamType", c_uint),       # 0-main stream,1-sub stream,2-third stream,3-transcode stream
        ("dwLinkMode", c_uint),         # 0-TCP,1-UDP,2-multicast,3-RTP,4-RTP/RTSP,5-RSTP/HTTP
        ("hPlayWnd", c_void_p),         # window handle for local rendering (None/0 for headless)
        ("bBlocked", c_uint),           # 0-non-blocking,1-blocking
        ("bPassbackRecord", c_uint),
        ("byPreviewMode", c_byte),
        ("byStreamID", c_byte * 32),
        ("byProtoType", c_byte),
        ("byRes1", c_byte),
        ("byVideoCodingType", c_byte),
        ("dwDisplayBufNum", c_uint),
        ("byNPQMode", c_byte),
        ("byRes", c_byte * 215),
    ]


# void CALLBACK RealDataCallBack(LONG lRealHandle, DWORD dwDataType, BYTE *pBuffer, DWORD dwBufSize, void* dwUser)
REALDATACALLBACK = WINFUNCTYPE(
    None, c_long, c_uint, POINTER(c_ubyte), c_uint, c_void_p
)

# --- PlayCtrl.dll (PlayM4_*) decode bindings ---
# void CALLBACK DecCBFun(int nPort, char *pBuf, int nSize, FRAME_INFO *pFrameInfo, void *nUser, int nReserved)
# We use the simpler display callback variant which hands back a ready RGB24
# buffer: void CALLBACK DispCBFun(int nPort, char *pBuf, int nSize, int nWidth,
#                                  int nHeight, int nStamp, int nType, int nReserved0, int nReserved1)
DISPLAYCBFUN = WINFUNCTYPE(
    None, c_long, POINTER(c_ubyte), c_long, c_long, c_long,
    c_long, c_long, c_long, c_long
)

STREAME_REALTIME = 0  # PlayM4_SetStreamOpenMode mode: live/realtime stream


class HikvisionSDK:

    def __init__(
        self,
        nvrs: list,
        sdk_path=r"app\config\hikvision_sdk_package\bin\HCNetSDK.dll"
    ):

        self.sdk_path = sdk_path
        self.sdk = self._load_sdk()

        # PlayCtrl.dll lives next to HCNetSDK.dll — used to decode the raw
        # stream data handed back by NET_DVR_RealPlay_V40 into actual frames.
        self.play_ctrl_path = os.path.join(
            os.path.dirname(sdk_path), "PlayCtrl.dll"
        )
        self.play_ctrl = self._load_play_ctrl()

        if not self.sdk.NET_DVR_Init():
            raise RuntimeError("SDK initialization failed")

        self.sessions = {}
        # keep strong refs to callback closures so they aren't GC'd
        self._live_callbacks = {}
        self._display_callbacks = {}

        for nvr in nvrs:

            user_id = self._login(
                ip=nvr["ip"],
                port=nvr["port"],
                username=nvr["username"],
                password=nvr["password"]
            )

            self.sessions[nvr["ip"]] = {
                "user_id": user_id,
                "ip": nvr["ip"],
                "port": nvr["port"],
                "username": nvr["username"],
                "password": nvr["password"],
                "lock": threading.RLock(),
                "jpeg_buffer_size": 8 * 1024 * 1024,
                "jpeg_buffer": (
                    c_ubyte * (8 * 1024 * 1024)
                )(),
                # live view state: channel -> {"handle", "port", "cap",
                #   "frame_lock", "latest_frame"}
                "live": {}
            }

            print(
                f"[SDK] Connected "
                f"{nvr['ip']} "
                f"user_id={user_id}"
            )

    def _load_sdk(self):

        sdk = WinDLL(self.sdk_path)

        sdk.NET_DVR_Init.restype = c_bool

        sdk.NET_DVR_GetLastError.restype = c_ulong

        sdk.NET_DVR_Logout.argtypes = [c_long]

        sdk.NET_DVR_Login_V30.argtypes = [
            c_char_p,
            c_ushort,
            c_char_p,
            c_char_p,
            POINTER(NET_DVR_DEVICEINFO_V30)
        ]
        sdk.NET_DVR_Login_V30.restype = c_long

        sdk.NET_DVR_CaptureJPEGPicture.argtypes = [
            c_long,
            c_long,
            POINTER(NET_DVR_JPEGPARA),
            c_char_p
        ]
        sdk.NET_DVR_CaptureJPEGPicture.restype = c_bool

        sdk.NET_DVR_CaptureJPEGPicture_NEW.argtypes = [
            c_long,                     # lUserID
            c_long,                     # lChannel
            POINTER(NET_DVR_JPEGPARA),  # lpJpegPara
            POINTER(c_ubyte),           # sJpegPicBuffer
            c_uint,                     # dwPicSize
            POINTER(c_uint)             # lpSizeReturned
        ]
        sdk.NET_DVR_CaptureJPEGPicture_NEW.restype = c_bool

        # --- live view / real play bindings (mirrors C# reference) ---
        sdk.NET_DVR_RealPlay_V40.argtypes = [
            c_long,                        # lUserID
            POINTER(NET_DVR_PREVIEWINFO),  # lpPreviewInfo
            REALDATACALLBACK,              # fRealDataCallBack_V30 (nullable)
            c_void_p                       # pUser
        ]
        sdk.NET_DVR_RealPlay_V40.restype = c_long

        sdk.NET_DVR_StopRealPlay.argtypes = [c_long]
        sdk.NET_DVR_StopRealPlay.restype = c_bool

        return sdk

    def _load_play_ctrl(self):

        if not os.path.exists(self.play_ctrl_path):
            print(
                f"[SDK] PlayCtrl.dll not found at {self.play_ctrl_path} "
                f"— decoded live_stream() will be unavailable until it's present."
            )
            return None

        pc = WinDLL(self.play_ctrl_path)

        pc.PlayM4_GetPort.argtypes = [POINTER(c_long)]
        pc.PlayM4_GetPort.restype = c_bool

        pc.PlayM4_FreePort.argtypes = [c_long]
        pc.PlayM4_FreePort.restype = c_bool

        pc.PlayM4_SetStreamOpenMode.argtypes = [c_long, c_uint]
        pc.PlayM4_SetStreamOpenMode.restype = c_bool

        pc.PlayM4_OpenStream.argtypes = [
            c_long, POINTER(c_ubyte), c_uint, c_uint
        ]
        pc.PlayM4_OpenStream.restype = c_bool

        pc.PlayM4_CloseStream.argtypes = [c_long]
        pc.PlayM4_CloseStream.restype = c_bool

        pc.PlayM4_InputData.argtypes = [c_long, POINTER(c_ubyte), c_uint]
        pc.PlayM4_InputData.restype = c_bool

        pc.PlayM4_Play.argtypes = [c_long, c_void_p]
        pc.PlayM4_Play.restype = c_bool

        pc.PlayM4_Stop.argtypes = [c_long]
        pc.PlayM4_Stop.restype = c_bool

        pc.PlayM4_SetDisplayCallBack.argtypes = [c_long, DISPLAYCBFUN]
        pc.PlayM4_SetDisplayCallBack.restype = c_bool

        pc.PlayM4_GetLastError.argtypes = [c_long]
        pc.PlayM4_GetLastError.restype = c_ulong

        return pc

    def _login(
        self,
        ip,
        port,
        username,
        password
    ):

        device_info = NET_DVR_DEVICEINFO_V30()

        user_id = self.sdk.NET_DVR_Login_V30(
            ip.encode(),
            port,
            username.encode(),
            password.encode(),
            byref(device_info)
        )

        if user_id < 0:
            err = self.sdk.NET_DVR_GetLastError()
            raise RuntimeError(
                f"Login failed for {ip} | ERR={err}"
            )

        print(
            f"[SDK] {ip} device info "
            f"| byStartChan={device_info.byStartChan} "
            f"| byChanNum={device_info.byChanNum} "
            f"| byIPChanNum={device_info.byIPChanNum} "
            f"| byZeroChanNum={device_info.byZeroChanNum} "
            f"| byDiskNum={device_info.byDiskNum}"
        )

        return user_id

    def _normalize_nvr_ip(self, nvr_ip: str):

        # Exact match first
        if nvr_ip in self.sessions:
            return nvr_ip

        # Remove dots and compare
        clean = nvr_ip.replace(".", "")

        for session_ip in self.sessions:

            if session_ip.replace(".", "") == clean:
                return session_ip

        raise RuntimeError(
            f"NVR not connected: {nvr_ip}"
        )

    def _get_session(self, nvr_ip):

        normalized_ip = self._normalize_nvr_ip(nvr_ip)

        return self.sessions[normalized_ip]

    def capture_frame(self, channel: int):  # BASIC
        if channel is None:
            return False, None
        jpeg = NET_DVR_JPEGPARA()
        jpeg.wPicSize = 0xFF
        jpeg.wPicQuality = 0

        tmp_dir = os.path.join(
            tempfile.gettempdir(),
            r"channels_frames"
        )
        os.makedirs(tmp_dir, exist_ok=True)

        tmp_file = os.path.join(
            tmp_dir,
            f"ch_{channel}.jpg"
        )

        ok = self.sdk.NET_DVR_CaptureJPEGPicture(
            self.user_id,
            channel,
            byref(jpeg),
            tmp_file.encode("utf-8")
        )

        if not ok:
            return False, None

        frame = cv2.imread(tmp_file)

        try:
            os.remove(tmp_file)
        except Exception:
            pass

        return True, frame

    def capture_frame_file(
        self,
        nvr_ip: str,
        channel: int
    ):

        session = self._get_session(nvr_ip)

        with session["lock"]:

            jpeg = NET_DVR_JPEGPARA()
            jpeg.wPicSize = 0xFF
            jpeg.wPicQuality = 0

            tmp_dir = r"channels_frames"
            os.makedirs(tmp_dir, exist_ok=True)

            tmp_file = os.path.join(
                tmp_dir,
                f"{nvr_ip.replace('.','')}_"
                f"{channel}_"
                f"{threading.get_ident()}.jpg"
            )

            ok = self.sdk.NET_DVR_CaptureJPEGPicture(
                session["user_id"],
                channel,
                byref(jpeg),
                tmp_file.encode()
            )

            if not ok:
                return False, None

            frame = cv2.imread(tmp_file)

            try:
                os.remove(tmp_file)
            except:
                pass

            return frame is not None, frame

    def capture_frame_buffer(
        self,
        nvr_ip: str,
        channel: int
    ):

        if channel is None:
            return False, None

        session = self._get_session(nvr_ip)

        with session["lock"]:

            jpeg = NET_DVR_JPEGPARA()
            jpeg.wPicSize = 0xFF
            jpeg.wPicQuality = 0

            returned_size = c_uint(0)

            ok = self.sdk.NET_DVR_CaptureJPEGPicture_NEW(
                session["user_id"],
                channel,
                byref(jpeg),
                session["jpeg_buffer"],
                session["jpeg_buffer_size"],
                byref(returned_size)
            )

            if not ok:

                err = self.sdk.NET_DVR_GetLastError()

                print(
                    f"[SDK] Capture failed "
                    f"| nvr={nvr_ip} "
                    f"| channel={channel} "
                    f"| err={err}"
                )

                return False, None

            np_buffer = np.frombuffer(
                session["jpeg_buffer"],
                dtype=np.uint8,
                count=returned_size.value
            )

            frame = cv2.imdecode(
                np_buffer,
                cv2.IMREAD_COLOR
            )

            return frame is not None, frame

    # -----------------------------------------------------------------
    # Live view (real play) — mirrors btnPreview_Click / RealDataCallBack
    # from the C# reference (NET_DVR_RealPlay_V40 / NET_DVR_StopRealPlay).
    #
    # NET_DVR_RealPlay_V40 opens the device-side preview stream and hands
    # raw stream data to a callback. That raw data is fed into
    # PlayCtrl.dll's PlayM4_* decoder, whose display callback returns
    # decoded RGB frames — converted to BGR numpy arrays here. Decoding
    # happens NVR-side (the stream arrives already encoded by the device;
    # PlayCtrl just decompresses it locally) — no RTSP client involved.
    #
    # Use start_real_play() / get_live_frame() / live_stream() to consume
    # frames this way.
    # -----------------------------------------------------------------

    def start_real_play(
        self,
        nvr_ip: str,
        channel: int,
        stream_type: int = 0,   # 0-main, 1-sub, 2-third, 3-transcode
        link_mode: int = 0,     # 0-TCP,1-UDP,2-multicast,3-RTP,4-RTP/RTSP,5-RTSP/HTTP
        hwnd=None,              # window handle for local rendering, None for headless
        decode: bool = True,    # decode via PlayCtrl.dll into retrievable frames
        on_data=None            # optional python callback: fn(data_type, bytes) — raw stream
    ):
        """
        Starts device-side live view via NET_DVR_RealPlay_V40, matching
        the C# btnPreview_Click flow. If `decode=True` and PlayCtrl.dll
        was loaded, raw stream data is fed into the PlayM4 decoder and
        decoded frames become available via get_live_frame() /
        live_stream() — no separate client needed.

        Returns the play handle (>=0) on success, or -1 on failure.
        """

        session = self._get_session(nvr_ip)

        with session["lock"]:

            if channel in session["live"]:
                # already streaming this channel
                return session["live"][channel]["handle"]

            port = c_long(-1)
            use_decode = decode and self.play_ctrl is not None

            if use_decode:
                if not self.play_ctrl.PlayM4_GetPort(byref(port)):
                    print(
                        f"[SDK] PlayM4_GetPort failed "
                        f"| nvr={nvr_ip} | channel={channel}"
                    )
                    use_decode = False
                else:
                    ok_mode = self.play_ctrl.PlayM4_SetStreamOpenMode(
                        port, STREAME_REALTIME
                    )
                    print(
                        f"[SDK] PlayM4_SetStreamOpenMode -> {bool(ok_mode)} "
                        f"| port={port.value}"
                    )
                    # NOTE: PlayM4_OpenStream is intentionally NOT called
                    # here with an empty buffer — it must be opened with
                    # the actual NET_DVR_SYSHEAD bytes, which only arrive
                    # via the first RealDataCallBack invocation below.

            live_entry = {
                "handle": None,
                "port": port.value if use_decode else None,
                "frame_lock": threading.Lock(),
                "latest_frame": None,
                "stream_opened": False,
                "playing": False,
                "frame_count": 0,
            }

            def _display_cb(nPort, pBuf, nSize, nWidth, nHeight,
                             nStamp, nType, nReserved0, nReserved1):
                try:
                    buf = string_at(pBuf, nSize)
                    arr = np.frombuffer(buf, dtype=np.uint8)

                    rgb_size = nWidth * nHeight * 3
                    yuv420_size = nWidth * nHeight * 3 // 2

                    if arr.size >= rgb_size:
                        # RGB24 buffer, bottom-up
                        rgb = arr[:rgb_size].reshape((nHeight, nWidth, 3))
                        bgr = cv2.cvtColor(np.flipud(rgb), cv2.COLOR_RGB2BGR)
                    elif arr.size >= yuv420_size:
                        # YV12 planar buffer (Y plane, then V, then U)
                        yuv = arr[:yuv420_size].reshape(
                            (nHeight * 3 // 2, nWidth)
                        )
                        bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_YV12)
                    else:
                        print(
                            f"[SDK] display callback: buffer too small "
                            f"({arr.size}) for {nWidth}x{nHeight} "
                            f"(need {yuv420_size} for YV12 or {rgb_size} for RGB24)"
                        )
                        return

                    with live_entry["frame_lock"]:
                        live_entry["latest_frame"] = bgr
                        live_entry["frame_count"] += 1
                        if live_entry["frame_count"] == 1:
                            print(
                                f"[SDK] first decoded frame received "
                                f"| nvr={nvr_ip} | channel={channel} "
                                f"| {nWidth}x{nHeight}"
                            )
                except Exception as disp_err:
                    print(f"[SDK] display callback error: {disp_err}")

            if use_decode:
                c_display_cb = DISPLAYCBFUN(_display_cb)
                self._display_callbacks[(nvr_ip, channel)] = c_display_cb
                ok_disp = self.play_ctrl.PlayM4_SetDisplayCallBack(port, c_display_cb)
                print(f"[SDK] PlayM4_SetDisplayCallBack -> {bool(ok_disp)}")

            preview_info = NET_DVR_PREVIEWINFO()
            preview_info.lChannel = channel
            preview_info.dwStreamType = stream_type
            preview_info.dwLinkMode = link_mode
            preview_info.hPlayWnd = c_void_p(hwnd) if hwnd else None
            preview_info.bBlocked = 1
            preview_info.dwDisplayBufNum = 1
            preview_info.byProtoType = 0
            preview_info.byPreviewMode = 0

            def _real_data_cb(lRealHandle, dwDataType, pBuffer, dwBufSize, pUser):
                if not dwBufSize:
                    return

                if not use_decode:
                    if on_data is not None:
                        try:
                            on_data(dwDataType, string_at(pBuffer, dwBufSize))
                        except Exception as cb_err:
                            print(f"[SDK] on_data callback error: {cb_err}")
                    return

                # NET_DVR_SYSHEAD == 1 -> open the stream with this header
                if dwDataType == 1 and not live_entry["stream_opened"]:
                    ok_open = self.play_ctrl.PlayM4_OpenStream(
                        port, pBuffer, dwBufSize, 2 * 1024 * 1024
                    )
                    print(
                        f"[SDK] PlayM4_OpenStream -> {bool(ok_open)} "
                        f"| nvr={nvr_ip} | channel={channel} | header_size={dwBufSize}"
                    )
                    if ok_open:
                        live_entry["stream_opened"] = True
                        ok_play = self.play_ctrl.PlayM4_Play(port, None)
                        live_entry["playing"] = bool(ok_play)
                        print(f"[SDK] PlayM4_Play -> {bool(ok_play)}")
                    else:
                        err = self.play_ctrl.PlayM4_GetLastError(port)
                        print(f"[SDK] PlayM4_OpenStream error code={err}")
                    return

                # NET_DVR_STREAMDATA == 2 -> feed frame data to the decoder
                if dwDataType == 2 and live_entry["stream_opened"]:
                    ok_input = self.play_ctrl.PlayM4_InputData(
                        port, pBuffer, dwBufSize
                    )
                    if not ok_input:
                        err = self.play_ctrl.PlayM4_GetLastError(port)
                        # PlayM4 buffer-full errors are common/harmless if
                        # the consumer isn't reading fast enough — only
                        # log occasionally to avoid flooding.
                        if live_entry["frame_count"] == 0:
                            print(f"[SDK] PlayM4_InputData failed, err={err}")

                if on_data is not None:
                    try:
                        on_data(dwDataType, string_at(pBuffer, dwBufSize))
                    except Exception as cb_err:
                        print(f"[SDK] on_data callback error: {cb_err}")

            c_callback = REALDATACALLBACK(_real_data_cb)
            # keep a reference alive so ctypes doesn't garbage collect it
            self._live_callbacks[(nvr_ip, channel)] = c_callback

            handle = self.sdk.NET_DVR_RealPlay_V40(
                session["user_id"],
                byref(preview_info),
                c_callback,
                None
            )

            if handle < 0:
                err = self.sdk.NET_DVR_GetLastError()
                print(
                    f"[SDK] NET_DVR_RealPlay_V40 failed "
                    f"| nvr={nvr_ip} | channel={channel} | err={err}"
                )
                self._live_callbacks.pop((nvr_ip, channel), None)
                if use_decode:
                    self._display_callbacks.pop((nvr_ip, channel), None)
                    self.play_ctrl.PlayM4_Stop(port)
                    self.play_ctrl.PlayM4_CloseStream(port)
                    self.play_ctrl.PlayM4_FreePort(port)
                return -1

            live_entry["handle"] = handle
            session["live"][channel] = live_entry

            print(
                f"[SDK] Live view started "
                f"| nvr={nvr_ip} | channel={channel} | handle={handle} "
                f"| decode={use_decode}"
            )

            return handle

    def get_live_frame(self, nvr_ip: str, channel: int):
        """
        Returns the most recent decoded frame for a channel started with
        start_real_play(decode=True), or None if nothing decoded yet.
        """

        session = self._get_session(nvr_ip)
        entry = session["live"].get(channel)

        if entry is None:
            return False, None

        with entry["frame_lock"]:
            frame = entry["latest_frame"]

        return frame is not None, frame

    def live_stream(self, nvr_ip: str, channel: int, poll_interval=0.02, **start_kwargs):
        """
        Generator yielding decoded BGR frames sourced directly from
        NET_DVR_RealPlay_V40 + PlayCtrl.dll (NVR-side decode). Starts
        the live view if it isn't already running, and stops it on
        generator close/exit.

        Usage:
            for frame in sdk.live_stream("172.16.15.27", 33):
                cv2.imshow("live", frame)
                if cv2.waitKey(1) == 27:
                    break
        """

        started_here = channel not in self._get_session(nvr_ip)["live"]

        if started_here:
            handle = self.start_real_play(nvr_ip, channel, decode=True, **start_kwargs)
            if handle < 0:
                return

        try:
            last_frame_id = None
            while True:
                ok, frame = self.get_live_frame(nvr_ip, channel)
                if ok:
                    # avoid yielding the exact same frame object repeatedly
                    fid = id(frame)
                    if fid != last_frame_id:
                        last_frame_id = fid
                        yield frame
                time.sleep(poll_interval)
        finally:
            if started_here:
                self.stop_real_play(nvr_ip, channel)

    def stop_real_play(self, nvr_ip: str, channel: int):
        """
        Stops device-side live view via NET_DVR_StopRealPlay, matching
        the C# stop-live-view branch of btnPreview_Click, and tears down
        the PlayCtrl decode port if one was opened.
        """

        session = self._get_session(nvr_ip)

        with session["lock"]:

            entry = session["live"].pop(channel, None)

            if entry is None:
                return True

            ok = self.sdk.NET_DVR_StopRealPlay(entry["handle"])

            if not ok:
                err = self.sdk.NET_DVR_GetLastError()
                print(
                    f"[SDK] NET_DVR_StopRealPlay failed "
                    f"| nvr={nvr_ip} | channel={channel} | err={err}"
                )

            self._live_callbacks.pop((nvr_ip, channel), None)

            if entry.get("port") is not None and self.play_ctrl is not None:
                port = entry["port"]
                self.play_ctrl.PlayM4_Stop(port)
                self.play_ctrl.PlayM4_CloseStream(port)
                self.play_ctrl.PlayM4_FreePort(port)
                self._display_callbacks.pop((nvr_ip, channel), None)

            print(
                f"[SDK] Live view stopped "
                f"| nvr={nvr_ip} | channel={channel}"
            )

            return bool(ok)

    def scan_channels(self, nvr_ip: str, low: int = 1, high: int = 64):
        """
        Probes a range of channel numbers directly against
        NET_DVR_RealPlay_V40 (no decode, just open/close) and reports
        which ones the device actually accepts. Use this instead of
        guessing at channel-numbering conventions (they vary by NVR
        model/series) — this asks the device directly.

        Returns a list of channel numbers that opened successfully.
        """

        session = self._get_session(nvr_ip)
        working = []

        for ch in range(low, high + 1):

            preview_info = NET_DVR_PREVIEWINFO()
            preview_info.lChannel = ch
            preview_info.dwStreamType = 0
            preview_info.dwLinkMode = 0
            preview_info.hPlayWnd = None
            preview_info.bBlocked = 1
            preview_info.dwDisplayBufNum = 1
            preview_info.byProtoType = 0
            preview_info.byPreviewMode = 0

            null_cb = REALDATACALLBACK(lambda *a: None)

            handle = self.sdk.NET_DVR_RealPlay_V40(
                session["user_id"],
                byref(preview_info),
                null_cb,
                None
            )

            if handle >= 0:
                print(f"[SDK] channel {ch}: OK (handle={handle})")
                working.append(ch)
                self.sdk.NET_DVR_StopRealPlay(handle)
            else:
                err = self.sdk.NET_DVR_GetLastError()
                # err==4 (NET_DVR_CHANNEL_ERROR) is the expected "not a
                # real channel" response — anything else is worth noting
                if err != 4:
                    print(f"[SDK] channel {ch}: failed, err={err} (not the usual channel-error code)")

            time.sleep(0.05)

        print(f"[SDK] scan_channels done | working channels: {working}")
        return working

    def close(self):

        for nvr_ip, session in self.sessions.items():

            for channel in list(session["live"].keys()):
                try:
                    self.stop_real_play(nvr_ip, channel)
                except Exception:
                    pass

            try:
                self.sdk.NET_DVR_Logout(
                    session["user_id"]
                )

                print(
                    f"[SDK] Logged out "
                    f"{nvr_ip}"
                )

            except Exception:
                pass

        try:
            self.sdk.NET_DVR_Cleanup()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# if __name__ == "__main__":

#     from app.config.config import AppConfig
#     cfg = AppConfig()
    
#     ip = cfg.get("NVR","IP")
#     port = cfg.get("NVR", "PORT")
#     username = cfg.get("NVR", "USERNAME")
#     password = cfg.get("NVR", "PASSWORD")

#     print(f"""
#           NVR IP: {ip}\n
#           NVR PORT: {port}\n
#           NVR USERNAME: {username}\n
#           NVR PASSWORD: {password}\n
#           """)
    
#     hik = HikvisionSDK(
#         nvrs=[{
#             "ip": ip,
#             "port": port,
#             "username": username,
#             "password": password
#         }]
#     )
#     hik.scan_channels(ip, 1, 64)
#     for frame in hik.live_stream(ip, 33):
#         cv2.imshow("live", frame)
#         # waitKey() is required for imshow to actually paint/refresh the
#         # window and process its message queue — without it the window
#         # will appear blank or never show at all.
#         if cv2.waitKey(1) & 0xFF == 27:  # Esc to quit
#             break

#     cv2.destroyAllWindows()
#     hik.close()
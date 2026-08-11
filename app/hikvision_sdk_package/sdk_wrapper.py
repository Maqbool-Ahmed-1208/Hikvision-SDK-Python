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


# ---------------------------------------------------------------------------
# Playback-by-time structures (NET_DVR_PlayBackByTime)
# ---------------------------------------------------------------------------

class NET_DVR_TIME(Structure):
    _fields_ = [
        ("dwYear", c_uint),
        ("dwMonth", c_uint),
        ("dwDay", c_uint),
        ("dwHour", c_uint),
        ("dwMinute", c_uint),
        ("dwSecond", c_uint),
    ]


class NET_DVR_PLAYCOND(Structure):
    _fields_ = [
        ("dwChannel", c_uint),
        ("struStartTime", NET_DVR_TIME),
        ("struStopTime", NET_DVR_TIME),
        ("byDrawFrame", c_byte),   # 0-non key frame, 1-key frame only
        ("byRes", c_byte * 63),
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
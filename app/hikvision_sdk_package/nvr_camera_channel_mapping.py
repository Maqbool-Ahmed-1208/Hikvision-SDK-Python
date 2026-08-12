import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
import json
import os, sys, re
sys.path.append(".")
from app.utils.helper_functions import load_json
from app.config.config import AppConfig

cfg = AppConfig()


CHANNEL_MAPPING_PATH = cfg.get("PATHS", "CHANNEL_MAPPING_PATH")


def build_camera_channel_mapping(
    nvr_ip: str,
    username: str,
    password: str,
    output_file: str = CHANNEL_MAPPING_PATH,
    timeout: int = 10,
    sdk: object = None
):
    """
    Build NVR -> Camera IP -> SDK Channel mapping.

    Handles NVRs where SDK channels may start from:
        1, 2, 3, ...
    or:
        33, 34, 35, ...

    ISAPI channel IDs are treated as the logical camera sequence,
    while SDK channels are resolved using the detected SDK start channel.

    Output example:

    {
        "19216810010": {
            "192.168.1.101": {
                "channel": 33,
                "name": "Camera 01"
            },
            "192.168.1.102": {
                "channel": 34,
                "name": "Camera 02"
            }
        }
    }
    """

    # ==========================================================
    # VALIDATE SDK
    # ==========================================================

    if sdk is None:
        return {
            "error": "SDK object is required"
        }

    # ==========================================================
    # STEP 1: SCAN ACTIVE SDK CHANNELS
    # ==========================================================

    try:

        active_channels = sdk.scan_channels(
            nvr_ip=nvr_ip,
            low=1,
            high=128
        )

    except Exception as e:

        return {
            "error": f"SDK channel scan failed for {nvr_ip}: {str(e)}"
        }

    if not active_channels:

        return {
            "error": f"No active channels found for NVR {nvr_ip}"
        }

    # ==========================================================
    # CLEAN SDK CHANNEL LIST
    # ==========================================================

    try:

        active_channels = sorted(
            set(
                int(ch)
                for ch in active_channels
                if str(ch).isdigit()
            )
        )

    except Exception as e:

        return {
            "error": f"Invalid SDK channel data: {str(e)}"
        }

    if not active_channels:

        return {
            "error": f"No valid SDK channels found for NVR {nvr_ip}"
        }

    # ==========================================================
    # DETECT SDK START CHANNEL
    # ==========================================================

    start_channel = active_channels[0]

    print()
    print("=" * 70)
    print(f"[{nvr_ip}] SDK ACTIVE CHANNELS")
    print(active_channels)

    print(
        f"[{nvr_ip}] Detected SDK channel start: "
        f"{start_channel}"
    )

    print("=" * 70)

    # ==========================================================
    # DETECT CHANNEL OFFSET
    #
    # Example:
    #
    # SDK starts at 1:
    #     ISAPI 1 -> SDK 1
    #
    # SDK starts at 33:
    #     ISAPI 1 -> SDK 33
    #
    # Therefore:
    #
    # sdk_channel = isapi_channel + (start_channel - 1)
    # ==========================================================

    channel_offset = start_channel - 1

    print(
        f"[{nvr_ip}] Channel offset: "
        f"{channel_offset}"
    )

    # ==========================================================
    # STEP 2: ISAPI REQUEST
    # ==========================================================

    url = (
        f"http://{nvr_ip}"
        f"/ISAPI/ContentMgmt/InputProxy/channels"
    )

    print(
        f"[{nvr_ip}] Requesting ISAPI:"
    )
    print(url)

    try:

        response = requests.get(
            url,
            auth=HTTPDigestAuth(
                username,
                password
            ),
            timeout=timeout
        )

        response.raise_for_status()

    except requests.exceptions.RequestException as e:

        return {
            "error": (
                f"ISAPI request failed for "
                f"{nvr_ip}: {str(e)}"
            )
        }

    # ==========================================================
    # STEP 3: PARSE XML
    # ==========================================================

    try:

        root = ET.fromstring(
            response.text
        )

    except ET.ParseError as e:

        return {
            "error": (
                f"Invalid ISAPI XML returned by "
                f"{nvr_ip}: {str(e)}"
            )
        }

    # ==========================================================
    # STEP 4: AUTO-DETECT XML NAMESPACE
    # ==========================================================

    namespace = ""

    if root.tag.startswith("{"):

        namespace = (
            root.tag
            .split("}")[0]
            .strip("{")
        )

    ns = {
        "ns": namespace
    } if namespace else {}

    print(
        f"[{nvr_ip}] XML namespace: "
        f"{namespace or 'NONE'}"
    )

    # ==========================================================
    # STEP 5: FIND ISAPI CHANNELS
    # ==========================================================

    if namespace:

        channels = root.findall(
            "ns:InputProxyChannel",
            ns
        )

    else:

        channels = root.findall(
            "InputProxyChannel"
        )

    print(
        f"[{nvr_ip}] ISAPI channels found: "
        f"{len(channels)}"
    )

    if not channels:

        print(
            f"[{nvr_ip}] WARNING: "
            f"No InputProxyChannel elements found."
        )

        print(
            f"[{nvr_ip}] XML response:"
        )

        print(response.text)

        return {
            "error": (
                f"No InputProxyChannel elements "
                f"found for NVR {nvr_ip}"
            )
        }

    # ==========================================================
    # STEP 6: NVR KEY
    # ==========================================================

    nvr_key = nvr_ip.replace(".", "")

    result = {
        nvr_key: {}
    }

    # ==========================================================
    # STEP 7: PROCESS ISAPI CHANNELS
    # ==========================================================

    for ch in channels:

        # ------------------------------------------------------
        # READ CHANNEL ID
        # ------------------------------------------------------

        if namespace:

            channel_id = ch.findtext(
                "ns:id",
                default=None,
                namespaces=ns
            )

            name = ch.findtext(
                "ns:name",
                default=None,
                namespaces=ns
            )

            ip = ch.findtext(
                ".//ns:ipAddress",
                default=None,
                namespaces=ns
            )

        else:

            channel_id = ch.findtext(
                "id"
            )

            name = ch.findtext(
                "name"
            )

            ip = ch.findtext(
                ".//ipAddress"
            )

        # ------------------------------------------------------
        # DEBUG
        # ------------------------------------------------------

        print(
            f"[{nvr_ip}] ISAPI -> "
            f"id={channel_id}, "
            f"name={name}, "
            f"ip={ip}"
        )

        # ------------------------------------------------------
        # VALIDATE IP
        # ------------------------------------------------------

        if not ip:

            print(
                f"[{nvr_ip}] SKIP: "
                f"No IP address"
            )

            continue

        # ------------------------------------------------------
        # VALIDATE CHANNEL ID
        # ------------------------------------------------------

        if not channel_id:

            print(
                f"[{nvr_ip}] SKIP: "
                f"No channel ID for {ip}"
            )

            continue

        if not str(channel_id).isdigit():

            print(
                f"[{nvr_ip}] SKIP: "
                f"Invalid channel ID "
                f"{channel_id}"
            )

            continue

        isapi_channel = int(
            channel_id
        )

        # ======================================================
        # CALCULATE SDK CHANNEL
        #
        # start = 1:
        #
        #   ISAPI 1 -> SDK 1
        #   ISAPI 2 -> SDK 2
        #
        # start = 33:
        #
        #   ISAPI 1 -> SDK 33
        #   ISAPI 2 -> SDK 34
        # ======================================================

        sdk_channel = (
            isapi_channel
            + channel_offset
        )

        print(
            f"[{nvr_ip}] Mapping: "
            f"ISAPI {isapi_channel} "
            f"-> SDK {sdk_channel}"
        )

        # ======================================================
        # ONLY USE CHANNELS ACTUALLY DETECTED BY SDK
        # ======================================================

        if sdk_channel not in active_channels:

            print(
                f"[{nvr_ip}] SKIP: "
                f"SDK channel {sdk_channel} "
                f"not active"
            )

            continue

        # ======================================================
        # ADD MAPPING
        # ======================================================

        result[nvr_key][ip] = {
            "channel": sdk_channel,
            "name": name
        }

    # ==========================================================
    # STEP 8: CHECK RESULT
    # ==========================================================

    print()
    print(
        f"[{nvr_ip}] FINAL MAPPINGS: "
        f"{len(result[nvr_key])}"
    )

    if not result[nvr_key]:

        print(
            f"[{nvr_ip}] WARNING: "
            f"No camera mappings were created."
        )

        print(
            f"[{nvr_ip}] SDK channels: "
            f"{active_channels}"
        )

        return result

    # ==========================================================
    # STEP 9: LOAD EXISTING FILE
    # ==========================================================

    if os.path.exists(output_file):

        try:

            with open(
                output_file,
                "r",
                encoding="utf-8"
            ) as f:

                existing = json.load(f)

            if not isinstance(existing, dict):

                existing = {}

        except (
            json.JSONDecodeError,
            OSError
        ):

            existing = {}

    else:

        existing = {}

    # ==========================================================
    # STEP 10: UPDATE NVR
    # ==========================================================

    existing[nvr_key] = result[nvr_key]

    # ==========================================================
    # STEP 11: CREATE OUTPUT DIRECTORY
    # ==========================================================

    output_dir = os.path.dirname(
        output_file
    )

    if output_dir:

        os.makedirs(
            output_dir,
            exist_ok=True
        )

    # ==========================================================
    # STEP 12: SAVE
    # ==========================================================

    try:

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                existing,
                f,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:

        return {
            "error": (
                f"Failed to save mapping file: "
                f"{str(e)}"
            )
        }

    # ==========================================================
    # FINAL OUTPUT
    # ==========================================================

    print()
    print("=" * 70)
    print(
        f"[{nvr_ip}] CAMERA CHANNEL MAPPING"
    )
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        )
    )

    print("=" * 70)
    print(
        f"[{nvr_ip}] Mapping saved to:"
    )
    print(output_file)
    print("=" * 70)

    return existing

def get_camera_channel(
    nvr_ip,
    camera_ip,
    nvr_channel_mappings_path = CHANNEL_MAPPING_PATH
):
    nvr_channel_mappings = load_json(nvr_channel_mappings_path)

    # Normalize NVR key
    nvr_key = nvr_ip.replace(".", "")

    # Normalize camera IP
    if camera_ip:
        match = re.search(r"\d{1,3}(?:\.\d{1,3}){3}", camera_ip)
        if match:
            camera_ip = match.group(0)

    nvr_mapping = nvr_channel_mappings.get(nvr_key)
    if not nvr_mapping:
        return None

    camera_mapping = nvr_mapping.get(camera_ip)
    if not camera_mapping:
        return None

    return camera_mapping.get("channel")


# if __name__ == "__main__":

#     from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
#     from app.config.config import AppConfig
#     cfg = AppConfig()

#     ip = cfg.get("NVR","IP")
#     port = cfg.get("NVR", "PORT", cast=int)
#     username = cfg.get("NVR", "USERNAME")
#     password = cfg.get("NVR", "PASSWORD")

#     hik = HikvisionSDK(
#         nvrs=[{
#             "ip": ip,
#             "port": port,
#             "username": username,
#             "password": password
#         }]
#     )

#     print(f"""
#             NVR IP: {ip}\n
#             NVR PORT: {port}\n
#             NVR USERNAME: {username}\n
#             NVR PASSWORD: {password}\n
#             """)
    
#     build_camera_channel_mapping(
#         nvr_ip=ip,
#         username=username,
#         password=password,
#         sdk=hik
#     )

    
#     channel = get_camera_channel(
#     nvr_ip=ip,
#     camera_ip="192.168.100.116",
#     )

#     print(channel)
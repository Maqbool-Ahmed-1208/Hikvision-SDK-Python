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
    # ==========================================================
    # SCAN ACTIVE CHANNELS
    # ==========================================================
    active_channels = sdk.scan_channels(
        nvr_ip=nvr_ip,
        low=1,
        high=128
    )

    if not active_channels:
        return {
            "error": f"No active channels found for NVR {nvr_ip}"
        }

    # Ensure sorted integer channel numbers
    active_channels = sorted(
        int(ch) for ch in active_channels
    )

    # Actual starting channel detected by SDK
    start_channel = active_channels[0]

    print(
        f"[{nvr_ip}] Active channels: "
        f"{active_channels}"
    )

    print(
        f"[{nvr_ip}] Channel sequence starts from: "
        f"{start_channel}"
    )

    url = (
        f"http://{nvr_ip}"
        f"/ISAPI/ContentMgmt/InputProxy/channels"
    )

    try:

        r = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            timeout=timeout
        )

        r.raise_for_status()

        root = ET.fromstring(r.text)

        # ======================================================
        # AUTO-DETECT XML NAMESPACE
        # ======================================================
        namespace = ""

        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0].strip("{")

        ns = {
            "ns": namespace
        } if namespace else {}

        nvr_key = nvr_ip.replace(".", "")

        result = {
            nvr_key: {}
        }

        # ======================================================
        # FIND CHANNELS
        # ======================================================
        if namespace:

            channels = root.findall(
                "ns:InputProxyChannel",
                ns
            )

        else:

            channels = root.findall(
                "InputProxyChannel"
            )

        # ======================================================
        # BUILD MAPPING
        # ======================================================
        for ch in channels:

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

                channel_id = ch.findtext("id")
                name = ch.findtext("name")
                ip = ch.findtext(".//ipAddress")

            if not ip:
                continue

            if not channel_id:
                continue

            if not str(channel_id).isdigit():
                continue

            channel_id = int(channel_id)

            # ==================================================
            # ONLY USE CHANNELS FOUND BY SDK
            # ==================================================
            if channel_id not in active_channels:
                continue

            result[nvr_key][ip] = {
                "channel": channel_id,
                "name": name
            }

        # ======================================================
        # MERGE WITH EXISTING FILE
        # ======================================================
        if os.path.exists(output_file):

            with open(
                output_file,
                "r",
                encoding="utf-8"
            ) as f:

                existing = json.load(f)

        else:

            existing = {}

        existing.update(result)

        # ======================================================
        # SAVE
        # ======================================================
        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                existing,
                f,
                indent=4
            )

        return existing

    except Exception as e:

        return {
            "error": str(e)
        }


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
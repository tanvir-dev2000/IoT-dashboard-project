# tuya/tuya_client.py

import datetime
import env
import data_processor
import storage.storage_manager as storage_manager
from tuya_iot import TuyaOpenAPI

_openapi = TuyaOpenAPI(env.ENDPOINT, env.ACCESS_ID, env.ACCESS_KEY)

def initialize_client():
    resp = _openapi.connect(env.USERNAME, env.PASSWORD, "eu", "tuyasmart")
    if resp and resp.get("success"):
        print("Tuya client connected.")
        return True
    else:
        print("Failed to connect Tuya client.")
        return False

def get_device_status():
    # Check device online status
    device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")
    if not device_info.get("success") or not device_info.get("result", {}).get("online", False):
        print("Device is offline, using offline snapshot.")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot, records = data_processor.get_offline_snapshot(env.DEVICE_ID, timestamp)
        storage_manager.insert_data_into_google_sheet(snapshot)
        for record in records:
            storage_manager.insert_data_into_sqlite(record)
        return snapshot

    # Device online - get real status
    status_resp = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}/status")
    if status_resp.get("success"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_dp_list = status_resp.get("result", [])
        snapshot, records = data_processor.process_device_data_snapshot(env.DEVICE_ID, raw_dp_list, timestamp)
        storage_manager.insert_data_into_google_sheet(snapshot)
        for record in records:
            storage_manager.insert_data_into_sqlite(record)
        return snapshot
    else:
        print("Failed to get device status.")
        return None

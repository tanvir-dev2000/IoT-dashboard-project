
import logging
import json
import time
import threading
import datetime
from tuya_iot import TuyaOpenAPI, TuyaOpenMQ, TUYA_LOGGER
import env
import data_processor
import storage_manager

TUYA_DEVICE_OFFLINE_CODE = 1106
TUYA_TOKEN_INVALID_CODE = 1010


_openapi = None
_openmq = None



def initialize_tuya_client():
    global _openapi
    _openapi = TuyaOpenAPI(env.ENDPOINT, env.ACCESS_ID, env.ACCESS_KEY)
    print("Tuya Client: Attempting to connect to Tuya Cloud API...")
    connect_response = _openapi.connect(env.USERNAME, env.PASSWORD, "eu", "tuyasmart")
    print(f"Tuya Client: Connect response: {connect_response}")

    if connect_response and connect_response.get("success"):
        print("Tuya Client: Successfully connected to Tuya Cloud API.")
        return True
    else:
        print("Tuya Client: Failed to establish connection to Tuya Cloud API.")
        return False



def _on_message_callback(msg):
    try:
        message_data = msg
        current_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        if 'data' in message_data and 'status' in message_data['data']:
            dev_id = message_data['data'].get('devId')
            raw_dp_list = message_data['data'].get('status', [])
            snapshot, individual_dp_records = data_processor.process_device_data_snapshot(dev_id, raw_dp_list,
                                                                                          current_timestamp)
            print(f"\nTuya Client: --- Received MQTT Device Data Update ({current_timestamp}) ---")
            data_processor.print_clean_snapshot(snapshot)
        else:
            print(
                f"\nTuya Client: --- Received Other MQTT Message (Protocol: {message_data.get('protocol', 'N/A')}) ---")
            print(json.dumps(message_data, indent=2))
    except Exception as e:
        print(f"Tuya Client: An error occurred in MQTT callback: {e} - Message: {msg}")


def start_mqtt_listener():
    global _openmq
    if _openapi is None:
        print("Tuya Client: OpenAPI not initialized. Cannot start MQTT listener.")
        return False

    print("Tuya Client: Starting MQTT listener...")
    _openmq = TuyaOpenMQ(_openapi)
    _openmq.add_message_listener(_on_message_callback)
    _openmq.start()
    print(f"Tuya Client: Listening for real-time MQTT updates for device: {env.DEVICE_ID}...")
    return True



def _get_device_status_poll():
    global _openapi

    if _openapi is None:
        print("Tuya Client: OpenAPI not initialized for polling.")
        return False

    print(f"\nTuya Client: --- Polling status for device: {env.DEVICE_ID} ---")

    print("Tuya Client: Checking device online status...")
    device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")


    if not device_info.get("success"):
        error_code = device_info.get("code")
        error_msg = device_info.get("msg")
        print(f"Tuya Client: Device info API call FAILED. Code: {error_code}, Message: {error_msg}")

        if error_code == TUYA_TOKEN_INVALID_CODE:
            print("Tuya Client: Token invalid detected. Forcing full API client re-initialization (re-login).")
            if not initialize_tuya_client():
                print("Tuya Client: Failed to re-initialize client after token invalid. Cannot poll.")
                return False

            device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")
            if not device_info.get("success"):
                print("Tuya Client: Still failed to get device info after re-login.")
                return False
        else:
            print("Tuya Client: Failed to get device info (not token issue).")
            return False

    is_online = device_info.get("result", {}).get("online", False)
    current_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

    if not is_online:
        print(f"Tuya Client: Device {env.DEVICE_ID} is OFFLINE. Using offline snapshot ({current_timestamp}).")
        snapshot, individual_dp_records = data_processor.get_offline_snapshot(env.DEVICE_ID, current_timestamp)
        data_processor.print_clean_snapshot(snapshot)
        storage_manager.insert_data_into_google_sheet(snapshot)
        for record in individual_dp_records:
            storage_manager.insert_data_into_sqlite(record)
        return True

    print(f"Tuya Client: Device {env.DEVICE_ID} is ONLINE. Proceeding with status polling...")
    response = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}/status")

    if not response.get("success"):
        error_code = response.get("code")
        error_msg = response.get("msg")
        print(f"Tuya Client: Status polling API call FAILED. Code: {error_code}, Message: {error_msg}")

        if error_code == TUYA_TOKEN_INVALID_CODE:
            print(
                "Tuya Client: Token invalid detected during status polling. Forcing full API client re-initialization.")
            if not initialize_tuya_client():
                print("Tuya Client: Failed to re-initialize client after token invalid. Cannot poll.")
                return False

            response = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}/status")
            if not response.get("success"):
                print("Tuya Client: Still failed to get device status after re-login.")
                return False
        else:
            print("Tuya Client: Failed to poll device status (not token issue).")
            return False

    raw_dp_list = response.get("result", [])
    snapshot, individual_dp_records = data_processor.process_device_data_snapshot(env.DEVICE_ID, raw_dp_list,
                                                                                  current_timestamp)
    print(f"Tuya Client: Current polled status for {env.DEVICE_ID} ({current_timestamp}):")
    data_processor.print_clean_snapshot(snapshot)

    storage_manager.insert_data_into_google_sheet(snapshot)
    for record in individual_dp_records:
        storage_manager.insert_data_into_sqlite(record)

    return True

def start_polling_loop():
    if _openapi is None:
        print("Tuya Client: OpenAPI not initialized for polling. Cannot start polling loop.")
        return

    polling_thread = threading.Thread(target=_polling_thread_runner, args=(env.POLLING_INTERVAL_SECONDS,), daemon=True)
    polling_thread.start()
    print(f"Tuya Client: Starting polling thread for device status every {env.POLLING_INTERVAL_SECONDS} seconds.")


def _polling_thread_runner(interval):
    while True:
        _get_device_status_poll()
        time.sleep(interval)


def stop_tuya_client():
    if _openmq:
        _openmq.stop()
        print("Tuya Client: MQTT listener stopped.")


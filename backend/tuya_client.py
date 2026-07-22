# tuya_client.py

import logging
import json
import time
import threading
import datetime
from tuya_iot import TuyaOpenAPI, TuyaOpenMQ, TUYA_LOGGER
import app_config as env
import data_processor
import storage_manager

TUYA_DEVICE_OFFLINE_CODE = 1106  # Common code for "device is offline"
TUYA_TOKEN_INVALID_CODE = 1010  # Code for "token invalid"

# --- Global Tuya API and MQTT objects ---
_openapi = None
_openmq = None
_polling_thread = None
_heartbeat_thread = None


# --- Initialization and Connection ---
_api_lock = threading.Lock()


def initialize_tuya_client():
    global _openapi
    with _api_lock:  # Thread-safe initialization
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


def start_mqtt_listener():
    global _openmq
    with _api_lock:  # Thread-safe MQTT startup
        if _openapi is None or _openapi.token_info is None:
            print("Tuya Client: OpenAPI not properly initialized. Cannot start MQTT listener.")
            return False

        if _openmq is not None:
            if _openmq.is_alive():
                print(f"Tuya Client: MQTT listener already running (alive={_openmq.is_alive()}).")
                return True

            print(f"Tuya Client: MQTT listener exists but not alive, cleaning up...")
            try:
                _openmq.stop()
                _openmq.join(timeout=10)
            except Exception as exc:
                print(f"Tuya Client: Error stopping existing MQTT listener: {exc}")
            _openmq = None

        print("Tuya Client: Starting MQTT listener...")
        _openmq = TuyaOpenMQ(_openapi)
        _openmq.add_message_listener(_on_message_callback)
        _openmq.start()
        print(f"Tuya Client: Listening for real-time MQTT updates for device: {env.DEVICE_ID}... alive={_openmq.is_alive()}")
        # Start a lightweight heartbeat thread to print online status frequently (no Sheets writes)
        try:
            start_heartbeat_loop()
        except Exception:
            pass
        return True


# --- MQTT Listener Callback (Only Prints, No Storage Insertions) ---
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
            data_processor.print_clean_snapshot(snapshot)  # Print to console

            # SQLite insertion for MQTT data (if desired) - currently commented out
            # for record in individual_dp_records:
            #     storage_manager.insert_data_into_sqlite(record)
        else:
            print(
                f"\nTuya Client: --- Received Other MQTT Message (Protocol: {message_data.get('protocol', 'N/A')}) ---")
            print(json.dumps(message_data, indent=2))
    except Exception as e:
        print(f"Tuya Client: An error occurred in MQTT callback: {e} - Message: {msg}")


# --- PUBLIC FUNCTIONS for main.py to call ---
# === START OF PUBLIC FUNCTION DEFINITIONS ===

# Function to Start MQTT Listener (This is what main.py calls)


# --- MODIFIED Polling Function with Device Online Status Check ---
def _get_device_status_poll():
    global _openapi  # Make sure _openapi is global to re-assign if needed

    if _openapi is None:
        print("Tuya Client: OpenAPI not initialized for polling.")
        return False

    print(f"\nTuya Client: --- Polling status for device: {env.DEVICE_ID} ---")

    # NEW: Check device online status FIRST
    print("Tuya Client: Checking device online status...")
    device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")

    # Handle API errors for device info request
    if not device_info.get("success"):
        error_code = device_info.get("code")
        error_msg = device_info.get("msg")
        print(f"Tuya Client: Device info API call FAILED. Code: {error_code}, Message: {error_msg}")

        # If token is invalid, force a full re-initialization (re-login)
        if error_code == TUYA_TOKEN_INVALID_CODE:
            print("Tuya Client: Token invalid detected. Forcing full API client re-initialization (re-login).")
            if not initialize_tuya_client():
                print("Tuya Client: Failed to re-initialize client after token invalid. Cannot poll.")
                return False

            # Retry device info call after re-login
            device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")
            if not device_info.get("success"):
                print("Tuya Client: Still failed to get device info after re-login.")
                return False
        else:
            print("Tuya Client: Failed to get device info (not token issue).")
            return False

    # Check if device is online
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

    # Device is online, proceed with normal status polling
    print(f"Tuya Client: Device {env.DEVICE_ID} is ONLINE. Proceeding with status polling...")
    response = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}/status")

    # Handle status polling API errors
    if not response.get("success"):
        error_code = response.get("code")
        error_msg = response.get("msg")
        print(f"Tuya Client: Status polling API call FAILED. Code: {error_code}, Message: {error_msg}")

        # If token is invalid, force a full re-initialization (re-login)
        if error_code == TUYA_TOKEN_INVALID_CODE:
            print(
                "Tuya Client: Token invalid detected during status polling. Forcing full API client re-initialization.")
            if not initialize_tuya_client():
                print("Tuya Client: Failed to re-initialize client after token invalid. Cannot poll.")
                return False

            # Retry status call after re-login
            response = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}/status")
            if not response.get("success"):
                print("Tuya Client: Still failed to get device status after re-login.")
                return False
        else:
            print("Tuya Client: Failed to poll device status (not token issue).")
            return False

    # Process successful response
    raw_dp_list = response.get("result", [])
    snapshot, individual_dp_records = data_processor.process_device_data_snapshot(env.DEVICE_ID, raw_dp_list,
                                                                                  current_timestamp)
    print(f"Tuya Client: Current polled status for {env.DEVICE_ID} ({current_timestamp}):")
    data_processor.print_clean_snapshot(snapshot)

    storage_manager.insert_data_into_google_sheet(snapshot)
    for record in individual_dp_records:
        storage_manager.insert_data_into_sqlite(record)

    return True


# --- Polling Thread Function (This is what main.py calls) ---
def start_polling_loop():
    global _polling_thread
    if _openapi is None:
        print("Tuya Client: OpenAPI not initialized for polling. Cannot start polling loop.")
        return

    if _polling_thread and _polling_thread.is_alive():
        print("Tuya Client: Polling thread already running")
        return

    _polling_thread = threading.Thread(target=_polling_thread_runner, args=(env.POLLING_INTERVAL_SECONDS,), daemon=True)
    _polling_thread.start()
    print(f"Tuya Client: Starting polling thread for device status every {env.POLLING_INTERVAL_SECONDS} seconds.")


def start_heartbeat_loop():
    """Start a heartbeat thread that prints device online status frequently (no Sheets writes)."""
    global _heartbeat_thread
    interval = int(getattr(env, 'HEARTBEAT_INTERVAL_SECONDS', 30))
    if _heartbeat_thread and _heartbeat_thread.is_alive():
        return
    _heartbeat_thread = threading.Thread(target=_heartbeat_thread_runner, args=(interval,), daemon=True)
    _heartbeat_thread.start()
    print(f"Tuya Client: Starting heartbeat thread every {interval} seconds.")


def _heartbeat_thread_runner(interval):
    while True:
        try:
            if _openapi is None:
                time.sleep(interval)
                continue
            device_info = _openapi.get(f"/v1.0/devices/{env.DEVICE_ID}")
            is_online = False
            if device_info and device_info.get('success'):
                is_online = device_info.get('result', {}).get('online', False)
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            status = 'ONLINE' if is_online else 'OFFLINE'
            print(f"Tuya Heartbeat: {env.DEVICE_ID} is {status} at {ts}")
        except Exception as e:
            print(f"Tuya Heartbeat: error checking device status: {e}")
        time.sleep(interval)


# Internal runner for the polling thread
def _polling_thread_runner(interval):
    while True:
        _get_device_status_poll()
        time.sleep(interval)


# --- Cleanup ---
def stop_tuya_client():
    if _openmq:
        print(f"Tuya Client: Stopping MQTT listener (alive={_openmq.is_alive()})")
        _openmq.stop()
        print("Tuya Client: MQTT listener stopped.")
    else:
        print("Tuya Client: No MQTT listener to stop.")

# === END OF PUBLIC FUNCTION DEFINITIONS ===

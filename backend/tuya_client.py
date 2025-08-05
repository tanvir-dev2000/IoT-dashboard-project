import logging
import json
import time
import threading
import datetime
from tuya_iot import TuyaOpenAPI, TuyaOpenMQ, TUYA_LOGGER
from env import env
from backend import data_processor
from backend import storage_manager

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
            data_processor.print_clean_snapshot(snapshot)  # Print to console


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
    global _openapi  # Make sure _openapi is global to re-assign if needed

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

    # Device is online, proceed with normal status polling
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


def turn_off_circuit_breaker():
    """Turn off the circuit breaker (DP ID 16)"""
    global _openapi

    if _openapi is None:
        print("Tuya Client: API not initialized")
        return False

    try:
        commands_list = [
            {
                "commands": [
                    {
                        "code": "switch",
                        "value": False
                    }
                ]
            },
            {
                "commands": [
                    {
                        "code": "switch_1",
                        "value": False
                    }
                ]
            }
        ]

        print(f"Tuya Client: Attempting to turn OFF circuit breaker...")

        for commands in commands_list:
            response = _openapi.post(f'/v1.0/devices/{env.DEVICE_ID}/commands', commands)

            if response and response.get('success'):
                print("Tuya Client: Circuit breaker turned OFF successfully")
                return True

        print(f"Tuya Client: Failed to turn off circuit breaker")
        return False

    except Exception as e:
        print(f"Tuya Client: Error turning off circuit breaker: {e}")
        return False


def turn_on_circuit_breaker():
    """Turn on the circuit breaker (DP ID 16)"""
    global _openapi

    if _openapi is None:
        print("Tuya Client: API not initialized")
        return False

    try:
        commands_list = [
            {
                "commands": [
                    {
                        "code": "switch",
                        "value": True
                    }
                ]
            },
            {
                "commands": [
                    {
                        "code": "switch_1",
                        "value": True
                    }
                ]
            }
        ]

        print(f"Tuya Client: Attempting to turn ON circuit breaker...")

        for commands in commands_list:
            response = _openapi.post(f'/v1.0/devices/{env.DEVICE_ID}/commands', commands)

            if response and response.get('success'):
                print("Tuya Client: Circuit breaker turned ON successfully")
                return True

        print(f"Tuya Client: Failed to turn on circuit breaker")
        return False

    except Exception as e:
        print(f"Tuya Client: Error turning on circuit breaker: {e}")
        return False


def get_switch_status():
    """Get current status of the circuit breaker"""
    global _openapi

    if _openapi is None:
        print("Tuya Client: API not initialized")
        return None

    try:
        response = _openapi.get(f'/v1.0/devices/{env.DEVICE_ID}/status')

        if response and response.get('success'):
            status_list = response.get('result', [])


            for status in status_list:
                if status.get('dp_id') == 16 or status.get('code') in ['switch', 'switch_1']:
                    switch_status = status.get('value')
                    return switch_status

            print("Tuya Client: Switch status not found")
            return None
        else:
            print(f"Tuya Client: Failed to get device status")
            return None

    except Exception as e:
        print(f"Tuya Client: Error getting switch status: {e}")
        return None


def get_switch_status_cached():
    """
    Get switch status with basic caching to avoid too many API calls
    """
    import time


    current_time = time.time()
    cache_duration = 10  # Cache for 10 seconds


    if hasattr(get_switch_status_cached, 'last_call') and hasattr(get_switch_status_cached, 'last_result'):
        if current_time - get_switch_status_cached.last_call < cache_duration:
            return get_switch_status_cached.last_result

    # Get fresh status
    status = get_switch_status()

    # Cache the result
    get_switch_status_cached.last_call = current_time
    get_switch_status_cached.last_result = status

    return status

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


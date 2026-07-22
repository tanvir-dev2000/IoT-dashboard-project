# main.py
import logging
import time
import sys

from env import env
import tuya_client
import storage_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



if __name__ == "__main__":
    print("Main: Starting Tuya IoT Data Logger Application...")

    try:
        storage_manager.initialize_storage(
            db_file='../tuya_device_data.db',
            google_sheets_key_file=env.SERVICE_ACCOUNT_FILE,
            google_sheet_name=env.GOOGLE_SHEETS_NAME,
        )


    except Exception as e:
        print(f"Main: Error initializing storage: {e}")
        sys.exit(1)

    # 2. Initialize and Connect to Tuya Cloud API
    if not tuya_client.initialize_tuya_client():
        print("Main: Failed to connect to Tuya Cloud API. Exiting.")
        storage_manager.close_storage()
        sys.exit(1)

    if not tuya_client.start_mqtt_listener():
        print("Main: Failed to start MQTT listener. Exiting.")
        tuya_client.stop_tuya_client()
        storage_manager.close_storage()
        sys.exit(1)

    if env.POLLING_INTERVAL_SECONDS > 0:
        tuya_client.start_polling_loop()
    else:
        print("Main: Polling is disabled (POLLING_INTERVAL_SECONDS set to 0 or less).")

    print("\nMain: Application is running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMain: Ctrl+C detected. Stopping application...")
    except Exception as main_e:
        print(f"Main: An unexpected error occurred in the main loop: {main_e}")
    finally:
        tuya_client.stop_tuya_client()
        storage_manager.close_storage()
        print("Main: Application finished.")
# main.py
import logging
import time
import sys

# Import our modular components
import env
import tuya_client
import storage_manager

# --- Configure Root Logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Main execution block ---
if __name__ == "__main__":
    print("Main: Starting Tuya IoT Data Logger Application...")

    # 1. Initialize Storage Managers (SQLite and Google Sheets)
    try:
        storage_manager.initialize_storage(
            db_file='tuya_device_data.db',
            google_sheets_key_file=env.GOOGLE_SHEETS_KEY_FILE,
            google_sheet_name=env.GOOGLE_SHEET_NAME,
        )
    except Exception as e:
        print(f"Main: Error initializing storage: {e}")
        sys.exit(1)

    # 2. Initialize and Connect to Tuya Cloud API
    if not tuya_client.initialize_tuya_client():
        print("Main: Failed to connect to Tuya Cloud API. Exiting.")
        storage_manager.close_storage()
        sys.exit(1)

    # 3. Start MQTT Listener for Real-time Updates
    if not tuya_client.start_mqtt_listener():
        print("Main: Failed to start MQTT listener. Exiting.")
        tuya_client.stop_tuya_client()
        storage_manager.close_storage()
        sys.exit(1)

    # 4. Start Polling Loop (Optional, based on env.POLLING_INTERVAL_SECONDS)
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
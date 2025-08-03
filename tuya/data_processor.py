# tuya/data_processor.py

def get_offline_snapshot(device_id, timestamp):
    # Return offline data snapshot
    snapshot = {
        "device_id": device_id,
        "timestamp": timestamp,
        "status": "Offline",
        "voltage": None,
        "current": None,
        "power": None,
    }
    records = []  # Possibly empty or fill as needed
    return snapshot, records

def process_device_data_snapshot(device_id, dp_list, timestamp):
    # Convert raw dp_list to cleaned snapshot and individual records
    snapshot = {
        "device_id": device_id,
        "timestamp": timestamp,
        "status": "Online",
        # Example values - adapt depending on your dp_list structure:
        "voltage": next((item.get("value") for item in dp_list if item.get("code") == "voltage"), None),
        "current": next((item.get("value") for item in dp_list if item.get("code") == "current"), None),
        "power": next((item.get("value") for item in dp_list if item.get("code") == "power"), None),
    }
    records = []  # Build list of individual dp records for storage if needed
    for dp in dp_list:
        record = {
            "device_id": device_id,
            "timestamp": timestamp,
            "code": dp.get("code"),
            "value": dp.get("value")
        }
        records.append(record)
    return snapshot, records

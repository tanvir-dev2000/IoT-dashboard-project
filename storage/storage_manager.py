# storage/storage_manager.py

import sqlite3
from env import env as env
import storage.authenticate_gsheets as auth_gsheets

# Google Sheets
def insert_data_into_google_sheet(snapshot):
    try:
        client = auth_gsheets.get_gsheets_client()
        sheet = client.open(env.GOOGLE_SHEETS_NAME).sheet1

        row = [
            snapshot.get("timestamp"),
            snapshot.get("device_id"),
            snapshot.get("status"),
            snapshot.get("voltage"),
            snapshot.get("current"),
            snapshot.get("power")
        ]
        sheet.append_row(row)
        print("Inserted snapshot into Google Sheets.")
    except Exception as e:
        print(f"Failed to insert data into Google Sheets: {e}")

# SQLite (simplified example)
def insert_data_into_sqlite(record):
    try:
        conn = sqlite3.connect("data/devices_data.db")
        cursor = conn.cursor()
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_data (
                device_id TEXT,
                timestamp TEXT,
                code TEXT,
                value REAL
            )
        ''')
        cursor.execute('''
            INSERT INTO device_data (device_id, timestamp, code, value) 
            VALUES (?, ?, ?, ?)
        ''', (record['device_id'], record['timestamp'], record['code'], record['value']))
        conn.commit()
        conn.close()
        print("Inserted record into SQLite.")
    except Exception as e:
        print(f"Failed to insert data into SQLite: {e}")

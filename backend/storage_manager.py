import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import time
import datetime
import json  # Ensure json is imported here at the top


_json_dumps_func = json.dumps


_sqlite_conn = None
_sqlite_cursor = None
_gspread_gc = None
_master_google_spreadsheet = None
_dp_worksheets = {}
_raw_log_worksheet = None
_current_daily_worksheet = None
_last_checked_date_str = None

_db_file = None
_google_sheets_key_file = None
_google_sheet_name = None
_impersonated_user_email = None

SHEET_MAPPINGS = {
    "output_voltage": {"name": "Voltage Data", "headers": ["Timestamp", "Voltage (V)"]},
    "output_current": {"name": "Current Data", "headers": ["Timestamp", "Current (A)"]},
    "output_power": {"name": "Active Power Data", "headers": ["Timestamp", "Active Power (kW)"]},
    "total_forward_energy": {"name": "Total Energy Data", "headers": ["Timestamp", "Total Energy (kWh)"]},
    "power_factor": {"name": "Power Factor Data", "headers": ["Timestamp", "Power Factor"]},
    "supply_frequency": {"name": "Frequency Data", "headers": ["Timestamp", "Frequency (Hz)"]},
    "leakage_current": {"name": "Leakage Current Data", "headers": ["Timestamp", "Leakage Current (mA)"]},
    "switch": {"name": "Switch Status Log", "headers": ["Timestamp", "Switch Status"]},
    "fault": {"name": "Faults Log", "headers": ["Timestamp", "Faults"]},
}

RAW_LOG_SHEET_NAME = "All Raw Data Log"
RAW_LOG_HEADERS = ["Timestamp", "Device ID", "DP Code", "DP Name", "DP Value", "DP Unit", "DP Type"]


DAILY_SHEET_HEADERS = [
    "Time",
    "Breaker Switch",
    "Voltage (V)",
    "Frequency (Hz)",
    "Current (A)",
    "Active Power (kW)",
    "Power Factor"
]



def initialize_storage(db_file, google_sheets_key_file, google_sheet_name, impersonated_user_email=None):
    global _db_file, _google_sheets_key_file, _google_sheet_name, _impersonated_user_email
    _db_file = db_file
    _google_sheets_key_file = google_sheets_key_file
    _google_sheet_name = google_sheet_name
    _impersonated_user_email = impersonated_user_email

    _setup_sqlite_db()
    _setup_google_sheets()


def _setup_sqlite_db():
    global _sqlite_conn, _sqlite_cursor
    try:
        _sqlite_conn = sqlite3.connect(_db_file, check_same_thread=False)
        _sqlite_cursor = _sqlite_conn.cursor()
        _sqlite_cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                dp_code TEXT NOT NULL,
                dp_name TEXT NOT NULL,
                dp_value REAL, 
                dp_unit TEXT,
                dp_type TEXT
            )
        ''')
        _sqlite_conn.commit()
        print(f"Storage Manager: SQLite database '{_db_file}' opened and table 'device_data' ensured.")
    except sqlite3.Error as e:
        print(f"Storage Manager: Error setting up SQLite database: {e}")
        _sqlite_conn = None
        _sqlite_cursor = None


def insert_data_into_sqlite(data_record):
    if _sqlite_conn is None or _sqlite_cursor is None:
        return False
    try:
        _sqlite_cursor.execute('''
            INSERT INTO device_data (timestamp, device_id, dp_code, dp_name, dp_value, dp_unit, dp_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data_record['timestamp'], data_record['device_id'], data_record['dp_code'],
              data_record['dp_name'], data_record['dp_value_save'], data_record['dp_unit'], data_record['dp_type']))
        _sqlite_conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Storage Manager: Error inserting data into SQLite DB: {e}")
        return False


def _get_or_create_daily_worksheet():
    global _current_daily_worksheet, _last_checked_date_str

    if _master_google_spreadsheet is None:
        print("Storage Manager: Master Google Spreadsheet not available to create daily sheet.")
        return None

    today_date_str = datetime.datetime.now().strftime('%d/%m/%Y')

    if _current_daily_worksheet and _current_daily_worksheet.title == today_date_str:
        return _current_daily_worksheet

    print(f"Storage Manager: Checking for/creating daily sheet for {today_date_str}...")
    try:
        worksheet = _master_google_spreadsheet.worksheet(today_date_str)
        print(f"Storage Manager: Found existing sheet '{today_date_str}'.")
    except gspread.exceptions.WorksheetNotFound:
        print(f"Storage Manager: Creating new sheet '{today_date_str}'...")
        worksheet = _master_google_spreadsheet.add_worksheet(title=today_date_str, rows="1000", cols="20")

    if not worksheet.row_values(1):
        worksheet.append_row(DAILY_SHEET_HEADERS)  # <--- DAILY_SHEET_HEADERS is used here
        print(f"Storage Manager: Headers added to '{today_date_str}'.")

    _last_checked_date_str = today_date_str
    _current_daily_worksheet = worksheet
    return worksheet


def _setup_google_sheets():
    global _gspread_gc, _master_google_spreadsheet, _dp_worksheets, _raw_log_worksheet, _current_daily_worksheet, _last_checked_date_str
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

        creds = Credentials.from_service_account_file(_google_sheets_key_file, scopes=scope)


        _gspread_gc = gspread.authorize(creds)

        # --- Open the Master Spreadsheet ---
        try:
            _master_google_spreadsheet = _gspread_gc.open(_google_sheet_name)
            print(f"Storage Manager: Successfully opened Master Google Sheet: '{_google_sheet_name}'.")
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"Storage Manager: Error: Master Google Sheet '{_google_sheet_name}' not found.")
            print(
                f"Storage Manager: Please create it manually and ensure it's shared with '{creds.service_account_email}'.")
            _master_google_spreadsheet = None
            return

            # --- Setup Raw Log Worksheet ---
        try:
            _raw_log_worksheet = _master_google_spreadsheet.worksheet(RAW_LOG_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Storage Manager: Creating '{RAW_LOG_SHEET_NAME}' worksheet for raw data...")
            _raw_log_worksheet = _master_google_spreadsheet.add_worksheet(title=RAW_LOG_SHEET_NAME, rows="1000",
                                                                          cols="20")

        if not _raw_log_worksheet.row_values(1):
            _raw_log_worksheet.append_row(RAW_LOG_HEADERS)
            print(f"Storage Manager: '{_raw_log_worksheet.title}' headers added.")


        _current_daily_worksheet = _get_or_create_daily_worksheet()
        if _current_daily_worksheet:
            print(f"Storage Manager: Initial daily sheet '{_current_daily_worksheet.title}' set up.")
        else:
            print("Storage Manager: Failed to set up initial daily sheet.")

    except Exception as e:
        print(f"Storage Manager: Error setting up Google Sheets: {e}")
        _gspread_gc = None
        _master_google_spreadsheet = None
        _dp_worksheets = {}
        _raw_log_worksheet = None
        _current_daily_worksheet = None


def insert_data_into_google_sheet(snapshot_data):
    if _master_google_spreadsheet is None:
        print("Storage Manager: Master Google Sheet not connected. Cannot insert data.")
        return False

    try:

        today_date_str = datetime.datetime.now().strftime('%d/%m/%Y')
        if today_date_str != _last_checked_date_str:
            print(f"Storage Manager: New day detected ({today_date_str}). Switching to new daily sheet...")
            _get_or_create_daily_worksheet()
            if _current_daily_worksheet is None:
                print("Storage Manager: Failed to get/create daily sheet for new day. Skipping Google Sheets insert.")
                return False


        raw_log_row = [
            snapshot_data['timestamp'],
            snapshot_data['device_id'],
            _json_dumps_func(snapshot_data['dp_code_raw']),
            "N/A",
            "N/A",
            "N/A",
            "N/A"
        ]
        if _raw_log_worksheet:
            _raw_log_worksheet.append_row(raw_log_row)
        else:
            print(f"Storage Manager: Raw log sheet not available. Raw data not saved to GS.")


        if _current_daily_worksheet:
            daily_row = [
                snapshot_data["time_12hr"],
                snapshot_data["Breaker Switch"],
                snapshot_data["Voltage (V)"],
                snapshot_data["Frequency (Hz)"],
                snapshot_data["Current (A)"],
                snapshot_data["Active Power (kW)"],
                snapshot_data["Power Factor"]
            ]
            _current_daily_worksheet.append_row(daily_row)
        else:
            print(f"Storage Manager: Daily sheet not available. Fixed-column data not saved to GS.")

        return True
    except Exception as e:
        print(f"Storage Manager: Error inserting data into Google Sheet: {e}")
        return False


def close_storage():
    if _sqlite_conn:
        _sqlite_conn.close()
        print("Storage Manager: SQLite database connection closed.")
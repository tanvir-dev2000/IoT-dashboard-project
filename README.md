# IoT Dashboard - Circuit Breaker Monitoring System

A comprehensive IoT dashboard for monitoring and controlling circuit breaker devices through the Tuya Cloud API with real-time data visualization and historical analytics.

## URL: https://iot-dashboard-project.onrender.com
## 🚀 Features

- **Real-time Monitoring**: Live power consumption, voltage, current, and frequency tracking
- **Remote Control**: Turn circuit breaker ON/OFF remotely
- **Data Persistence**: Dual storage with SQLite and Google Sheets integration
- **Interactive Dashboard**: Modern Streamlit-based web interface
- **Historical Analytics**: Time-series data visualization with Plotly
- **Auto-refresh**: Real-time updates every 30 seconds
- **MQTT Support**: Real-time device status updates via Tuya MQTT
- **Offline Detection**: Automatic handling of device offline states

## 📋 Prerequisites

- Python 3.7+
- Tuya Cloud Developer Account
- Google Cloud Service Account (for Sheets integration)
- Circuit breaker device compatible with Tuya IoT platform

## 🛠️ Installation

1. **Clone the repository**
```
git clone <repository-url>
cd iot-dashboard
```

2. **Install dependencies**
```
pip install streamlit pandas plotly gspread google-auth tuya-iot-py-sdk streamlit-autorefresh
```


3. **Configure environment variables**

Edit `env/env.py` with your credentials:
```commandline
ENDPOINT = "https://openapi.tuyaeu.com" # Your Tuya region endpoint
ACCESS_ID = "your_access_id"
ACCESS_KEY = "your_access_key"
DEVICE_ID = "your_device_id"
USERNAME = "your_tuya_username"
PASSWORD = "your_tuya_password"
SERVICE_ACCOUNT_FILE = 'credentials.json'
GOOGLE_SHEETS_NAME = 'Data Log'
POLLING_INTERVAL_SECONDS = 300
```

4. **Setup Google Sheets authentication**
- Place your Google Cloud service account JSON file as `credentials.json` in the root directory
- Create a Google Sheet named "Data Log" and share it with your service account email

## 🚀 Usage

1. **Start the dashboard**
```commandline
streamlit run dashboard/dashboard.py
```


2. **Access the web interface**
- Open your browser to `http://localhost:8501`
- Navigate between Dashboard and History pages using the sidebar

3. **Dashboard Features**
- **🏠 Dashboard**: Real-time metrics, device control, and live charts
- **📊 History**: Historical data analysis with customizable date ranges

## 📊 Data Storage

- **SQLite**: Local database (`backend/tuya_device_data.db`) for detailed device data points
- **Google Sheets**: Cloud backup with daily worksheets and raw data logs
- **Automatic Rotation**: Daily sheets created automatically with proper headers

## 🔧 Configuration

### Tuya Cloud Setup
1. Create a developer account at [Tuya IoT Platform](https://iot.tuya.com/)
2. Create a cloud project and obtain API credentials
3. Link your circuit breaker device to the project

### Google Sheets Setup
1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a service account and download the JSON key
4. Share your target spreadsheet with the service account email

## 🏗️ Project Structure

```commandline
iot-dashboard/
├── assets/ # Project assets
│ └── logo.png
├── backend/ # Core business logic
│ ├── main.py # Main application entry
│ ├── tuya_client.py # Tuya API integration
│ ├── data_processor.py # Data processing and formatting
│ ├── storage_manager.py # Database and Sheets management
│ └── tuya_device_data.db # SQLite database
├── dashboard/ # UI components
│ ├── dashboard.py # Real-time dashboard
│ └── history.py # Historical analytics
├── env/ # Configuration
│ └── env.py # Environment variables
├── storage/ # Google Sheets integration
│ └── authenticate_gsheets.py
└── tuya_iot/ # Tuya IoT SDK components
├── openapi.py
├── openmq.py
└── ...
```


## 📈 Monitoring Capabilities

- **Electrical Parameters**: Voltage, Current, Power, Frequency
- **Switch Status**: Circuit breaker ON/OFF state
- **Power Factor**: Electrical efficiency metrics
- **Fault Detection**: Automatic alarm monitoring
- **Energy Consumption**: Total forward energy tracking

## 🔄 Data Flow

1. **Real-time**: MQTT listener receives instant device updates
2. **Polling**: Periodic API calls every 5 minutes (configurable)
3. **Processing**: Raw device data converted to readable metrics
4. **Storage**: Simultaneous saving to SQLite and Google Sheets
5. **Visualization**: Live dashboard updates with processed data

## 🛡️ Error Handling

- Automatic token refresh for Tuya API
- Offline device detection and handling
- Graceful fallback to polling if MQTT fails
- Data persistence during connection interruptions

## 🚀 Getting Started

1. Set up your Tuya developer account and obtain device credentials
2. Configure Google Sheets API access
3. Update `env/env.py` with your configuration
4. Run `python backend/main.py` to start data collection
5. Launch the dashboard with `streamlit run dashboard/dashboard.py`

## 📝 License

This project is for educational and monitoring purposes. Ensure compliance with your local electrical codes and Tuya's terms of service.

**⚡ Monitor your power, control your future!**

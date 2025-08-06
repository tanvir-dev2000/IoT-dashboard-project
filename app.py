import logging, os, sys, threading
import streamlit as st
from streamlit_autorefresh import st_autorefresh

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from backend.timezone_utils import setup_timezone
setup_timezone()

import env
from backend import tuya_client, storage_manager
from dashboard.dashboard import dashboard_page
from dashboard.history import history_page

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s")

st.set_page_config(
    page_title="IoT LoG",
    page_icon="assets/logo.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

st_autorefresh(interval=30_000, key="autorefresh")

st.markdown(
    """
    <style>
    [data-testid="stSidebarContent"] > div:first-child {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
@st.cache_resource(show_spinner=False)
def start_backend() -> threading.Event:
    storage_manager.initialize_storage(
        db_file=os.path.join(current_dir, "tuya_device_data.db"),
        google_sheets_key_file=env.SERVICE_ACCOUNT_FILE,
        google_sheet_name=env.GOOGLE_SHEETS_NAME,
    )

    if not tuya_client.initialize_tuya_client():
        raise RuntimeError("Could not connect to Tuya Cloud API")

    if not tuya_client.start_mqtt_listener():
        logging.warning("MQTT listener failed – continuing with polling only")

    if env.POLLING_INTERVAL_SECONDS > 0:
        tuya_client.start_polling_loop()

    logging.info("Backend started successfully")
    stop_evt = threading.Event()
    return stop_evt


_ = start_backend()




if __name__ == "__main__":
    # Create sidebar FIRST, before any other page content
    st.sidebar.title("⚡ IoT Monitor")
    st.sidebar.markdown("---")

    # Simple navigation
    page = st.sidebar.radio(
        "Choose Page:",
        ["🏠 Dashboard", "📊 History"]
    )


    if "Dashboard" in page:
        dashboard_page()
    else:
        history_page()

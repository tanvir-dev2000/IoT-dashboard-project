# app.py  (no type hints)
import streamlit as st
import threading
import time
import sys
import os
import logging
import queue
from datetime import datetime

# ------------------------------------------------------------------ #
#  Path setup                                                        #
# ------------------------------------------------------------------ #
ROOT_DIR = os.path.dirname(__file__)
sys.path.append(ROOT_DIR)
sys.path.append(os.path.join(ROOT_DIR, "backend"))
sys.path.append(os.path.join(ROOT_DIR, "env"))

import app_config as env
from backend import tuya_client
from backend import storage_manager
from dashboard.dashboard import dashboard_page
from dashboard.history import history_page
from streamlit_autorefresh import st_autorefresh

# ------------------------------------------------------------------ #
#  Misc Streamlit config                                             #
# ------------------------------------------------------------------ #
st.set_page_config(page_title="IoT Log", page_icon="⚡", layout="wide")
st_autorefresh(interval=30_000, limit=None, key="autorefresh")

# ------------------------------------------------------------------ #
#  Logging                                                           #
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------------------------------------------------------ #
#  Thread-shared flags & helpers                                     #
# ------------------------------------------------------------------ #
STATUS_Q = queue.Queue()      # holds (status, message, timestamp)
GLOBAL_BACKEND_LOCK = threading.Lock()
GLOBAL_BACKEND_THREAD = None
GLOBAL_BACKEND_STOP_EVENT = threading.Event()
BACKEND_PID_FILE = os.path.join(ROOT_DIR, ".backend_pid")


def _push_status(status, msg=""):
    """Thread-safe status update."""
    STATUS_Q.put((status, msg, datetime.now()))


def _read_pid_file():
    try:
        with open(BACKEND_PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _write_pid_file():
    try:
        with open(BACKEND_PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception as exc:
        print(f"Unable to write backend pid file: {exc}")


def _remove_pid_file():
    try:
        if os.path.exists(BACKEND_PID_FILE):
            os.remove(BACKEND_PID_FILE)
    except Exception as exc:
        print(f"Unable to remove backend pid file: {exc}")


def _is_process_alive(pid):
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _another_backend_running():
    pid = _read_pid_file()
    if pid is None:
        return False
    if pid == os.getpid():
        return False
    if _is_process_alive(pid):
        print(f"Another backend process is already running with pid={pid}")
        return True
    _remove_pid_file()
    return False


def _get_backend_thread():
    thread = st.session_state.get("backend_thread")
    if thread is not None:
        return thread
    return GLOBAL_BACKEND_THREAD


def _set_backend_thread(thread):
    st.session_state.backend_thread = thread
    global GLOBAL_BACKEND_THREAD
    GLOBAL_BACKEND_THREAD = thread


def _get_stop_event():
    return GLOBAL_BACKEND_STOP_EVENT


# ------------------------------------------------------------------ #
#  Backend initialisation                                            #
# ------------------------------------------------------------------ #
def _init_backend():
    try:
        _push_status("initialising", "Setting up storage...")
        storage_manager.initialize_storage(
            db_file="tuya_device_data.db",
            google_sheets_key_file=env.SERVICE_ACCOUNT_FILE,
            google_sheet_name=env.GOOGLE_SHEETS_NAME,
        )

        _push_status("initialising", "Connecting to Tuya API…")
        if not tuya_client.initialize_tuya_client():
            _push_status("error", "Could not connect to Tuya Cloud API")
            return False

        _push_status("initialising", "Starting MQTT listener…")
        if not tuya_client.start_mqtt_listener():
            _push_status("error", "Could not start MQTT listener")
            return False

        if env.POLLING_INTERVAL_SECONDS > 0:
            tuya_client.start_polling_loop()

        _push_status("running", "Backend up & running")
        return True

    except Exception as exc:   # noqa: B902, E722
        _push_status("error", "Initialisation failed: {}".format(exc))
        return False


# ------------------------------------------------------------------ #
#  Worker thread                                                     #
# ------------------------------------------------------------------ #
def _backend_worker():
    print("Backend worker: started")
    try:
        if not _init_backend():
            _push_status("error", "Backend initialization failed")
            return

        # Keep the worker alive but don't spam
        while not _get_stop_event().is_set():
            time.sleep(5)  # Check every 5 seconds instead of 1

    except Exception as exc:
        _push_status("error", f"Worker exception: {exc}")
    finally:
        try:
            tuya_client.stop_tuya_client()
            storage_manager.close_storage()
        except Exception as cleanup_exc:
            print(f"Cleanup error: {cleanup_exc}")
        _push_status("stopped", "Backend shut down")


def _start_backend():
    if st.session_state.get("backend_started", False):
        return

    if _another_backend_running():
        _push_status("error", "Backend already running in another Streamlit process")
        return

    with GLOBAL_BACKEND_LOCK:
        backend_thread = _get_backend_thread()
        if backend_thread and backend_thread.is_alive():
            print(f"Backend thread already running (id={backend_thread.ident})")
            st.session_state.backend_started = True
            st.session_state.backend_status = "running"
            return

        _write_pid_file()
        st.session_state.backend_started = True
        st.session_state.backend_status = "initialising"
        st.session_state.backend_msg = ""
        st.session_state.backend_ts = datetime.now()

        stop_event = _get_stop_event()
        stop_event.clear()

        backend_thread = threading.Thread(target=_backend_worker, daemon=True)
        _set_backend_thread(backend_thread)
        backend_thread.start()
        print(f"Backend thread started (id={backend_thread.ident})")


def _stop_backend():
    print("Stopping backend thread...")
    _get_stop_event().set()
    _remove_pid_file()
    st.session_state.backend_started = False
    st.session_state.backend_status = "stopped"


# ------------------------------------------------------------------ #
#  UI helpers                                                        #
# ------------------------------------------------------------------ #
def _drain_status_queue():
    while not STATUS_Q.empty():
        status, msg, ts = STATUS_Q.get_nowait()
        st.session_state.backend_status = status
        st.session_state.backend_msg = msg
        st.session_state.backend_ts = ts


def sidebar():
    with st.sidebar:
        st.title("⚡ IoT Power Monitor")

        status = st.session_state.get("backend_status", "starting")
        msg    = st.session_state.get("backend_msg", "")
        badge_text, badge_fn = {
            "running": ("🟢 Running",  st.success),
            "initialising": ("🟡 Starting …", st.info),
            "starting": ("🟡 Starting …", st.info),
            "stopped": ("⚪ Stopped",  st.warning),
            "error": ("🔴 Error",     st.error),
        }[status]
        badge_fn(badge_text)
        if msg:
            st.caption(msg)
        if ts := st.session_state.get("backend_ts"):
            st.caption("Last update {}".format(ts.strftime("%H:%M:%S")))

        st.markdown("---")
        page = st.radio("Navigate to :", ["Dashboard", "History"], index=0)
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Restart"):
                _stop_backend()
                _start_backend()
                st.rerun()
        with col2:
            if st.button("ℹ️ Thread status"):
                backend_thread = _get_backend_thread()
                alive = backend_thread.is_alive() if backend_thread else False
                st.info("Thread: {}".format("alive" if alive else "dead"))

        return page


# ------------------------------------------------------------------ #
#  Main Streamlit logic                                              #
# ------------------------------------------------------------------ #
def main():
    if "backend_status" not in st.session_state:
        st.session_state.backend_status = "starting"
        st.session_state.backend_msg = ""
        st.session_state.backend_ts = datetime.now()

    _drain_status_queue()

    if st.session_state.backend_status == "starting":
        _start_backend()

    page = sidebar()

    try:
        if page == "Dashboard":
            dashboard_page()
        else:
            history_page()
    except Exception as exc:   # noqa: B902, E722
        st.error("Page error: {}".format(exc))
        st.info("Backend may still be initialising. Please wait & refresh.")


# ------------------------------------------------------------------ #
#  Entrypoint                                                        #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _stop_backend()
    except Exception as exc:   # noqa: B902, E722
        st.error("Fatal app error: {}".format(exc))
        _stop_backend()

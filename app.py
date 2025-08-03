import streamlit as st

from dashboard.dashboard import dashboard_page
from dashboard.history import history_page

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30000, limit=None, key="autorefresh")
st.set_page_config(
    page_title="IoT LoG",
    page_icon="assets/logo.png",
    layout="wide"
)

def main():
    st.sidebar.title("Navigation")
    pages = {
        "Dashboard": dashboard_page,
        "History": history_page,
    }

    # User selects page from sidebar radio buttons
    selected_page = st.sidebar.radio("Go to", list(pages.keys()))
    pages[selected_page]()

if __name__ == "__main__":
    main()

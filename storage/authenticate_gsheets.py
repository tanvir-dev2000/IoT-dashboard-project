# storage/authenticate_gsheets.py
import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import env.env as env

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def get_gsheets_client():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    creds = Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    return client

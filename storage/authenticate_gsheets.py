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
    creds = Credentials.from_service_account_file(env.SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    client = gspread.authorize(creds)
    return client

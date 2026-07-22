import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
from storage.authenticate_gsheets import get_gsheets_client
import app_config as env
from datetime import datetime

def calculate_cost(units_kwh):
    slabs = [
        (50, 4.63),
        (25, 5.26),
        (125, 7.20),
        (100, 7.59),
        (100, 8.02),
        (200, 12.67),
        (float('inf'), 14.61)
    ]
    remaining = units_kwh
    total = 0
    for limit, rate in slabs:
        use = min(remaining, limit)
        total += use * rate
        remaining -= use
        if remaining <= 0:
            break
    return total

def history_page():
    st.title("IoT Power History")

    # Don't cache client or spreadsheet objects
    client = get_gsheets_client()
    spreadsheet = client.open(env.GOOGLE_SHEETS_NAME)
    all_worksheets = spreadsheet.worksheets()
    date_sheets = [
        ws for ws in all_worksheets
        if ws.title.count("/") == 2 and len(ws.title) == 10
    ]
    date_names = sorted([ws.title for ws in date_sheets], reverse=True)
    date_format = '%d/%m/%Y'
    # Sort dates chronologically (latest first)
    date_names_sorted = sorted(
        date_names,
        key=lambda d: datetime.strptime(d, date_format)
    )[::-1]

    if not date_names:
        st.info("No data logs available.")
        return

    selected_date = st.selectbox("Select a log date", date_names_sorted)

    try:
        # Always freshly get the worksheet and rows
        worksheet = spreadsheet.worksheet(selected_date)
        data = worksheet.get_all_records()
    except Exception as e:
        st.error(f"Could not load worksheet '{selected_date}': {e}")
        return

    if not data:
        st.warning(f"No data logged for the selected date: {selected_date}")
        return

    df1 = pd.DataFrame(data)
    if 'Time' in df1.columns and 'Active Power (kW)' in df1.columns:
        # Parse strict 12-hour time, drop bad rows, order
        df1['Time'] = pd.to_datetime(df1['Time'], format='%I:%M:%S %p', errors='coerce')
        df1 = df1.dropna(subset=['Time'])
        df1 = df1.sort_values('Time').reset_index(drop=True)
        df1['delta_sec'] = df1['Time'].diff().dt.total_seconds().fillna(0)
        df1.loc[df1['delta_sec'] <= 0, 'delta_sec'] = 1
        df1['Active Power (kW)'] = pd.to_numeric(df1['Active Power (kW)'], errors='coerce')
        df1['energy_kwh'] = df1['Active Power (kW)'] * (df1['delta_sec'] / 3600)
        df1.loc[df1['energy_kwh'] < 0, 'energy_kwh'] = 0
        df1['cum_energy_kwh'] = df1['energy_kwh'].cumsum()
        df1['cumulative_cost_bdt'] = df1['cum_energy_kwh'].apply(calculate_cost)
        total_kwh = df1['cum_energy_kwh'].iloc[-1] if len(df1) > 0 else 0
        total_cost = df1['cumulative_cost_bdt'].iloc[-1] if len(df1) > 0 else 0

        st.metric("Total kWh Used", f"{total_kwh:.3f}")
        st.metric("Total Cost (৳)", f"{total_cost:.2f}")

        import plotly.express as px
        fig_cost = px.line(
            df1, x='Time', y='cumulative_cost_bdt',
            title="Cumulative Cost Over Time (৳)",
            labels={"cumulative_cost_bdt": "BDT", "Time": "Time"}
        )
        fig_cost.update_xaxes(tickangle=90, tickformat="%I:%M %p")
        st.plotly_chart(fig_cost, use_container_width=True)
    else:
        st.info("Data does not have energy/cost calculation columns.")

    df = pd.DataFrame(data)
    st.subheader(f"Data Preview for {selected_date}")
    st.dataframe(df)

    # Example graphs: adjust columns to your data
    import plotly.express as px

    if 'Time' in df.columns and 'Voltage (V)' in df.columns:
        fig1 = px.line(df, x='Time', y='Voltage (V)', title='Voltage over Time')
        fig1.update_xaxes(tickangle=90)
        st.plotly_chart(fig1, use_container_width=True)

    if 'Time' in df.columns and 'Active Power (kW)' in df.columns:
        fig2 = px.line(df, x='Time', y='Active Power (kW)', title='Power over Time')
        fig2.update_xaxes(tickangle=90)
        st.plotly_chart(fig2, use_container_width=True)

    if 'Time' in df.columns and 'Current (A)' in df.columns:
        fig3 = px.line(df, x='Time', y='Current (A)', title='Current over Time')
        fig3.update_xaxes(tickangle=90)
        st.plotly_chart(fig3, use_container_width=True)

    # Provide CSV download
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv_bytes, f"{selected_date}.csv", "text/csv")

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import datetime
import storage
from storage import authenticate_gsheets as auth_gsheets
import env
from gspread.exceptions import WorksheetNotFound

import plotly.express as px



# Auto-refresh every 30 seconds


def calculate_cost(units_kwh):
    slabs = [
        (50, 4.63),    # First 50 units
        (25, 5.26),    # Next 25
        (125, 7.20),   # Next 125
        (100, 7.59),   # Next 100
        (100, 8.02),   # Next 100
        (200, 12.67),  # Next 200
        (float('inf'), 14.61)  # Above 600
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



def get_latest_data(client, spreadsheet_name, sheet_name):
    try:
        sheet = client.open(spreadsheet_name).worksheet(sheet_name)
        all_records = sheet.get_all_records()
        if all_records:
            return all_records[-1], all_records
        else:
            return None, None
    except WorksheetNotFound:
        st.warning(f"Today's sheet/tab '{sheet_name}' not found in '{spreadsheet_name}'.")
        return None, None

def plot_pretty_line_chart(df, y_column, title, color):
    if y_column in df.columns and "Time" in df.columns:
        df = df.copy()
        df["Time"] = pd.to_datetime(df["Time"], format="%I:%M:%S %p", errors='coerce')
        yvals = pd.to_numeric(df[y_column], errors='coerce')
        if yvals.notnull().any():
            earliest = df["Time"].min().replace(hour=0, minute=0, second=0, microsecond=0)
            latest = df["Time"].max()
            five_hours_ago = max(latest - pd.Timedelta(hours=5), earliest)

            fig = px.line(
                df,
                x="Time",
                y=y_column,
                title=title,
                line_shape="spline",
                markers=True,
                color_discrete_sequence=[color],
                labels={y_column: title, "Time": "Time"},
            )
            fig.update_xaxes(
                range=[five_hours_ago, latest],
                fixedrange=True,
                rangeslider=dict(
                    visible=True,
                    range=[earliest, latest],
                    bgcolor="#E3EAF2",
                    thickness=0.12
                ),
                tickformat="%I:%M %p"
            )
            fig.update_yaxes(fixedrange=True)
            fig.update_layout(
                dragmode=False,
                hovermode="x unified",
                showlegend=False,
                plot_bgcolor="#F5F6FA",
                height=500,
                margin=dict(t=40, l=0, r=0, b=0),
                title_font_size=16,
                xaxis_title="Time",
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "scrollZoom": False,
                    "staticPlot": False
                }
            )

def dashboard_page():
    client = auth_gsheets.get_gsheets_client()
    today_tab = datetime.datetime.now().strftime("%d/%m/%Y")
    latest_data, all_records = get_latest_data(client, env.GOOGLE_SHEETS_NAME, today_tab)

    if latest_data:
        breaker_switch = (latest_data.get("Breaker Switch") or latest_data.get("breaker switch") or latest_data.get("BreakerSwitch") or "Unknown").lower()
        if breaker_switch == "on":
            st.success("🟢 Device Status: ON")
        elif breaker_switch == "off":
            st.error("🔴 Device Status: OFF")
        else:
            st.warning("⚪ Device Status: Unknown")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Voltage (V)", latest_data.get("Voltage (V)", "N/A"))
        col2.metric("Current (A)", latest_data.get("Current (A)", "N/A"))
        col3.metric("Active Power (kW)", latest_data.get("Active Power (kW)", "N/A"))
        col4.metric("Power Factor", latest_data.get("Power Factor", "N/A"))


        df1 = pd.DataFrame(all_records)
        if 'Time' in df1.columns and 'Active Power (kW)' in df1.columns:
            df1['Time'] = pd.to_datetime(df1['Time'], format='%I:%M:%S %p', errors='coerce')
            df1 = df1.dropna(subset=['Time'])
            df1 = df1.sort_values('Time')

            df1['delta_sec'] = df1['Time'].diff().dt.total_seconds().fillna(0)
            df1.loc[df1['delta_sec'] <= 0, 'delta_sec'] = 1  # minimal interval

            df1['Active Power (kW)'] = pd.to_numeric(df1['Active Power (kW)'], errors='coerce')
            df1['energy_kwh'] = df1['Active Power (kW)'] * (df1['delta_sec'] / 3600)
            df1.loc[df1['energy_kwh'] < 0, 'energy_kwh'] = 0

            total_kwh = df1['energy_kwh'].sum()
            cumulative_cost = calculate_cost(total_kwh)
        else:
            total_kwh = 0
            cumulative_cost = 0

        col5.metric("Cumulative Cost (৳)", f"{cumulative_cost:.2f}")
        df = pd.DataFrame(all_records)

        if "Breaker Switch" in df.columns:
            df = df.drop(columns=["Breaker Switch"])
        numeric_cols = ["Voltage (V)", "Current (A)", "Active Power (kW)", "Power Factor"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        timestamp = latest_data.get("Time") or latest_data.get("time") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"Last Updated: {timestamp}")

        st.markdown("### Voltage Over Time")
        plot_pretty_line_chart(df, "Voltage (V)", "Voltage (V)", "#0081B8")

        st.markdown("### Current Over Time")
        plot_pretty_line_chart(df, "Current (A)", "Current (A)", "#E37153")

        st.markdown("### Active Power Over Time")
        plot_pretty_line_chart(df, "Active Power (kW)", "Active Power (kW)", "#4CAF50")

        with st.expander("Show Today's Full Data Table"):
            st.dataframe(df, use_container_width=True)
    else:
        st.warning(f"No data available for today ({today_tab}).")

if __name__ == "__main__":
    dashboard_page()

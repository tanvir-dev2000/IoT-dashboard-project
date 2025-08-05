import streamlit as st
import pandas as pd
import datetime
from storage import authenticate_gsheets as auth_gsheets
import env
from gspread.exceptions import WorksheetNotFound
import plotly.graph_objects as go
from backend import tuya_client


CUSTOM_CSS = """
<style>
    /* Main container and layout */
    .stApp {
        background-color: #f0f2f6;
        font-family: 'Inter', sans-serif;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Custom header with gradient */
    .page-header {
        background: linear-gradient(135deg, #1f2937 0%, #4b5563 100%);
        padding: 2.5rem;
        border-radius: 15px;
        margin-bottom: 2.5rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .page-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -1px;
    }
    .page-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.8;
        font-size: 1rem;
    }

    /* Custom metric cards */
    .metric-card-container {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 2rem;
        flex-wrap: wrap;
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border: 1px solid #e5e7eb;
        flex: 1;
        min-width: 180px;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
    }
    .metric-card-title {
        color: #4b5563;
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    .metric-card-value {
        color: #1f2937;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
    }

    /* Chart sections */
    .chart-container {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border: 1px solid #e5e7eb;
        margin-bottom: 2rem;
    }

    /* Status indicators */
    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding: 1rem;
        border-radius: 8px;
        background: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .status-on { color: #10b981; }
    .status-off { color: #ef4444; }
    .status-unknown { color: #9ca3af; }
    .status-dot {
        height: 12px;
        width: 12px;
        border-radius: 50%;
    }
    .dot-on { background-color: #10b981; }
    .dot-off { background-color: #ef4444; }
    .dot-unknown { background-color: #9ca3af; }

    /* ONLY hide these specific elements - NOT the sidebar */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
"""


def create_metric_card(title, value):
    return f"""
        <div class="metric-card">
            <div class="metric-card-title">{title}</div>
            <div class="metric-card-value">{value}</div>
        </div>
    """


def calculate_cost(units_kwh):
    """Calculate electricity cost based on DPDC tariff slabs"""
    slabs = [
        (50, 4.63), (25, 5.26), (125, 7.20), (100, 7.59),
        (100, 8.02), (200, 12.67), (float('inf'), 14.61)
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
    """Get the latest data from Google Sheets"""
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
    """Create modern line charts with better styling"""
    if y_column in df.columns and "Time" in df.columns:
        df = df.copy()

        try:
            df["Time"] = pd.to_datetime(df["Time"], format="%I:%M:%S %p", errors='coerce')
        except (ValueError, TypeError):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df["Time"] = pd.to_datetime(df["Time"], errors='coerce')

        df = df.dropna(subset=['Time'])
        yvals = pd.to_numeric(df[y_column], errors='coerce')

        if yvals.notnull().any() and len(df) > 0:
            earliest = df["Time"].min()
            latest = df["Time"].max()

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df["Time"],
                y=yvals,
                mode='lines+markers',
                name=y_column,
                line=dict(color=color, width=3, shape='spline'),
                marker=dict(size=6, color=color, symbol='circle'),
                hovertemplate='%{x|%I:%M:%S %p}<br>' + f'{title}: %{{y}}<extra></extra>',
                fill='tonexty',
                fillcolor=f'rgba({int(color[1:3], 16) if len(color) > 1 else 76}, {int(color[3:5], 16) if len(color) > 3 else 114}, {int(color[5:7], 16) if len(color) > 5 else 176}, 0.1)'
            ))

            fig.update_layout(
                title=f'<span style="font-size:18px; font-weight: bold; color: #1f2937;">{title} Over Time</span>',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family='Inter',
                margin=dict(t=60, b=40, l=40, r=40),
                height=400,
                xaxis=dict(
                    title_text="Time",
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)',
                    linecolor='#d1d5db',
                    tickformat="%I:%M %p",
                    range=[earliest, latest] if earliest != latest else None,
                ),
                yaxis=dict(
                    title_text=title,
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)',
                    linecolor='#d1d5db',
                ),
                hovermode="x unified",
                showlegend=False,
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

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


    st.markdown("""
        <div class="page-header">
            <h1>⚡ IoT Power Monitor</h1>
            <p>Real-time power consumption analytics</p>
        </div>
        """, unsafe_allow_html=True)

    client = auth_gsheets.get_gsheets_client()
    today_tab = datetime.datetime.now().strftime("%d/%m/%Y")
    latest_data, all_records = get_latest_data(client, env.GOOGLE_SHEETS_NAME, today_tab)

    if latest_data:

        breaker_switch = str(latest_data.get("Breaker Switch", "Unknown")).lower()
        if breaker_switch == "on":
            status_text = "ONLINE & ACTIVE"
            status_class = "status-on"
            dot_class = "dot-on"
        elif breaker_switch == "off":
            status_text = "OFFLINE"
            status_class = "status-off"
            dot_class = "dot-off"
        else:
            status_text = "UNKNOWN"
            status_class = "status-unknown"
            dot_class = "dot-unknown"

        st.markdown(
            f'<div class="status-indicator {status_class}"><span class="status-dot {dot_class}"></span>Device Status: {status_text}</div>',
            unsafe_allow_html=True)


        st.markdown("---")

        current_breaker_status = False
        try:
            status = tuya_client.get_switch_status()
            if status is not None:
                current_breaker_status = status
        except:
            pass

        if 'breaker_toggle' not in st.session_state:
            st.session_state.breaker_toggle = current_breaker_status


        st.markdown("### 🔧 Circuit Breaker Control")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            # Status display
            if st.session_state.breaker_toggle:
                st.success("🟢 Circuit Breaker: **ONLINE**")
            else:
                st.error("🔴 Circuit Breaker: **OFFLINE**")

            # Toggle
            breaker_toggle = st.toggle(
                "🔌 Power Control",
                value=st.session_state.breaker_toggle,
                key="compact_breaker_toggle"
            )

            # Control logic (same as above)
            if breaker_toggle != st.session_state.breaker_toggle:
                action = "ON" if breaker_toggle else "OFF"
                with st.spinner(f"Turning {action}..."):
                    try:
                        if breaker_toggle:
                            result = tuya_client.turn_on_circuit_breaker()
                        else:
                            result = tuya_client.turn_off_circuit_breaker()

                        if result:
                            st.session_state.breaker_toggle = breaker_toggle
                            st.success(f"✅ Turned {action}")
                            import time
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Failed")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

        st.markdown("---")


        with st.container():
            st.markdown('<div class="metric-card-container">', unsafe_allow_html=True)
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.markdown(create_metric_card("Voltage (V)", latest_data.get("Voltage (V)", "N/A")),
                            unsafe_allow_html=True)
            with col2:
                st.markdown(create_metric_card("Current (A)", latest_data.get("Current (A)", "N/A")),
                            unsafe_allow_html=True)
            with col3:
                st.markdown(create_metric_card("Active Power (kW)", latest_data.get("Active Power (kW)", "N/A")),
                            unsafe_allow_html=True)
            with col4:
                st.markdown(create_metric_card("Power Factor", latest_data.get("Power Factor", "N/A")),
                            unsafe_allow_html=True)


            df1 = pd.DataFrame(all_records)
            total_kwh = 0
            cumulative_cost = 0

            if not df1.empty and 'Time' in df1.columns and 'Active Power (kW)' in df1.columns:
                try:
                    df1['Time'] = pd.to_datetime(df1['Time'], format='%I:%M:%S %p', errors='coerce')
                except:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        df1['Time'] = pd.to_datetime(df1['Time'], errors='coerce')

                df1 = df1.dropna(subset=['Time']).sort_values('Time')
                df1['delta_sec'] = df1['Time'].diff().dt.total_seconds().fillna(60)
                df1.loc[df1['delta_sec'] <= 0, 'delta_sec'] = 60
                df1['Active Power (kW)'] = pd.to_numeric(df1['Active Power (kW)'], errors='coerce').fillna(0)
                df1['energy_kwh'] = df1['Active Power (kW)'] * (df1['delta_sec'] / 3600)
                df1.loc[df1['energy_kwh'] < 0, 'energy_kwh'] = 0
                total_kwh = df1['energy_kwh'].sum()
                cumulative_cost = calculate_cost(total_kwh)

            with col5:
                st.markdown(create_metric_card("Today's Cost (৳)", f"{cumulative_cost:.2f}"),
                            unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)


        df = pd.DataFrame(all_records)
        if not df.empty:
            if "Breaker Switch" in df.columns:
                df = df.drop(columns=["Breaker Switch"])

            numeric_cols = ["Voltage (V)", "Current (A)", "Active Power (kW)", "Power Factor"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            st.markdown(f"""
            <div style="text-align: center; margin: 2rem 0; padding: 1rem; 
                        background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                <small style="color: #64748b;">🕒 Last Updated: {latest_data.get('Time', 'Unknown')} | 🔄 Auto-refresh every 30 seconds</small>
            </div>
            """, unsafe_allow_html=True)


            st.markdown("### 📊 Real-time Analytics")

            if not df.empty:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                plot_pretty_line_chart(df, "Voltage (V)", "Voltage", "#4c72b0")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                plot_pretty_line_chart(df, "Current (A)", "Current", "#dd8452")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                plot_pretty_line_chart(df, "Active Power (kW)", "Active Power", "#55a868")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                plot_pretty_line_chart(df, "Power Factor", "Power Factor", "#c44e52")
                st.markdown('</div>', unsafe_allow_html=True)

            # Data table in expander
            with st.expander("📋 Show Today's Full Data Table"):
                st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("📊 No chart data available - waiting for device readings...")
    else:
        st.error(f"📡 No data available for today ({today_tab}). Please check your device connection.")


if __name__ == "__main__":
    dashboard_page()

# history.py
import streamlit as st
import pandas as pd
from storage.authenticate_gsheets import get_gsheets_client
import env
from datetime import datetime
import plotly.graph_objects as go


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


def history_page():

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.title("IoT Power History")

    client = get_gsheets_client()
    spreadsheet = client.open(env.GOOGLE_SHEETS_NAME)
    all_worksheets = spreadsheet.worksheets()
    date_sheets = [
        ws for ws in all_worksheets
        if ws.title.count("/") == 2 and len(ws.title) == 10
    ]
    date_names = sorted([ws.title for ws in date_sheets], reverse=True)
    date_format = '%d/%m/%Y'
    date_names_sorted = sorted(
        date_names,
        key=lambda d: datetime.strptime(d, date_format)
    )[::-1]

    if not date_names:
        st.info("No data logs available.")
        return

    selected_date = st.selectbox("Select a log date", date_names_sorted)

    try:
        worksheet = spreadsheet.worksheet(selected_date)
        data = worksheet.get_all_records()
    except Exception as e:
        st.error(f"Could not load worksheet '{selected_date}': {e}")
        return

    if not data:
        st.warning(f"No data logged for the selected date: {selected_date}")
        return

    df = pd.DataFrame(data)
    if 'Time' in df.columns and 'Active Power (kW)' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'], format='%I:%M:%S %p', errors='coerce')
        df = df.dropna(subset=['Time'])
        df = df.sort_values('Time').reset_index(drop=True)
        df['delta_sec'] = df['Time'].diff().dt.total_seconds().fillna(0)
        df.loc[df['delta_sec'] <= 0, 'delta_sec'] = 1
        df['Active Power (kW)'] = pd.to_numeric(df['Active Power (kW)'], errors='coerce')
        df['energy_kwh'] = df['Active Power (kW)'] * (df['delta_sec'] / 3600)
        df.loc[df['energy_kwh'] < 0, 'energy_kwh'] = 0
        df['cum_energy_kwh'] = df['energy_kwh'].cumsum()
        df['cumulative_cost_bdt'] = df['cum_energy_kwh'].apply(calculate_cost)
        total_kwh = df['cum_energy_kwh'].iloc[-1] if len(df) > 0 else 0
        total_cost = df['cumulative_cost_bdt'].iloc[-1] if len(df) > 0 else 0

        st.markdown('<div class="metric-card-container">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(create_metric_card("Total kWh Used", f"{total_kwh:.3f}"), unsafe_allow_html=True)
        with col2:
            st.markdown(create_metric_card("Total Cost (৳)", f"{total_cost:.2f}"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        plot_pretty_line_chart(df, "cumulative_cost_bdt", "Cumulative Cost (৳)", "#4c72b0")
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Data does not have energy/cost calculation columns.")

    with st.expander(f"📋 Show Data Table for {selected_date}"):
        st.dataframe(df, use_container_width=True, height=400)

    st.markdown("### 📊 Historical Analytics")
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

    csv_bytes = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv_bytes, f"{selected_date}.csv", "text/csv")
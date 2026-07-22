#!/usr/bin/env bash
# Start Streamlit directly on the port Render expects.
exec streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0

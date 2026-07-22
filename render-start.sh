#!/usr/bin/env bash
# Start Streamlit bound to localhost and proxy via Gunicorn Flask app
streamlit run app.py --server.port 8501 --server.address 127.0.0.1 &
exec gunicorn -w 1 healthcheck:app -b 0.0.0.0:${PORT}

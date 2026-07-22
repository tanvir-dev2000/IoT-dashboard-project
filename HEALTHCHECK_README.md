Render healthcheck proxy (Option B)

Summary
- Adds a small Flask proxy `healthcheck.py` that exposes `/health` and forwards other requests to the local Streamlit server running on port 8501. Use an uptime monitor to ping `/health` so Render won't idle the service.

Dependencies
- Add these to your `requirements.txt` (pin versions if you prefer):

```
Flask==2.3.4
requests==2.31.0
gunicorn==21.2.0
```

Render configuration (no Docker)
- In the Render dashboard create a new Web Service connected to your GitHub repo.
- Set Environment: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `bash render-start.sh`

Notes
- `render-start.sh` launches Streamlit on `127.0.0.1:8501` and then starts Gunicorn serving `healthcheck.app` on `$PORT`. The public Render URL points to Gunicorn, which proxies to Streamlit.
- Optional: set environment variable `STREAMLIT_INTERNAL_URL` if Streamlit runs on a different host/port.
- After deployment, configure UptimeRobot or cron-job.org to send GET requests to `https://<your-app>.onrender.com/health` every 10 minutes.

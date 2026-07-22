from flask import Flask, Response, request
import requests
import os

# Internal Streamlit address the proxy will forward to
STREAMLIT_URL = os.environ.get("STREAMLIT_INTERNAL_URL", "http://127.0.0.1:8501")

app = Flask(__name__)


@app.route("/health")
def health():
    return "OK", 200


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy(path):
    # Build target URL
    url = f"{STREAMLIT_URL}/{path}"

    # Forward incoming request to the Streamlit internal server
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            allow_redirects=False,
            timeout=30,
        )
    except requests.RequestException:
        return "Upstream unavailable", 503

    excluded = ("content-encoding", "transfer-encoding", "connection")
    response_headers = [(name, value) for (name, value) in resp.headers.items() if name.lower() not in excluded]
    return Response(resp.content, resp.status_code, response_headers)

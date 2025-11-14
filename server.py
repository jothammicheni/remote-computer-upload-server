from flask import Flask, request, Response, render_template, stream_with_context, send_from_directory, abort
from werkzeug.utils import safe_join
import os
import io
import zipfile
import queue
from functools import wraps

app = Flask(__name__)

# --- CONFIG ---
BASE_DIR = "uploaded_folders"
os.makedirs(BASE_DIR, exist_ok=True)

# --- Simple per-machine message queue (for SSE) ---
message_queues = {}  # { machine_name: Queue() }

def send_message(machine, message):
    q = message_queues.setdefault(machine, queue.Queue())
    q.put(message)

# ========== SIMPLE BASIC AUTH (NO SESSIONS) ==========

USERNAME = "admin@1234"
PASSWORD = "password@admin"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        "Login Required", 401,
        {"WWW-Authenticate": 'Basic realm="Admin Area"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ========== SSE ENDPOINT ==========
@app.route("/events/<machine>")
@requires_auth
def sse(machine):
    def event_stream():
        q = message_queues.setdefault(machine, queue.Queue())
        while True:
            msg = q.get()
            yield f"data: {msg}\n\n"
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# ========== UPLOAD ENDPOINT ==========
@app.route("/upload", methods=["POST"])
@requires_auth
def upload():
    machine_name = request.form.get("machine", "unknown")
    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return "No file provided", 400

    send_message(machine_name, f"📡 Connected to client ({machine_name})")
    send_message(machine_name, "📦 Receiving file...")

    machine_dir = os.path.join(BASE_DIR, machine_name)
    os.makedirs(machine_dir, exist_ok=True)

    zip_bytes = io.BytesIO(uploaded_file.read())
    try:
        with zipfile.ZipFile(zip_bytes) as zf:
            zf.extractall(machine_dir)
    except zipfile.BadZipFile:
        send_message(machine_name, "❌ Bad ZIP file — upload failed")
        return "Invalid ZIP file", 400

    send_message(machine_name, f"✅ Upload complete: {uploaded_file.filename}")
    return f"Uploaded {uploaded_file.filename} to {machine_dir}"

# ========== FILE SERVING ==========
@app.route("/files/<machine>/<path:filename>")
@requires_auth
def get_file(machine, filename):
    safe_path = safe_join(BASE_DIR, machine)
    if safe_path is None:
        abort(404)

    full_path = os.path.join(safe_path, filename)
    if not os.path.exists(full_path):
        abort(404)

    return send_from_directory(safe_path, filename, as_attachment=False)

# ========== DASHBOARD ==========
@app.route("/")
@requires_auth
def index():
    machines_data = {}
    for machine in os.listdir(BASE_DIR):
        machine_path = os.path.join(BASE_DIR, machine)
        if os.path.isdir(machine_path):
            files = []
            for root, dirs, filenames in os.walk(machine_path):
                for f in filenames:
                    rel_path = os.path.relpath(os.path.join(root, f), machine_path)
                    files.append(rel_path)
            machines_data[machine] = files
    return render_template("index.html", machines=machines_data)

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    print("🚀 Server running on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)

from flask import Flask, request, render_template, Response, stream_with_context, send_from_directory, abort
from werkzeug.utils import safe_join
import os
import io
import zipfile
import queue

app = Flask(__name__)

# --- CONFIG ---
BASE_DIR = "uploaded_folders"
os.makedirs(BASE_DIR, exist_ok=True)

# --- Simple per-machine message queue (for SSE) ---
message_queues = {}  # { machine_name: Queue() }

def send_message(machine, message):
    """Send a message to a specific machine's SSE stream."""
    q = message_queues.setdefault(machine, queue.Queue())
    q.put(message)

# --- SSE endpoint ---
@app.route("/events/<machine>")
def sse(machine):
    """Server-Sent Events stream for live updates per machine."""
    def event_stream():
        q = message_queues.setdefault(machine, queue.Queue())
        while True:
            msg = q.get()  # wait for next message
            yield f"data: {msg}\n\n"
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# --- Upload endpoint ---
@app.route("/upload", methods=["POST"])
def upload():
    """Receive a zipped folder from the client and extract it."""
    machine_name = request.form.get("machine", "unknown")
    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return "No file provided", 400

    send_message(machine_name, f"📡 Connected to client ({machine_name})")
    send_message(machine_name, "📦 Receiving file...")

    # Create per-machine directory
    machine_dir = os.path.join(BASE_DIR, machine_name)
    os.makedirs(machine_dir, exist_ok=True)

    # Read zip bytes and extract safely
    zip_bytes = io.BytesIO(uploaded_file.read())
    try:
        with zipfile.ZipFile(zip_bytes) as zf:
            zf.extractall(machine_dir)
    except zipfile.BadZipFile:
        send_message(machine_name, "❌ Bad ZIP file — upload failed")
        return "Invalid ZIP file", 400

    send_message(machine_name, f"✅ Upload complete: {uploaded_file.filename}")
    return f"Uploaded {uploaded_file.filename} to {machine_dir}"

# --- File-serving endpoint ---
@app.route("/files/<machine>/<path:filename>")
def get_file(machine, filename):
    """Serve individual files for viewing or download."""
    safe_path = safe_join(BASE_DIR, machine)
    if safe_path is None:
        abort(404)

    full_path = os.path.join(safe_path, filename)
    if not os.path.exists(full_path):
        abort(404)

    # Serve safely
    return send_from_directory(safe_path, filename, as_attachment=False)

# --- Web Interface ---
@app.route("/")
def index():
    """Main dashboard showing all uploaded machines and their files."""
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

# --- Entry Point ---
if __name__ == "__main__":
    print("🚀 Server starting at http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)

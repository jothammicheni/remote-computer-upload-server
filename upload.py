import os
import requests
import socket
import zipfile
import io
import time

# --- CONFIG ---
HOME_DIR = os.path.expanduser("~")
SERVER_IP = "192.168.1.100"  # Change to your Flask server's IP
SERVER_URL = f"http://{SERVER_IP}:5000/upload"

# Identify this machine
MACHINE_NAME = socket.gethostname()

# Retry settings
MAX_RETRIES = 5          # Max attempts before skipping
RETRY_DELAY = 10         # Seconds between retries


def zip_folder(folder_path):
    """Create a ZIP archive in memory for the given folder."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                abs_file = os.path.join(root, file)
                rel_path = os.path.relpath(abs_file, folder_path)
                zf.write(abs_file, arcname=rel_path)
    memory_file.seek(0)
    return memory_file


def upload_folder(folder_path, folder_name):
    """Try uploading folder, retrying on failure."""
    zipped = zip_folder(folder_path)
    files = {'file': (f"{folder_name}.zip", zipped)}
    data = {'machine': MACHINE_NAME}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}: Uploading {folder_name}...")
            response = requests.post(SERVER_URL, files=files, data=data, timeout=30)
            if response.status_code == 200:
                print(f"✅ Upload success: {folder_name}")
                return True
            else:
                print(f"⚠️ Server error ({response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Upload failed ({attempt}/{MAX_RETRIES}): {e}")

        if attempt < MAX_RETRIES:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

    print(f"🚫 Giving up on {folder_name} after {MAX_RETRIES} attempts.")
    return False


if __name__ == "__main__":
    for item in os.listdir(HOME_DIR):
        local_item = os.path.join(HOME_DIR, item)
        if os.path.isdir(local_item) and item.lower().startswith("v"):
            upload_folder(local_item, item)

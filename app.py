import os
import time
import uuid
import zipfile
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
import qrcode

UPLOAD_FOLDER = "uploads"
QR_FOLDER = "static/qr"
MAX_SIZE = 100 * 1024 * 1024
EXPIRY_TIME = 3600

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app = Flask(__name__)
file_db = {}

def generate_code():
    return str(uuid.uuid4().int)[:6]

def cleanup():
    while True:
        now = time.time()
        for code in list(file_db.keys()):
            if now > file_db[code]["expiry"]:
                try:
                    os.remove(file_db[code]["file"])
                    os.remove(file_db[code]["qr"])
                except:
                    pass
                del file_db[code]
        time.sleep(60)

threading.Thread(target=cleanup, daemon=True).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files selected"})

    total_size = sum(len(f.read()) for f in files)
    for f in files:
        f.seek(0)

    if total_size > MAX_SIZE:
        return jsonify({"error": "Total size exceeds 100MB"})

    code = generate_code()

    if len(files) == 1:
        f = files[0]
        path = os.path.join(UPLOAD_FOLDER, f"{code}_{f.filename}")
        f.save(path)
    else:
        path = os.path.join(UPLOAD_FOLDER, f"{code}.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.writestr(f.filename, f.read())

    link = request.host_url + f"download/{code}"
    qr_path = f"{QR_FOLDER}/{code}.png"
    qrcode.make(link).save(qr_path)

    file_db[code] = {
        "file": path,
        "qr": qr_path,
        "expiry": time.time() + EXPIRY_TIME
    }

    return jsonify({
        "code": code,
        "files": len(files),
        "link": link,
        "qr": "/" + qr_path
    })

@app.route("/getfile", methods=["POST"])
def getfile():
    code = request.form.get("code")
    if code not in file_db:
        return jsonify({"error": "Invalid or expired code"})
    return jsonify({"link": request.host_url + f"download/{code}"})

@app.route("/download/<code>")
def download(code):
    if code not in file_db:
        return "Invalid or expired"

    file_path = file_db[code]["file"]
    stored = os.path.basename(file_path)

    if "_" in stored and not stored.endswith(".zip"):
        download_name = stored.split("_", 1)[1]
    else:
        download_name = stored

    return send_from_directory(
        os.path.dirname(file_path),
        stored,
        as_attachment=True,
        download_name=download_name
    )

# 🔥 REQUIRED FOR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

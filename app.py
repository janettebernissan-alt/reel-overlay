import os
import subprocess
import uuid
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "changeme")
LOGO_URL = os.environ.get("LOGO_URL", "")

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/overlay", methods=["POST"])
def overlay():
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    video_url = data.get("video_url")
    banner_text = data.get("banner_text", "")
    logo_url = data.get("logo_url", LOGO_URL)

    if not video_url:
        return jsonify({"error": "video_url is required"}), 400

    work_id = str(uuid.uuid4())
    video_path = f"/tmp/{work_id}_input.mp4"
    logo_path = f"/tmp/{work_id}_logo.png"
    text_path = f"/tmp/{work_id}_text.txt"
    output_path = f"/tmp/{work_id}_output.mp4"

    try:
        r = requests.get(video_url, timeout=60, stream=True)
        r.raise_for_status()
        with open(video_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)

        has_logo = False
        if logo_url:
            r2 = requests.get(logo_url, timeout=30)
            if r2.status_code == 200:
                with open(logo_path, "wb") as f:
                    f.write(r2.content)
                has_logo = True

        with open(text_path, "w", encoding="utf-8") as f:
            f.write(banner_text)

        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        text_filter = (
            f"drawtext=fontfile={font}:textfile={text_path}:x=10:y=h-th-30:"
            f"fontsize=32:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"
        )
        scale_filter = "scale=-2:1280"

        if has_logo:
            filter_complex = f"[0:v]{scale_filter}[v0];[v0][1:v]overlay=10:10[ov];[ov]{text_filter}"
            cmd = ["ffmpeg", "-y", "-i", video_path, "-i", logo_path,
                   "-filter_complex", filter_complex, "-codec:a", "copy", output_path]
        else:
            cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"{scale_filter},{text_filter}",
                   "-codec:a", "copy", output_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return jsonify({"error": "ffmpeg failed", "details": result.stderr[-2000:]}), 500

        return send_file(output_path, mimetype="video/mp4",
                          as_attachment=True, download_name="output.mp4")
    finally:
        for p in [video_path, logo_path, text_path, output_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

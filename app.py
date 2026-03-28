from flask import Flask, render_template, request, redirect, url_for, session, send_file, send_from_directory
import whisper
import os
from datetime import datetime
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
import nltk
import io
import json
import base64
import ssl
import mysql.connector

# ---------------- MYSQL CONNECTION ---------------- #
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Mansi@123",
    database="audio_processing_system"
)
cursor = db.cursor(dictionary=True)

# ---------------- FIX SSL ---------------- #
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except:
    pass

# ---------------- NLTK ---------------- #
nltk.download('punkt')

# ---------------- FLASK ---------------- #
app = Flask(__name__)
app.secret_key = "secretkey"

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

UPLOAD_FOLDER = "uploads"
SAVE_FOLDER = "saved_files"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SAVE_FOLDER, exist_ok=True)

# ---------------- MODEL ---------------- #
whisper_model = whisper.load_model("base")

# ---------------- LOGIN ---------------- #
USERNAME = "mansi"
PASSWORD = "1234"

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username == USERNAME and password == PASSWORD:
        session["user"] = username
        return redirect(url_for("dashboard"))
    else:
        return "Invalid Credentials"

@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("dashboard.html", user=session["user"])
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ---------------- SERVE AUDIO ---------------- #
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- FILE UPLOAD ---------------- #
@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("home"))

    file = request.files.get("audio")

    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        # 🔹 Transcription
        result = whisper_model.transcribe(filepath, fp16=False)
        transcription = result["text"]

        # 🔹 Summarization
        parser = PlaintextParser.from_string(transcription, Tokenizer("english"))
        summarizer = TextRankSummarizer()
        summary_sentences = summarizer(parser.document, 3)

        summary_text = " ".join(str(sentence) for sentence in summary_sentences)

        # 🔹 SAVE TO DATABASE
        query = "INSERT INTO results (filename, transcription, summary) VALUES (%s, %s, %s)"
        values = (file.filename, transcription, summary_text)
        cursor.execute(query, values)
        db.commit()

        return render_template("result.html",
                               transcription=transcription,
                               summary=summary_text,
                               audio_file=file.filename)

    return "No file uploaded"

# ---------------- HISTORY ---------------- #
@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("home"))

    cursor.execute("SELECT * FROM results ORDER BY id DESC")
    data = cursor.fetchall()

    return render_template("history.html", records=data)

# ---------------- LIVE RECORDING ---------------- #
@app.route("/live_upload", methods=["POST"])
def live_upload():
    if "user" not in session:
        return redirect(url_for("home"))

    audio_data = request.form["audio_data"]
    header, encoded = audio_data.split(",", 1)
    audio_bytes = base64.b64decode(encoded)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(UPLOAD_FOLDER, f"live_{now}.webm")

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    result = whisper_model.transcribe(filepath, fp16=False)
    transcription = result["text"]

    parser = PlaintextParser.from_string(transcription, Tokenizer("english"))
    summarizer = TextRankSummarizer()
    summary_text = " ".join(str(s) for s in summarizer(parser.document, 3))

    query = "INSERT INTO results (filename, transcription, summary) VALUES (%s, %s, %s)"
    values = (os.path.basename(filepath), transcription, summary_text)
    cursor.execute(query, values)
    db.commit()

    return render_template("result.html",
                           transcription=transcription,
                           summary=summary_text,
                           audio_file=os.path.basename(filepath))

# ---------------- DOWNLOAD TXT ---------------- #
@app.route("/download", methods=["POST"])
def download():
    transcription = request.form["transcription"]
    summary = request.form["summary"]

    content = f"TRANSCRIPTION:\n\n{transcription}\n\nSUMMARY:\n\n{summary}"

    file = io.BytesIO()
    file.write(content.encode("utf-8"))
    file.seek(0)

    return send_file(file,
                     as_attachment=True,
                     download_name="result.txt",
                     mimetype="text/plain")

# ---------------- DOWNLOAD JSON ---------------- #
@app.route("/download_json", methods=["POST"])
def download_json():
    data = {
        "transcription": request.form["transcription"],
        "summary": request.form["summary"]
    }

    file = io.BytesIO()
    file.write(json.dumps(data, indent=4).encode("utf-8"))
    file.seek(0)

    return send_file(file,
                     as_attachment=True,
                     download_name="result.json",
                     mimetype="application/json")

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    app.run(debug=True)

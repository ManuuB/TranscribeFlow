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

#cursor = db.cursor()
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
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def do_login():
    username = request.form["username"]
    password = request.form["password"]

    if username == USERNAME and password == PASSWORD:
        session["user"] = username
        return redirect(url_for("dashboard"))
    else:
        return "Invalid Credentials"

@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template("dashboard.html")
    return redirect(url_for("login"))
    from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "secret123"

# Home Page (Login)
@app.route('/')
def home():
    return render_template("login.html")

# Login Route
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    # Validation
    if not username or not password:
        return "Please fill all fields!"

    if len(username) < 3 or len(password) < 3:
        return "Username & Password must be at least 3 characters!"

    # Allow any user
    session['user'] = username
    return redirect(url_for('dashboard'))

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template("dashboard.html", user=session['user'])
    return redirect(url_for('home'))

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

# ---------------- SERVE AUDIO ---------------- #
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- FILE UPLOAD ---------------- #
@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    file = request.files["audio"]

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

        summary_text = ""
        for sentence in summary_sentences:
            summary_text += str(sentence) + " "

        # 🔹 SAVE TO DATABASE ✅
        filename = file.filename

        query = "INSERT INTO results (filename, transcription, summary) VALUES (%s, %s, %s)"
        values = (filename, transcription, summary_text)

        cursor.execute(query, values)
        db.commit()

        # 🔹 SAVE TXT FILE (optional)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(SAVE_FOLDER, f"result_{now}.txt")

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("TRANSCRIPTION:\n")
            f.write(transcription + "\n\n")
            f.write("SUMMARY:\n")
            f.write(summary_text)

        return render_template("result.html",
                               transcription=transcription,
                               summary=summary_text,
                               audio_file=filename)

    return "No file uploaded"

@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute("SELECT * FROM results ORDER BY id DESC")
    data = cursor.fetchall()

    return render_template("history.html", records=data)

# ---------------- LIVE RECORDING ---------------- #
@app.route("/live_upload", methods=["POST"])
def live_upload():
    if "user" not in session:
        return redirect(url_for("login"))

    audio_data = request.form["audio_data"]

    header, encoded = audio_data.split(",", 1)
    audio_bytes = base64.b64decode(encoded)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(UPLOAD_FOLDER, f"live_{now}.webm")

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    # 🔹 Transcription
    result = whisper_model.transcribe(filepath, fp16=False)
    transcription = result["text"]

    # 🔹 Summarization
    parser = PlaintextParser.from_string(transcription, Tokenizer("english"))
    summarizer = TextRankSummarizer()
    summary_sentences = summarizer(parser.document, 3)

    summary_text = ""
    for sentence in summary_sentences:
        summary_text += str(sentence) + " "

    # 🔹 SAVE TO DATABASE ✅
    filename = os.path.basename(filepath)

    query = "INSERT INTO results (filename, transcription, summary) VALUES (%s, %s, %s)"
    values = (filename, transcription, summary_text)

    cursor.execute(query, values)
    db.commit()

    return render_template("result.html",
                           transcription=transcription,
                           summary=summary_text,
                           audio_file=filename)

# ---------------- DOWNLOAD TXT ---------------- #
@app.route("/download", methods=["POST"])
def download():
    transcription = request.form["transcription"]
    summary = request.form["summary"]

    content = "TRANSCRIPTION:\n\n" + transcription + "\n\nSUMMARY:\n\n" + summary

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
    transcription = request.form["transcription"]
    summary = request.form["summary"]

    data = {
        "transcription": transcription,
        "summary": summary
    }

    json_data = json.dumps(data, indent=4)

    file = io.BytesIO()
    file.write(json_data.encode("utf-8"))
    file.seek(0)

    return send_file(file,
                     as_attachment=True,
                     download_name="result.json",
                     mimetype="application/json")

# ---------------- LOGOUT ---------------- #
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    app.run(debug=True)

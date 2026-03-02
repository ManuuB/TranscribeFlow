from flask import Flask, render_template, request, redirect, url_for, session
import whisper
#from transformers import pipeline
import os
from datetime import datetime
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
import nltk
from flask import send_file
import io

#nltk.download('punkt')

import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
except:
    pass

import nltk
nltk.download('punkt')
nltk.download('punkt_tab')

app = Flask(__name__)
app.secret_key = "secretkey"

UPLOAD_FOLDER = "uploads"
SAVE_FOLDER = "saved_files"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Load models once
whisper_model = whisper.load_model("base")
# summarizer = pipeline("summarization", model="t5-small")

# Predefined Login
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

@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    file = request.files["audio"]
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        # Transcribe
        result = whisper_model.transcribe(filepath)
        transcription = result["text"]

        # Summarize
       # summary = summarizer(transcription, max_length=100, min_length=30, do_sample=False)
       # summary_text = summary[0]["summary_text"]
       
        parser = PlaintextParser.from_string(transcription, Tokenizer("english"))
        summarizer = TextRankSummarizer()

        summary_sentences = summarizer(parser.document, 3)  # 3 sentences summary

        summary_text = ""
        for sentence in summary_sentences:
            summary_text += str(sentence) + " "

        # Save file
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(SAVE_FOLDER, f"result_{now}.txt")

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("TRANSCRIPTION:\n")
            f.write(transcription + "\n\n")
            f.write("SUMMARY:\n")
            f.write(summary_text)

        return render_template("result.html", 
                       transcription=transcription, 
                       summary=summary_text)

    return "No file uploaded"
import base64

@app.route("/live_upload", methods=["POST"])
def live_upload():
    if "user" not in session:
        return redirect(url_for("login"))

    audio_data = request.form["audio_data"]

    # Remove header
    header, encoded = audio_data.split(",", 1)
    audio_bytes = base64.b64decode(encoded)

    # Save file
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(UPLOAD_FOLDER, f"live_{now}.wav")

    with open(filepath, "wb") as f:
        f.write(audio_bytes)

    # Transcribe using Whisper
    result = whisper_model.transcribe(filepath)
    transcription = result["text"]

    # Summarize using TextRank
    parser = PlaintextParser.from_string(transcription, Tokenizer("english"))
    summarizer = TextRankSummarizer()

    summary_sentences = summarizer(parser.document, 3)

    summary_text = ""
    for sentence in summary_sentences:
        summary_text += str(sentence) + " "

    return render_template("result.html",
                           transcription=transcription,
                           summary=summary_text)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/download", methods=["POST"])
def download():
    transcription = request.form["transcription"]
    summary = request.form["summary"]

    content = "TRANSCRIPTION:\n\n"
    content += transcription + "\n\n"
    content += "SUMMARY:\n\n"
    content += summary

    file = io.BytesIO()
    file.write(content.encode("utf-8"))
    file.seek(0)

    return send_file(file,
                     as_attachment=True,
                     download_name="result.txt",
                     mimetype="text/plain")

if __name__ == "__main__":
    app.run(debug=True)
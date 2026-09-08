import os
import time
import wave
import io
import requests
import speech_recognition as sr
from flask import Flask, request, send_file
from gtts import gTTS

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

session = requests.Session()
recognizer = sr.Recognizer()

def generate_clean_audio(text):
    try:
        clean_text = text.replace('"', '').replace("'", "").replace("`", "").replace("*", "").replace("#", "").replace("_", "").strip()
        if not clean_text:
            clean_text = "Halo, asisten pintar siap membantu."

        print(f"[MEMPROSES SUARA TTS]: {clean_text}")
        tts = gTTS(text=clean_text, lang='id', slow=False)
        tts.save("temp.mp3")

        if os.path.exists("response.wav"):
            os.remove("response.wav")

        os.system('ffmpeg -y -v quiet -i temp.mp3 -acodec pcm_u8 -ar 11025 -ac 1 response.wav')

        if os.path.exists("response.wav") and os.path.getsize("response.wav") > 1000:
            print(f"[AUDIO READY]: Ukuran file {os.path.getsize('response.wav')} bytes")
            return True
        else:
            print("[ERROR AUDIO]: File response.wav kosong atau gagal dibuat!")
            return False
    except Exception as e:
        print(f"[ERROR TTS/FFMPEG]: {e}")
        return False

def call_groq_ai(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [
            {
                "role": "system",
                "content": "Kamu asisten pintar bernama Gemini/ESP-Assistant. Jawab setiap pertanyaan dalam 1 atau 2 kalimat singkat, jelas, santai, dan berbahasa Indonesia tanpa format markdown atau simbol aneh."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.6,
        "max_tokens": 150
    }

    try:
        res = session.post(GROQ_URL, json=payload, headers=headers, timeout=15)
        data = res.json()
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"[GROQ STATUS ERROR]: {data}")
            return "Maaf, terjadi kendala saat memproses jawaban."
    except Exception as e:
        print(f"[ERROR REQUEST GROQ]: {e}")
        return "Gagal terhubung ke server kecerdasan buatan."

def get_audio_url():
    host = request.host
    scheme = "https" if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https' else "http"
    return f"{scheme}://{host}/get_response_audio"

@app.route('/ask_text', methods=['GET'])
def ask_text():
    prompt = request.args.get('q', 'Ceritakan satu lelucon lucu bahasa Indonesia')
    print(f"\n[USER PERTANYAAN]: {prompt}")

    ai_reply = call_groq_ai(prompt)
    print(f"[AI MENJAWAB]:\n{ai_reply}\n")

    generate_clean_audio(ai_reply)
    return get_audio_url()

@app.route('/process_audio', methods=['POST'])
def process_audio():
    pcm_data = request.data
    if not pcm_data:
        return "No data", 400

    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(pcm_data)
    wav_io.seek(0)

    user_text = ""
    try:
        with sr.AudioFile(wav_io) as source:
            audio_content = recognizer.record(source)
            user_text = recognizer.recognize_google(audio_content, language="id-ID").strip().lower()
            print(f"\n[SUARA TERDETEKSI]: {user_text}")
    except sr.UnknownValueError:
        print("Suara tidak terdeteksi.")
        user_text = ""
    except Exception as e:
        print(f"Error STT: {e}")
        return "Error STT", 500

    if not user_text:
        generate_clean_audio("Suara tidak terdengar jelas, silakan ulangi.")
        return get_audio_url()

    if "nyalakan lampu" in user_text:
        generate_clean_audio("Siap, lampu dinyalakan.")
        return get_audio_url()
    elif "matikan lampu" in user_text:
        generate_clean_audio("Baik, lampu sudah dimatikan.")
        return get_audio_url()

    ai_reply = call_groq_ai(user_text)
    print(f"[AI MENJAWAB]:\n{ai_reply}\n")

    generate_clean_audio(ai_reply)
    return get_audio_url()

@app.route('/get_response_audio', methods=['GET'])
def get_response_audio():
    if os.path.exists("response.wav"):
        response = send_file("response.wav", mimetype="audio/wav")
        response.headers["Connection"] = "close"
        response.headers["Cache-Control"] = "no-cache"
        return response
    return "File tidak ditemukan", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

import os
import queue
import sounddevice as sd
import vosk
import sys
import json
import subprocess
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

# ========== CONFIGURATION ==========
# Set your Gemini API key here or via environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
# Path to your Vosk model directory
VOSK_MODEL_PATH = 'vosk-model-small-en-us-0.15'  # Change if needed

# ========== INITIALIZE VOSK ==========
if not os.path.exists(VOSK_MODEL_PATH):
    print(f"Vosk model not found at '{VOSK_MODEL_PATH}'. Please download and extract it.")
    print("Download from: https://alphacephei.com/vosk/models")
    sys.exit(1)

model = vosk.Model(VOSK_MODEL_PATH)
q = queue.Queue()

# ========== AUDIO CALLBACK ==========
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

# ========== GEMINI PRO API SETUP ==========
if GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY_HERE' or not GEMINI_API_KEY:
    print("Please set your Gemini API key in the script or as the GEMINI_API_KEY environment variable.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def get_linux_command_from_gemini(user_text):
    prompt = (
        "You are a helpful Linux assistant. "
        "Given the following user request, reply with a single-line, safe Linux shell command that fulfills the intent. "
        "Do not explain, just output the command. If the request is unsafe or ambiguous, reply with 'echo Unsafe or unclear command.'\n"
        f"User request: {user_text}\nCommand: "
    )
    model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
    response = model.generate_content(prompt)
    command = response.text.strip().split('\n')[0]
    return command

# ========== MAIN LOOP ==========
def main():
    print("\n🎤 Voice-Controlled Linux Assistant\nPress Ctrl+C to exit. Speak your command after the beep.\n")
    while True:
        try:
            input("Press Enter and speak...")
            print("(Listening...)")
            rec = vosk.KaldiRecognizer(model, 16000)
            with sd.RawInputStream(samplerate=16000, blocksize = 8000, dtype='int16', channels=1, callback=callback):
                while True:
                    data = q.get()
                    if rec.AcceptWaveform(data):
                        result = rec.Result()
                        break
            result_json = json.loads(result)
            user_text = result_json.get('text', '').strip()
            if not user_text:
                print("Didn't catch that. Please try again.\n")
                continue
            print(f"You said: {user_text}")

            # Get command from Gemini
            print("Contacting Gemini...")
            command = get_linux_command_from_gemini(user_text)
            print(f"\nGemini suggests: {command}")
            confirm = input("Do you want to run this command? (yes/no): ").strip().lower()
            if confirm == 'yes':
                print(f"\nRunning: {command}\n---")
                subprocess.run(command, shell=True)
                print("---\nDone.\n")
            else:
                print("Command not run.\n")
        except KeyboardInterrupt:
            print("\nExiting. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main() 
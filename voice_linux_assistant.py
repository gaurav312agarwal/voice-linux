import os
import queue
import sounddevice as sd
import vosk
import sys
import json
import subprocess
import google.generativeai as genai
import numpy as np
import time
from dotenv import load_dotenv
load_dotenv()

# ========== CONFIGURATION ==========
# Set your Gemini API key here or via environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
# Path to your Vosk model directory
VOSK_MODEL_PATH = 'vosk-model-small-en-us-0.15'  # Change if needed

# Audio settings for better recognition
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 8000
DTYPE = 'int16'

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

# ========== NOISE REDUCTION ==========
def reduce_noise(audio_data):
    """Simple noise reduction by removing very quiet parts"""
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    # Remove very quiet parts (likely background noise)
    threshold = np.std(audio_array) * 0.1
    audio_array = audio_array[np.abs(audio_array) > threshold]
    return audio_array.tobytes()

# ========== IMPROVED LISTENING FUNCTION ==========
def listen_for_speech():
    """Improved listening with better feedback and noise handling"""
    print("🎤 Listening... (speak clearly)")
    
    # Initialize recognizer
    rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)  # Enable word timing
    
    # Start audio stream
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        dtype=DTYPE,
        channels=CHANNELS,
        callback=callback
    ):
        start_time = time.time()
        silence_duration = 0
        last_speech_time = time.time()
        
        while True:
            try:
                data = q.get(timeout=1)  # 1 second timeout
                
                # Process audio
                if rec.AcceptWaveform(data):
                    result = rec.Result()
                    result_json = json.loads(result)
                    text = result_json.get('text', '').strip()
                    
                    if text:
                        print(f"✅ Heard: {text}")
                        return text
                    else:
                        print("🔇 No speech detected, continuing...")
                        continue
                
                # Check for partial results
                partial = rec.PartialResult()
                partial_json = json.loads(partial)
                partial_text = partial_json.get('partial', '').strip()
                
                if partial_text:
                    print(f"🎯 Processing: {partial_text}", end='\r')
                    last_speech_time = time.time()
                    silence_duration = 0
                else:
                    silence_duration = time.time() - last_speech_time
                    if silence_duration > 2:  # 2 seconds of silence
                        print("⏸️  Pausing... (speak to continue)")
                        silence_duration = 0
                
                # Timeout after 10 seconds
                if time.time() - start_time > 10:
                    print("\n⏰ Timeout - no speech detected")
                    return ""
                    
            except queue.Empty:
                print("⏸️  Waiting for speech...")
                continue

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
    print("\n🎤 VoiceLinux - Enhanced Voice-Controlled Linux Assistant")
    print("=" * 50)
    print("💡 Tips for better recognition:")
    print("   • Speak clearly and at normal volume")
    print("   • Reduce background noise")
    print("   • Wait for the listening prompt")
    print("   • Say 'exit' to quit")
    print("=" * 50)
    print("Press Ctrl+C to exit.\n")
    
    while True:
        try:
            input("Press Enter to start listening...")
            print("\n" + "="*30)
            
            # Listen for speech
            user_text = listen_for_speech()
            
            if not user_text:
                print("❌ No speech detected. Please try again.\n")
                continue
            
            # Check for exit command
            if user_text.lower() in ['exit', 'quit', 'stop', 'bye']:
                print("👋 Goodbye!")
                break
            
            print(f"\n🎯 You said: '{user_text}'")
            
            # Get command from Gemini
            print("🤖 Contacting Gemini...")
            command = get_linux_command_from_gemini(user_text)
            print(f"\n💻 Gemini suggests: {command}")
            
            confirm = input("✅ Run this command? (yes/no/edit): ").strip().lower()
            
            if confirm == 'yes':
                print(f"\n🚀 Running: {command}")
                print("-" * 50)
                subprocess.run(command, shell=True)
                print("-" * 50)
                print("✅ Done.\n")
            elif confirm == 'edit':
                new_command = input("📝 Enter corrected command: ").strip()
                if new_command:
                    print(f"\n🚀 Running: {new_command}")
                    print("-" * 50)
                    subprocess.run(new_command, shell=True)
                    print("-" * 50)
                    print("✅ Done.\n")
            else:
                print("❌ Command not run.\n")
                
        except KeyboardInterrupt:
            print("\n👋 Exiting. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main() 
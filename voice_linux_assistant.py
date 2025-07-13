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

# ========== ERROR RESOLUTION ==========
def resolve_error_with_api(original_task, error_message, command_that_failed):
    """Use API to generate a command to fix the error"""
    prompt = f"""
    Original task: "{original_task}"
    Command that failed: "{command_that_failed}"
    Error message: "{error_message}"
    
    Generate a single Linux command to fix this error and continue with the original task.
    The command should:
    1. Address the specific error shown
    2. Help complete the original task
    3. Be safe and appropriate
    
    Respond with only the command, no explanations.
    """
    
    try:
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        response = model.generate_content(prompt)
        fix_command = response.text.strip().split('\n')[0]
        return fix_command
    except Exception as e:
        print(f"❌ Error getting fix command: {e}")
        return None

def check_task_completion(original_task, command_output):
    """Check if the original task was completed successfully"""
    prompt = f"""
    Original task: "{original_task}"
    Command output: "{command_output}"
    
    Determine if the original task was completed successfully.
    Consider:
    1. Was the original goal achieved?
    2. Are there any remaining errors?
    3. Is the task fully resolved?
    
    Respond with only: "COMPLETED" or "INCOMPLETE"
    """
    
    try:
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        return result == "COMPLETED"
    except:
        return False

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

# ========== AUTOMATIC ERROR RESOLUTION ==========
def execute_with_error_resolution(original_task):
    """Execute command and automatically resolve errors until task is completed"""
    print(f"\n🎯 Original Task: {original_task}")
    print("🔄 I'll automatically fix any errors until the task is completed!")
    
    max_resolution_attempts = 10
    attempt_count = 0
    
    while attempt_count < max_resolution_attempts:
        attempt_count += 1
        print(f"\n🔄 Attempt {attempt_count}/{max_resolution_attempts}")
        print("-" * 40)
        
        # Get initial command or fix command
        if attempt_count == 1:
            command = get_linux_command_from_gemini(original_task)
            print(f"💻 Initial command: {command}")
        else:
            print("🔧 Generating fix command...")
            command = resolve_error_with_api(original_task, last_error, last_command)
            if not command:
                print("❌ Could not generate fix command")
                break
            print(f"🔧 Fix command: {command}")
        
        # Ask for confirmation
        confirm = input("✅ Run this command? (yes/no/edit): ").strip().lower()
        
        if confirm == 'edit':
            command = input("📝 Enter corrected command: ").strip()
            if not command:
                print("❌ No command entered, skipping...")
                continue
        
        if confirm in ['yes', 'edit']:
            try:
                print(f"\n🚀 Executing: {command}")
                print("-" * 50)
                
                # Execute command and capture output
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                
                print("📤 Output:")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print("❌ Errors:")
                    print(result.stderr)
                
                print("-" * 50)
                
                # Check if task is completed
                output_text = result.stdout + result.stderr
                if check_task_completion(original_task, output_text):
                    print("🎉 SUCCESS! Original task completed successfully!")
                    return True
                
                # If there are errors, prepare for next iteration
                if result.returncode != 0 or result.stderr:
                    print("⚠️  Errors detected. Preparing to fix...")
                    last_error = result.stderr if result.stderr else "Command failed with return code " + str(result.returncode)
                    last_command = command
                    continue
                else:
                    print("✅ Command executed successfully, but task may not be complete.")
                    # Ask user if they're satisfied
                    user_satisfied = input("✅ Are you satisfied with the result? (yes/no): ").strip().lower()
                    if user_satisfied == 'yes':
                        print("🎉 Task completed to user's satisfaction!")
                        return True
                    else:
                        last_error = "User not satisfied with result"
                        last_command = command
                        continue
                        
            except Exception as e:
                print(f"❌ Error executing command: {e}")
                last_error = str(e)
                last_command = command
                continue
        else:
            print("❌ Command not executed.")
            break
    
    print(f"\n⚠️  Reached maximum resolution attempts ({max_resolution_attempts}).")
    print("Task may need manual intervention.")
    return False

# ========== MAIN LOOP ==========
def main():
    print("\n🎤 VoiceLinux - Automatic Error Resolver")
    print("=" * 50)
    print("💡 This assistant will automatically fix errors until your task is completed!")
    print("💡 Input options:")
    print("   • Voice: Speak your command")
    print("   • Text: Type your command")
    print("💡 Tips for better recognition:")
    print("   • Speak clearly and at normal volume")
    print("   • Reduce background noise")
    print("   • Wait for the listening prompt")
    print("   • Say 'exit' to quit")
    print("=" * 50)
    print("Press Ctrl+C to exit.\n")
    
    while True:
        try:
            # Ask for input method
            print("Choose input method:")
            print("1. 🎤 Voice (speak your command)")
            print("2. ⌨️  Text (type your command)")
            print("3. 🚪 Exit")
            
            choice = input("\nEnter choice (1/2/3): ").strip()
            
            if choice == "3":
                print("👋 Goodbye!")
                break
            elif choice == "2":
                # Text input
                print("\n" + "="*30)
                print("⌨️  Text Input Mode")
                print("="*30)
                user_text = input("Enter your Linux command request: ").strip()
                
                if not user_text:
                    print("❌ No text entered. Please try again.\n")
                    continue
                
                # Check for exit command
                if user_text.lower() in ['exit', 'quit', 'stop', 'bye']:
                    print("👋 Goodbye!")
                    break
                
                print(f"\n🎯 You typed: '{user_text}'")
                
                # Execute with automatic error resolution
                success = execute_with_error_resolution(user_text)
                
                if success:
                    print("\n🎉 Task completed successfully!")
                else:
                    print("\n⚠️  Task may need manual intervention.")
                
                print("\n" + "="*50)
                print("Ready for next task...")
                
            elif choice == "1":
                # Voice input
                print("\n" + "="*30)
                print("🎤 Voice Input Mode")
                print("="*30)
                input("Press Enter to start listening...")
                
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
                
                # Execute with automatic error resolution
                success = execute_with_error_resolution(user_text)
                
                if success:
                    print("\n🎉 Task completed successfully!")
                else:
                    print("\n⚠️  Task may need manual intervention.")
                
                print("\n" + "="*50)
                print("Ready for next task...")
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.\n")
                continue
                
        except KeyboardInterrupt:
            print("\n👋 Exiting. Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")

if __name__ == "__main__":
    main() 
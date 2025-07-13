# VoiceLinux - Voice-Controlled Linux Assistant

A Python-based voice assistant that converts spoken commands into Linux shell commands using speech recognition and AI-powered command generation.

## Features

- **Voice Recognition**: Uses Vosk for real-time speech-to-text conversion
- **AI-Powered Commands**: Leverages Google's Gemini AI to intelligently convert natural language to Linux commands
- **Safety First**: Requires user confirmation before executing any command
- **Real-time Processing**: Streams audio for immediate response

## Requirements

- Python 3.7+
- Vosk speech recognition model
- Google Gemini API key
- Microphone access

## Installation

1. Install dependencies:
```bash
pip install sounddevice vosk google-generativeai python-dotenv
```

2. Download Vosk model:
   - Download from: https://alphacephei.com/vosk/models
   - Extract to project directory as `vosk-model-small-en-us-0.15`

3. Set up environment:
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

## Usage

Run the assistant:
```bash
python voice_linux_assistant.py
```

Speak your Linux command naturally, and the AI will suggest the appropriate shell command for your request.

## Safety

- All commands require user confirmation before execution
- The AI is programmed to reject unsafe or ambiguous commands
- Commands are displayed before execution for review

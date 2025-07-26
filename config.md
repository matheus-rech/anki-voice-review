# Voice Review - Complete Implementation Configuration

## 🎯 Overview
This add-on provides **complete automatic voice control injection** into all your Anki cards. No manual template editing required!

## 📋 Prerequisites

### 1. AnkiConnect Add-on
**REQUIRED**: Install AnkiConnect (Code: **2055492159**)
- Go to Tools → Add-ons → Get Add-ons
- Enter code: `2055492159`
- Restart Anki

### 2. ElevenLabs API Key
**REQUIRED**: Set your ElevenLabs API key as an environment variable:

**macOS/Linux:**
```bash
export ELEVENLABS_API_KEY="your_api_key_here"
```

**Windows:**
```cmd
set ELEVENLABS_API_KEY=your_api_key_here
```

**Permanent Setup (recommended):**
Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)

## 🚀 How It Works

### Automatic Injection
- Voice controls are **automatically injected** into ALL cards
- No manual template editing required
- Works with any card type or layout
- Appears as a floating panel on every card

### Voice Commands
**Navigation:**
- "show answer" - Reveal the answer
- "next card" - Move to next card

**Rating (Natural Language):**
- "I forgot" / "again" - Rate as Again (1)
- "hard" / "difficult" - Rate as Hard (2)
- "got it" / "correct" - Rate as Good (3)
- "easy" / "perfect" - Rate as Easy (4)

**Audio:**
- "read card" - Text-to-speech of card content
- "repeat" - Read card again
- "help" - Show available commands

### Keyboard Shortcuts
- **Ctrl+V** - Start/stop voice session
- **Ctrl+R** - Read current card

## 🔧 Configuration Options

### Voice Settings
- **voice_id**: ElevenLabs voice ID (default: cgSgspJ2msm6clMCkdW9)
- **auto_injection**: Automatic injection enabled (default: true)
- **voice_recognition_language**: Speech recognition language (default: en-US)

### UI Settings
- **panel_position**: Voice panel position (default: bottom-right)
- **show_session_stats**: Show session statistics (default: true)
- **voice_feedback**: Enable voice feedback (default: true)
- **auto_read_cards**: Auto-read cards on display (default: false)
- **show_keyboard_shortcuts**: Display shortcuts in help (default: true)

### Technical Settings
- **ankiconnect_url**: AnkiConnect API URL (default: http://localhost:8765)
- **elevenlabs_base_url**: ElevenLabs API base URL
- **speech_recognition_continuous**: Continuous speech recognition (default: true)
- **tts_text_limit**: Text-to-speech character limit (default: 500)

### Natural Language Mappings
Extensive natural language understanding for card ratings:
- **again**: "forgot", "missed", "no", "wrong", etc.
- **hard**: "difficult", "struggled", "challenging", etc.  
- **good**: "correct", "yes", "got it", "right", etc.
- **easy**: "perfect", "instant", "obvious", "simple", etc.

## 📱 Usage

1. **Study normally** - Open any deck and start reviewing
2. **Voice panel appears** automatically on every card
3. **Click "Start Voice"** to activate voice controls
4. **Use voice commands** naturally while studying
5. **Click "Stop Voice"** when finished

## 🎉 Benefits

- **Zero setup per card** - Works with ALL card types automatically
- **Professional voice synthesis** - High-quality ElevenLabs TTS
- **Natural language understanding** - Speak naturally, no rigid commands
- **Session statistics** - Track your study progress
- **Keyboard shortcuts** - Quick access without mouse
- **Hands-free operation** - Perfect for accessibility or multitasking

## 🔧 Troubleshooting

### Voice controls don't appear
- Ensure AnkiConnect is installed (code: 2055492159)
- Restart Anki after installing AnkiConnect
- Check that add-on is enabled in Tools → Add-ons

### "API key not configured" error
- Set ELEVENLABS_API_KEY environment variable
- Restart Anki after setting the environment variable
- Verify the API key is valid in your ElevenLabs account

### Speech recognition not working
- Allow microphone permissions in your browser
- Try refreshing the card (press 'R' or navigate away and back)
- Check that your browser supports Web Speech API (Chrome/Edge recommended)

### AnkiConnect connection failed
- Verify AnkiConnect is installed and enabled
- Check that Anki is running
- Ensure no firewall is blocking localhost:8765

## 🚀 Technical Architecture

- **Python Add-on**: Automatic injection system using Anki hooks
- **AnkiConnect**: Direct Anki integration via REST API
- **ElevenLabs API**: Professional voice synthesis
- **Web Speech API**: Browser-based speech recognition
- **No MCP complexity**: Simple, direct API integration

## 📞 Support

- **Status Check**: Tools → Voice Review → Voice Controls Status
- **Configuration**: Tools → Voice Review → Configuration  
- **Help**: Tools → Voice Review → Help
- **Logs**: Check Anki's debug console for detailed information

Happy hands-free studying! 🎤✨ 
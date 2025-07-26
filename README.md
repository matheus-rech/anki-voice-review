# 🎤 Voice Review with AI Assistant - Anki Add-on

**Transform your Anki flashcard review with hands-free voice commands and ElevenLabs conversational AI!**

Perfect for studying during commutes, walking, or any hands-free scenario.

## ✨ Features

### 🚀 **One-Click Voice Sessions**
- **Automatic Server Startup**: Just click "Start Voice" and everything starts automatically
- **Smart Connection**: Checks server status and starts if needed
- **Visual Feedback**: Clear status indicators and progress messages

### 🎯 **Natural Language Commands**
- **Card Navigation**: "next card", "show answer", "continue"
- **Smart Rating**: "I forgot" (1), "pretty hard" (2), "got it" (3), "too easy" (4)
- **Session Control**: "start", "stop", "pause session"

### 🤖 **ElevenLabs AI Integration**
- **Conversational Agent**: Your personal "Anki Study Buddy"
- **Natural Conversation**: Speak naturally, no rigid commands
- **Smart Hints**: AI-powered study assistance
- **Mobile Support**: Works with ElevenLabs mobile app

### 🎨 **Beautiful UI**
- **Embedded Controls**: Voice buttons directly in flashcards
- **Floating Panel**: Modern gradient design with animations
- **Status Indicators**: Real-time connection and session status
- **Mobile Responsive**: Works perfectly on phones and tablets

## 🚀 Installation

### Method 1: AnkiWeb (Recommended)
1. Open Anki
2. Go to **Tools → Add-ons → Get Add-ons**
3. Enter add-on code: `[ANKIWEB_CODE_HERE]`
4. Restart Anki

### Method 2: Manual Installation
1. Download the latest `.ankiaddon` file from releases
2. Open Anki
3. Go to **Tools → Add-ons → Install from file**
4. Select the downloaded file
5. Restart Anki

## ⚙️ Setup

### 1. **ElevenLabs Configuration**
- Sign up for [ElevenLabs](https://elevenlabs.io)
- Create a conversational agent or use the default "Anki Study Buddy"
- Copy your agent ID to add-on configuration

### 2. **Voice Controls Setup**
Add voice controls to your card templates:

#### **HTML** (Add to Front or Back Template):
```html
<!-- Voice Control Buttons -->
<div id="voice-controls" class="voice-control-panel">
    <!-- Full HTML from templates/anki_card_voice_buttons.py -->
</div>
```

#### **CSS** (Add to Styling):
```css
/* Voice Control Styling */
.voice-control-panel {
    /* Full CSS from templates/anki_card_voice_buttons.py */
}
```

#### **JavaScript** (Add to Back Template):
```javascript
<script>
    /* Full JavaScript from templates/anki_card_voice_buttons.py */
</script>
```

### 3. **Configuration**
- Go to **Tools → Voice Review → Configuration**
- Adjust settings as needed
- Your ElevenLabs agent ID
- Voice recognition language
- UI preferences

## 🎯 Usage

### **Quick Start**
1. Open any flashcard with voice controls
2. Click **"Start Voice"** button
3. System automatically starts MCP server
4. Begin voice session immediately
5. Say **"next card"** to begin studying

### **Voice Commands**

#### **Navigation**
- *"next card"* / *"continue"* → Next flashcard
- *"show answer"* / *"reveal"* → Show answer
- *"start"* / *"begin"* → Start voice session

#### **Natural Rating**
- *"I forgot"* / *"again"* / *"no idea"* → Again (1)
- *"pretty hard"* / *"struggled"* → Hard (2)  
- *"got it"* / *"correct"* / *"yes"* → Good (3)
- *"too easy"* / *"obvious"* / *"simple"* → Easy (4)

#### **Session Control**
- *"stop"* / *"end session"* → Stop voice session
- *"pause"* / *"take a break"* → Pause session

### **Keyboard Shortcuts**
- **Ctrl+V**: Toggle voice session
- **Ctrl+N**: Next card (during session)
- **Ctrl+S**: Show answer (during session)
- **Double-click panel**: Minimize/maximize

## 🛠️ Technical Architecture

### **Components**
- **MCP Server**: Model Context Protocol interface for AI assistants
- **Voice Recognition**: Browser-based speech recognition (Chrome/Edge recommended)
- **ElevenLabs Integration**: Conversational AI agent for natural interaction
- **Anki Integration**: Direct database access for card management

### **File Structure**
```
voice_review_addon/
├── __init__.py              # Main entry point
├── manifest.json            # Add-on metadata
├── config.json             # User configuration
├── config.md               # Configuration documentation
├── core/
│   └── mcp_server.py       # MCP server implementation
├── ui/
│   ├── menu_integration.py # Tools menu integration
│   └── voice_controls.py   # Voice control widgets
├── utils/
│   └── config_manager.py   # Configuration management
├── web/
│   └── voice_card_controls.js # JavaScript for cards
└── templates/
    └── anki_card_voice_buttons.py # Complete card integration
```

## 🔧 Advanced Configuration

### **Natural Language Mappings**
Customize voice command recognition in `config.json`:

```json
{
    "natural_language_mappings": {
        "again": ["forgot", "missed", "no idea", "blank"],
        "hard": ["difficult", "struggled", "challenging"],
        "good": ["correct", "got it", "remembered"],
        "easy": ["obvious", "simple", "too easy"]
    }
}
```

### **UI Customization**
```json
{
    "ui_settings": {
        "show_status_indicator": true,
        "show_session_stats": true,
        "minimizable_panel": true,
        "panel_position": "bottom-right"
    }
}
```

## 📱 Mobile Support

Works perfectly with the **ElevenLabs mobile app**:
1. Install ElevenLabs app on your phone
2. Connect to the same agent
3. Start voice session on Anki desktop
4. Use phone for voice commands during commute
5. Real-time sync with desktop Anki

## 🐛 Troubleshooting

### **Common Issues**

**"MCP Server not connected"**
- Click "Start Voice" to auto-start
- Check Tools → Voice Review → Start MCP Server
- Ensure port 8000 is available

**Voice commands not working**
- Grant microphone permissions
- Use Chrome or Edge browser
- Check green status indicator

**ElevenLabs agent not responding**
- Verify agent ID in configuration
- Check ElevenLabs subscription
- Ensure internet connection

### **Debug Mode**
Enable debug logging in configuration:
```json
{
    "advanced": {
        "enable_debug_logging": true
    }
}
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **ElevenLabs** for conversational AI technology
- **Anki** for the spaced repetition platform
- **MCP Protocol** for AI assistant integration
- **Community Contributors** for feedback and testing

## 🌟 Support

- ⭐ **Star this repo** if you find it useful
- 🐛 **Report bugs** in GitHub Issues
- 💡 **Request features** in GitHub Discussions
- 📧 **Contact**: [your-email@domain.com]

---

**Perfect for commute studying and hands-free learning!** 🚀

*Transform your daily commute into productive study time with natural voice commands.* 
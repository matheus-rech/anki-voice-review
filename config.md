# Voice Review with AI Assistant - Configuration

This add-on enables hands-free flashcard review using voice commands and ElevenLabs conversational AI.

## Basic Settings

### Auto-start MCP Server
- **Default**: `true`
- **Description**: Automatically start the MCP server when Anki launches
- **Note**: The MCP server is required for AI assistant integration

### Show Voice Assistant
- **Default**: `true`  
- **Description**: Show voice control widgets and assistant interface
- **Note**: Can be toggled from the Tools menu

### ElevenLabs Agent ID
- **Default**: `"agent_5301k0wccfefeaxtkqr0kce7v66a"`
- **Description**: Your ElevenLabs conversational agent ID
- **Note**: Replace with your own agent ID if using a custom agent

### MCP Server Port
- **Default**: `8000`
- **Description**: Port for the MCP server to listen on
- **Warning**: Change only if port 8000 is already in use

### Auto-start from Cards
- **Default**: `true`
- **Description**: Allow voice controls on cards to automatically start the MCP server
- **Note**: Enables seamless "one-click" voice sessions

## Voice Recognition

### Widget Type
- **Options**: `"sidebar"`, `"floating"`, `"popup"`
- **Default**: `"sidebar"`
- **Description**: How voice controls are displayed in the interface

### Recognition Language
- **Default**: `"en-US"`
- **Description**: Language for speech recognition
- **Supported**: Any language supported by browser speech recognition

## Natural Language Mappings

The add-on understands natural language responses for card ratings:

### "Again" (Rating: 1)
- "again", "repeat", "forgot", "missed", "no"
- "totally forgot", "completely forgot", "no idea" 
- "blank", "drawing a blank", "clueless"

### "Hard" (Rating: 2)  
- "hard", "difficult", "struggled", "almost"
- "pretty hard", "took a while", "challenging"
- "eventually got it", "figured it out"

### "Good" (Rating: 3)
- "good", "correct", "yes", "got it", "remembered"
- "knew that", "right answer", "of course"
- "recognized it", "came to me"

### "Easy" (Rating: 4)
- "easy", "perfect", "instant", "obvious", "simple"
- "immediately", "too simple", "way too easy"
- "piece of cake", "no problem", "super obvious"

## UI Settings

### Show Status Indicator
- **Default**: `true`
- **Description**: Display connection status and voice session state

### Show Session Stats
- **Default**: `true`
- **Description**: Show cards reviewed, accuracy, and session duration

### Minimizable Panel
- **Default**: `true`
- **Description**: Allow double-click to minimize voice control panel

### Panel Position
- **Default**: `"bottom-right"`
- **Options**: `"bottom-right"`, `"bottom-left"`, `"top-right"`, `"top-left"`
- **Description**: Where to position the voice control panel

## Troubleshooting

### Common Issues

**Voice commands not working:**
- Ensure microphone permissions are granted
- Use Chrome or Edge browser for best speech recognition
- Check that MCP server is running (green status indicator)

**"MCP Server not connected" error:**
- Click "Start Voice" to auto-start the server
- Manually start from Tools → Voice Review → Start MCP Server
- Check that port 8000 is available

**ElevenLabs agent not responding:**
- Verify your `elevenlabs_agent_id` is correct
- Ensure you have an active ElevenLabs subscription
- Check internet connection for API access

### Reset to Defaults

To reset all settings to defaults, click "Restore Defaults" in the add-on configuration dialog.

## Voice Commands

### Navigation
- "next card" / "continue" / "next" → Advance to next card
- "show answer" / "reveal" / "answer" → Show the answer

### Session Control  
- "start" / "begin" → Start voice session
- "stop" / "end session" → Stop voice session

### Rating (Natural Language)
- "I forgot" → Again (1)
- "pretty hard" → Hard (2)
- "got it" → Good (3) 
- "too easy" → Easy (4)

### Keyboard Shortcuts
- **Ctrl+V**: Toggle voice session
- **Ctrl+N**: Next card (during session)
- **Ctrl+S**: Show answer (during session)

## Support

For support, feature requests, or bug reports, please visit:
https://github.com/matheus-rech/anki-voice-review

**Perfect for commute studying and hands-free learning!** 🎤 
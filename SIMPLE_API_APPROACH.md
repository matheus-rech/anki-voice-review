# 🎯 Simple ElevenLabs API Integration (No MCP Needed!)

## 🤔 **The Problem with MCP Approach**

**Current Complex Architecture:**
```
Anki Cards → Python Add-on → MCP Server → AI Assistant → ElevenLabs API
```

**Issues:**
- ❌ MCP library dependencies not available in Anki
- ❌ Server startup failures
- ❌ Complex debugging across multiple layers
- ❌ Fragile connection management
- ❌ Overkill for simple voice controls

## ✅ **Proposed Simple Architecture**

**Direct API Integration:**
```
Anki Cards → JavaScript → ElevenLabs API (Direct HTTP)
```

**Benefits:**
- ✅ No Python dependencies
- ✅ No server setup required
- ✅ Works entirely in browser
- ✅ Simple HTTP requests
- ✅ Easy to debug and maintain

## 🔧 **Implementation Plan**

### **1. Text-to-Speech (TTS)**
```javascript
async function speakCardContent(text) {
    const response = await fetch('https://api.elevenlabs.io/v1/text-to-speech/VOICE_ID', {
        method: 'POST',
        headers: {
            'Accept': 'audio/mpeg',
            'Content-Type': 'application/json',
            'xi-api-key': 'YOUR_API_KEY'
        },
        body: JSON.stringify({
            text: text,
            model_id: 'eleven_monolingual_v1',
            voice_settings: {
                stability: 0.5,
                similarity_boost: 0.5
            }
        })
    });
    
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.play();
}
```

### **2. Speech-to-Text (STT)**
```javascript
async function transcribeAudio(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob);
    formData.append('model', 'whisper-1');
    
    const response = await fetch('https://api.elevenlabs.io/v1/speech-to-text', {
        method: 'POST',
        headers: {
            'xi-api-key': 'YOUR_API_KEY'
        },
        body: formData
    });
    
    const result = await response.json();
    return result.text;
}
```

### **3. Conversational AI (Optional Enhancement)**
```javascript
async function getAIResponse(userInput, cardContext) {
    const response = await fetch('https://api.elevenlabs.io/v1/convai/conversations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'xi-api-key': 'YOUR_API_KEY'
        },
        body: JSON.stringify({
            agent_id: 'agent_5301k0wccfefeaxtkqr0kce7v66a',
            text: userInput,
            context: cardContext
        })
    });
    
    return response.json();
}
```

## 🎨 **Simplified Voice Control Architecture**

### **Core JavaScript Module: `simple_voice_controls.js`**
```javascript
class SimpleVoiceControls {
    constructor(apiKey, voiceId, agentId) {
        this.apiKey = apiKey;
        this.voiceId = voiceId;
        this.agentId = agentId;
        this.recognition = null;
        this.session = { active: false, stats: {} };
    }
    
    // Direct API methods
    async speak(text) { /* TTS implementation */ }
    async listen() { /* STT implementation */ }
    async processCommand(command) { /* Command processing */ }
    async getAIHelp(context) { /* Optional AI assistance */ }
    
    // Anki integration
    rateCard(ease) { window.pycmd(`ease${ease}`); }
    nextCard() { window.pycmd('ans'); }
    showAnswer() { window.pycmd('ans'); }
}
```

### **Configuration (Simple)**
```javascript
const voiceControls = new SimpleVoiceControls(
    'your-elevenlabs-api-key',
    'cgSgspJ2msm6clMCkdW9', // Jessica voice
    'agent_5301k0wccfefeaxtkqr0kce7v66a' // Your agent
);
```

## 🚀 **Benefits of This Approach**

### **1. Simplicity**
- Single JavaScript file
- No Python dependencies
- No server setup
- Direct browser integration

### **2. Reliability**
- HTTP requests are well-tested
- No complex connection management
- Clear error handling
- Works in any modern browser

### **3. Performance**
- No intermediate servers
- Direct API calls
- Minimal latency
- Efficient resource usage

### **4. Maintainability**
- Easy to debug (browser dev tools)
- Clear API documentation
- Simple error messages
- Straightforward testing

### **5. Compatibility**
- Works in any Anki environment
- No Python version conflicts
- Cross-platform support
- Future-proof architecture

## 📝 **Implementation Steps**

### **Phase 1: Replace MCP with Direct API**
1. Create `simple_voice_controls.js`
2. Implement direct ElevenLabs API calls
3. Replace MCP server logic with HTTP requests
4. Test basic TTS/STT functionality

### **Phase 2: Enhanced Features**
1. Add conversational AI integration
2. Implement advanced voice commands
3. Add session management
4. Optimize for mobile use

### **Phase 3: Polish**
1. Error handling and recovery
2. Configuration interface
3. Performance optimization
4. Documentation and examples

## 🎯 **Result: Clean, Simple, Reliable**

**Instead of:**
- Complex MCP server setup
- Python dependency management
- Multi-layer debugging
- Fragile connection handling

**We get:**
- Single JavaScript file
- Direct API integration
- Browser-native functionality
- Simple configuration

## 💡 **Why This Wasn't Done Originally**

The MCP approach was designed for:
- AI assistants to query Anki data
- Complex multi-agent workflows
- Advanced conversational scenarios

**But for voice controls, we just need:**
- Play audio (TTS)
- Recognize speech (STT)
- Process simple commands
- Optional AI enhancement

**Direct API is perfect for this use case!**

---

**Recommendation: Refactor to use direct ElevenLabs API integration for a much simpler, more reliable solution.** 
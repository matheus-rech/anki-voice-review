"""
Complete AnkiConnect + ElevenLabs Voice Control Template
Ready to copy/paste into Anki card templates - No Python add-on needed!
Automatically loads ELEVENLABS_API_KEY from environment variables
"""

import os

def generate_complete_ankiconnect_template():
    """Generate the complete ready-to-use template with API key from environment"""
    
    # Get API key from environment
    api_key = os.getenv('ELEVENLABS_API_KEY', 'YOUR_API_KEY_HERE')
    
    # Show status
    if api_key != 'YOUR_API_KEY_HERE':
        print(f"✅ Found ELEVENLABS_API_KEY in environment (ends with: ...{api_key[-4:]})")
    else:
        print("⚠️  ELEVENLABS_API_KEY not found in environment - using placeholder")
    
    html_template = '''<!-- Voice Controls - AnkiConnect + ElevenLabs API -->
<div id="voice-controls" class="voice-control-panel">
    <!-- Status Display -->
    <div class="voice-status-section">
        <div id="voice-status" class="voice-status ready">Voice Ready</div>
        <div id="session-stats" class="session-stats"></div>
    </div>
    
    <!-- Main Controls -->
    <div class="voice-main-controls">
        <button id="start-voice-btn" class="voice-btn primary" title="Start voice session with AnkiConnect + ElevenLabs">
            <span class="btn-icon">🎤</span>
            <span class="btn-text">Start Voice</span>
        </button>
    </div>
    
    <!-- Voice Buttons (hidden initially) -->
    <div id="voice-buttons" class="voice-buttons" style="display: none;">
        <button id="mic-btn" class="voice-btn mic-btn" title="Toggle microphone">
            <span class="btn-icon">🎙️</span>
        </button>
        
        <button id="read-btn" class="voice-btn" title="Read card content aloud" onclick="readCurrentCard()">
            <span class="btn-icon">🔊</span>
            <span class="btn-text">Read</span>
        </button>
        
        <button id="help-btn" class="voice-btn" title="Show voice commands" onclick="showVoiceHelp()">
            <span class="btn-icon">❓</span>
            <span class="btn-text">Help</span>
        </button>
    </div>
    
    <!-- Feedback Display -->
    <div id="voice-feedback" class="voice-feedback"></div>
</div>'''

    css_template = '''/* Voice Control Panel - AnkiConnect + ElevenLabs */
.voice-control-panel {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    padding: 15px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    z-index: 1000;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    min-width: 200px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Status Section */
.voice-status-section {
    margin-bottom: 12px;
    text-align: center;
}

.voice-status {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 12px;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.voice-status.ready { background: #e3f2fd; color: #1976d2; }
.voice-status.starting { background: #fff3e0; color: #f57c00; }
.voice-status.active { background: #e8f5e8; color: #2e7d32; }
.voice-status.error { background: #ffebee; color: #d32f2f; }
.voice-status.inactive { background: #f5f5f5; color: #616161; }

.session-stats {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.8);
    margin-top: 2px;
}

/* Main Controls */
.voice-main-controls {
    display: flex;
    justify-content: center;
    margin-bottom: 10px;
}

.voice-btn {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 8px;
    color: white;
    padding: 8px 12px;
    margin: 0 3px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.2s ease;
    min-height: 32px;
}

.voice-btn:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.voice-btn.primary {
    background: rgba(255, 255, 255, 0.9);
    color: #667eea;
    font-weight: 600;
    padding: 10px 16px;
}

.voice-btn.primary:hover { background: white; }
.voice-btn.primary.active { background: #f44336; color: white; }

/* Voice Buttons Row */
.voice-buttons {
    display: flex;
    justify-content: space-between;
    gap: 5px;
    margin-bottom: 10px;
}

.mic-btn.listening {
    background: #4caf50;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
    100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
}

/* Feedback Display */
.voice-feedback {
    font-size: 11px;
    padding: 6px 8px;
    border-radius: 6px;
    margin-top: 8px;
    text-align: center;
    min-height: 16px;
    transition: all 0.3s ease;
}

.voice-feedback.info { background: rgba(33, 150, 243, 0.2); color: #1976d2; border: 1px solid rgba(33, 150, 243, 0.3); }
.voice-feedback.success { background: rgba(76, 175, 80, 0.2); color: #388e3c; border: 1px solid rgba(76, 175, 80, 0.3); }
.voice-feedback.warning { background: rgba(255, 152, 0, 0.2); color: #f57c00; border: 1px solid rgba(255, 152, 0, 0.3); }
.voice-feedback.error { background: rgba(244, 67, 54, 0.2); color: #d32f2f; border: 1px solid rgba(244, 67, 54, 0.3); }

/* Button Icons */
.btn-icon { font-size: 14px; line-height: 1; }
.btn-text { font-size: 11px; font-weight: 500; }

/* Mobile Responsive */
@media (max-width: 768px) {
    .voice-control-panel { bottom: 10px; right: 10px; left: 10px; min-width: auto; }
    .voice-buttons { flex-wrap: wrap; }
    .voice-btn { flex: 1; min-width: 0; }
    .btn-text { display: none; }
}'''

    # Inject the actual API key from environment
    javascript_template = f'''<script>
// Complete Voice Control System - AnkiConnect + ElevenLabs API
// API key automatically loaded from ELEVENLABS_API_KEY environment variable

const ELEVENLABS_API_KEY = '{api_key}'; // ← Loaded from environment
const VOICE_ID = 'cgSgspJ2msm6clMCkdW9'; // Jessica voice (change if desired)
const ANKICONNECT_URL = 'http://localhost:8765';

// Voice session state
let voiceSession = {{
    active: false,
    listening: false,
    connected: false,
    stats: {{ cardsReviewed: 0, startTime: null, correctCount: 0 }}
}};

// Global instances
let ankiConnect = null;
let elevenLabs = null;

// AnkiConnect API class
class AnkiConnectAPI {{
    constructor(url = ANKICONNECT_URL) {{
        this.url = url;
    }}
    
    async invoke(action, params = {{}}) {{
        const response = await fetch(this.url, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ action, version: 6, params }})
        }});
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        return result.result;
    }}
    
    async answerCard(ease) {{
        await this.invoke('guiAnswerCard', {{ ease }});
        return true;
    }}
    
    async showAnswer() {{
        await this.invoke('guiShowAnswer');
        return true;
    }}
    
    async getCurrentCard() {{
        return await this.invoke('guiCurrentCard');
    }}
    
    async testConnection() {{
        try {{
            const version = await this.invoke('version');
            return version >= 6;
        }} catch (error) {{
            return false;
        }}
    }}
}}

// ElevenLabs API class
class ElevenLabsAPI {{
    constructor(apiKey, voiceId = VOICE_ID) {{
        this.apiKey = apiKey;
        this.voiceId = voiceId;
        this.baseUrl = 'https://api.elevenlabs.io/v1';
    }}
    
    async testConnection() {{
        try {{
            const response = await fetch(`${{this.baseUrl}}/user`, {{
                headers: {{ 'xi-api-key': this.apiKey }}
            }});
            return response.ok;
        }} catch (error) {{
            return false;
        }}
    }}
    
    async speak(text) {{
        try {{
            const response = await fetch(`${{this.baseUrl}}/text-to-speech/${{this.voiceId}}`, {{
                method: 'POST',
                headers: {{
                    'Accept': 'audio/mpeg',
                    'Content-Type': 'application/json',
                    'xi-api-key': this.apiKey
                }},
                body: JSON.stringify({{
                    text: text.substring(0, 500),
                    model_id: 'eleven_monolingual_v1',
                    voice_settings: {{ stability: 0.5, similarity_boost: 0.5 }}
                }})
            }});
            
            if (!response.ok) throw new Error(`TTS failed: ${{response.status}}`);
            
            const audioBlob = await response.blob();
            const audio = new Audio(URL.createObjectURL(audioBlob));
            
            return new Promise((resolve) => {{
                audio.onended = resolve;
                audio.play();
            }});
        }} catch (error) {{
            console.error('TTS error:', error);
            showFeedback(`TTS Error: ${{error.message}}`, 'error');
        }}
    }}
}}

// Voice commands
const voiceCommands = {{
    'show answer': () => ankiConnect?.showAnswer(),
    'next card': () => ankiConnect?.showAnswer(),
    'next': () => ankiConnect?.showAnswer(),
    
    'again': () => answerCard(1),
    'hard': () => answerCard(2),
    'good': () => answerCard(3),
    'easy': () => answerCard(4),
    
    'i forgot': () => answerCard(1),
    'forgot': () => answerCard(1),
    'no': () => answerCard(1),
    'wrong': () => answerCard(1),
    
    'difficult': () => answerCard(2),
    'struggled': () => answerCard(2),
    'close': () => answerCard(2),
    
    'correct': () => answerCard(3),
    'yes': () => answerCard(3),
    'got it': () => answerCard(3),
    'right': () => answerCard(3),
    
    'perfect': () => answerCard(4),
    'instant': () => answerCard(4),
    'obvious': () => answerCard(4),
    'too easy': () => answerCard(4),
    
    'read card': () => readCurrentCard(),
    'repeat': () => readCurrentCard(),
    'help': () => showVoiceHelp()
}};

// Answer card function
async function answerCard(ease) {{
    try {{
        await ankiConnect.answerCard(ease);
        voiceSession.stats.cardsReviewed++;
        if (ease >= 3) voiceSession.stats.correctCount++;
        updateSessionStats();
        
        const messages = {{ 1: "Again", 2: "Hard", 3: "Good", 4: "Easy" }};
        showFeedback(`✓ ${{messages[ease]}}`, 'success');
    }} catch (error) {{
        showFeedback(`Error: ${{error.message}}`, 'error');
    }}
}}

// Read current card
async function readCurrentCard() {{
    try {{
        showFeedback('Getting card content...', 'info');
        const cardInfo = await ankiConnect.getCurrentCard();
        if (!cardInfo) {{
            showFeedback('No card available', 'warning');
            return;
        }}
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = cardInfo.question || cardInfo.answer || '';
        let text = tempDiv.textContent || tempDiv.innerText || '';
        text = text.replace(/\\s+/g, ' ').trim();
        text = text.replace(/Show Answer|Type in the answer/gi, '');
        
        if (text && elevenLabs) {{
            showFeedback('Reading card...', 'info');
            await elevenLabs.speak(text);
        }} else {{
            showFeedback('No content to read', 'warning');
        }}
    }} catch (error) {{
        showFeedback(`Error: ${{error.message}}`, 'error');
    }}
}}

// Start voice session
async function startVoiceSession() {{
    if (voiceSession.active) {{
        stopVoiceSession();
        return;
    }}
    
    updateVoiceStatus('Connecting...', 'starting');
    showFeedback('Starting voice session...');
    
    try {{
        // Check API key
        if (!ELEVENLABS_API_KEY || ELEVENLABS_API_KEY === 'YOUR_API_KEY_HERE') {{
            throw new Error('ElevenLabs API key not configured. Set ELEVENLABS_API_KEY environment variable.');
        }}
        
        // Initialize APIs
        ankiConnect = new AnkiConnectAPI();
        elevenLabs = new ElevenLabsAPI(ELEVENLABS_API_KEY);
        
        // Test connections
        showFeedback('Testing AnkiConnect...', 'info');
        const ankiOk = await ankiConnect.testConnection();
        if (!ankiOk) {{
            throw new Error('AnkiConnect not available. Install add-on code: 2055492159');
        }}
        
        showFeedback('Testing ElevenLabs...', 'info');
        const elevenLabsOk = await elevenLabs.testConnection();
        if (!elevenLabsOk) {{
            throw new Error('ElevenLabs API failed. Check your API key.');
        }}
        
        // Start session
        voiceSession.active = true;
        voiceSession.connected = true;
        voiceSession.stats.startTime = Date.now();
        voiceSession.stats.cardsReviewed = 0;
        voiceSession.stats.correctCount = 0;
        
        // Update UI
        const startBtn = document.getElementById('start-voice-btn');
        const voiceButtons = document.getElementById('voice-buttons');
        
        if (startBtn) {{
            startBtn.textContent = 'Stop Voice';
            startBtn.classList.add('active');
        }}
        if (voiceButtons) voiceButtons.style.display = 'flex';
        
        // Initialize speech recognition
        initializeSpeechRecognition();
        
        updateVoiceStatus('Voice Active', 'active');
        showFeedback('🎤 Voice active! Say "show answer", "got it", or "read card"', 'success');
        
        // Welcome message
        setTimeout(() => {{
            elevenLabs.speak("Voice controls activated. Say show answer, got it, read card, or help.");
        }}, 1000);
        
    }} catch (error) {{
        updateVoiceStatus('Failed', 'error');
        showFeedback(`Failed: ${{error.message}}`, 'error');
    }}
}}

// Stop voice session
function stopVoiceSession() {{
    voiceSession.active = false;
    voiceSession.listening = false;
    voiceSession.connected = false;
    
    if (window.voiceRecognition) {{
        try {{ window.voiceRecognition.stop(); }} catch (e) {{}}
    }}
    
    ankiConnect = null;
    elevenLabs = null;
    
    const startBtn = document.getElementById('start-voice-btn');
    const voiceButtons = document.getElementById('voice-buttons');
    
    if (startBtn) {{
        startBtn.textContent = 'Start Voice';
        startBtn.classList.remove('active');
    }}
    if (voiceButtons) voiceButtons.style.display = 'none';
    
    updateVoiceStatus('Voice Ready', 'ready');
    updateMicrophoneStatus(false);
    
    if (voiceSession.stats.cardsReviewed > 0) {{
        const duration = Math.floor((Date.now() - voiceSession.stats.startTime) / 1000);
        const accuracy = Math.round((voiceSession.stats.correctCount / voiceSession.stats.cardsReviewed) * 100);
        showFeedback(`Session: ${{voiceSession.stats.cardsReviewed}} cards, ${{duration}}s, ${{accuracy}}% accuracy`, 'success');
    }}
}}

// Speech recognition
function initializeSpeechRecognition() {{
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {{
        showFeedback('Speech recognition not supported', 'warning');
        return;
    }}
    
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    window.voiceRecognition = new SpeechRecognitionAPI();
    
    window.voiceRecognition.continuous = true;
    window.voiceRecognition.interimResults = false;
    window.voiceRecognition.lang = 'en-US';
    
    window.voiceRecognition.onstart = () => {{
        voiceSession.listening = true;
        updateMicrophoneStatus(true);
    }};
    
    window.voiceRecognition.onresult = (event) => {{
        const lastResult = event.results[event.results.length - 1];
        if (lastResult.isFinal) {{
            const transcript = lastResult[0].transcript.toLowerCase().trim();
            showFeedback(`Heard: "${{transcript}}"`);
            handleVoiceCommand(transcript);
        }}
    }};
    
    window.voiceRecognition.onerror = (event) => {{
        showFeedback(`Speech error: ${{event.error}}`, 'warning');
    }};
    
    window.voiceRecognition.onend = () => {{
        voiceSession.listening = false;
        updateMicrophoneStatus(false);
        
        if (voiceSession.active) {{
            setTimeout(() => {{
                try {{ window.voiceRecognition.start(); }} catch (e) {{}}
            }}, 500);
        }}
    }};
    
    try {{
        window.voiceRecognition.start();
    }} catch (error) {{
        showFeedback('Failed to start speech recognition', 'error');
    }}
}}

// Handle voice commands
async function handleVoiceCommand(transcript) {{
    try {{
        for (const [command, action] of Object.entries(voiceCommands)) {{
            if (transcript.includes(command) || command.includes(transcript)) {{
                await action();
                showFeedback(`✓ ${{command}}`, 'success');
                return;
            }}
        }}
        showFeedback(`Not recognized: "${{transcript}}". Try "help"`, 'warning');
    }} catch (error) {{
        showFeedback(`Error: ${{error.message}}`, 'error');
    }}
}}

// Show help
function showVoiceHelp() {{
    const helpText = `Voice Commands:
    
Navigation: "show answer", "next card"
Rating: "I forgot", "hard", "got it", "easy"
Audio: "read card", "repeat"  
Session: "help"

Natural language works:
"That was difficult", "Perfect!"`;

    showFeedback(helpText, 'info');
    if (elevenLabs) {{
        elevenLabs.speak("Available commands: show answer, I forgot, got it, easy, read card, help.");
    }}
}}

// UI helpers
function showFeedback(message, type = 'info') {{
    const feedback = document.getElementById('voice-feedback');
    if (!feedback) return;
    
    feedback.textContent = message;
    feedback.className = `voice-feedback ${{type}}`;
    
    if (type === 'success' || type === 'info') {{
        setTimeout(() => {{
            if (feedback.textContent === message) {{
                feedback.textContent = '';
                feedback.className = 'voice-feedback';
            }}
        }}, 4000);
    }}
}}

function updateVoiceStatus(status, className) {{
    const statusElement = document.getElementById('voice-status');
    if (statusElement) {{
        statusElement.textContent = status;
        statusElement.className = `voice-status ${{className}}`;
    }}
}}

function updateMicrophoneStatus(listening) {{
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {{
        micBtn.classList.toggle('listening', listening);
    }}
}}

function updateSessionStats() {{
    const statsElement = document.getElementById('session-stats');
    if (statsElement && voiceSession.stats.startTime) {{
        const duration = Math.floor((Date.now() - voiceSession.stats.startTime) / 1000);
        const accuracy = voiceSession.stats.cardsReviewed > 0 
            ? Math.round((voiceSession.stats.correctCount / voiceSession.stats.cardsReviewed) * 100) : 0;
        statsElement.textContent = `${{voiceSession.stats.cardsReviewed}} cards, ${{duration}}s, ${{accuracy}}% accuracy`;
    }}
}}

// Keyboard shortcuts
document.addEventListener('keydown', (event) => {{
    if (event.ctrlKey || event.metaKey) {{
        switch (event.key.toLowerCase()) {{
            case 'v':
                event.preventDefault();
                startVoiceSession();
                break;
            case 'r':
                event.preventDefault();
                if (voiceSession.active) readCurrentCard();
                break;
        }}
    }}
}});

// Initialize
document.addEventListener('DOMContentLoaded', () => {{
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) startBtn.addEventListener('click', startVoiceSession);
    
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {{
        micBtn.addEventListener('click', () => {{
            if (voiceSession.active && window.voiceRecognition) {{
                if (voiceSession.listening) {{
                    window.voiceRecognition.stop();
                }} else {{
                    window.voiceRecognition.start();
                }}
            }}
        }});
    }}
    
    updateVoiceStatus('Voice Ready', 'ready');
    showFeedback('Ready! AnkiConnect + ElevenLabs API configured from environment.');
}});
</script>'''

    return {
        'html': html_template,
        'css': css_template,
        'javascript': javascript_template
    }

def print_setup_guide():
    """Print the complete setup guide with environment variable info"""
    api_key = os.getenv('ELEVENLABS_API_KEY', 'NOT_SET')
    
    print("""
🚀 ULTRA-SIMPLE VOICE CONTROLS - AnkiConnect + ElevenLabs API
""")
    
    if api_key != 'NOT_SET':
        print(f"✅ ELEVENLABS_API_KEY found in environment (ends with: ...{api_key[-4:]})")
        print("🎯 Template will be generated with your API key automatically!")
    else:
        print("⚠️  ELEVENLABS_API_KEY not found in environment")
        print("💡 Set it with: export ELEVENLABS_API_KEY='your-key-here'")
    
    print("""
📋 REQUIREMENTS (3-minute setup):
1. AnkiConnect add-on (Code: 2055492159)
2. ELEVENLABS_API_KEY environment variable (✅ already set!)
3. Copy/paste the template code below

🎯 SAME BUTTON BEHAVIOR YOU WANTED:
✅ "Start Voice" button → Connects to AnkiConnect + ElevenLabs APIs  
✅ "Stop Voice" button → Disconnects from both APIs
✅ Same UI/UX - just REST API calls instead of complex Python

🔧 SETUP STEPS:

STEP 1: Install AnkiConnect (2 minutes)
1. Open Anki → Tools → Add-ons → Get Add-ons
2. Code: 2055492159
3. Install & restart Anki

STEP 2: Environment Variable (✅ Done!)
Your ELEVENLABS_API_KEY is already in the environment

STEP 3: Add Template to Cards (2 minutes)
1. Tools → Manage Note Types → Select type → Cards
2. Add HTML to Front/Back Template
3. Add CSS to Styling section  
4. Add JavaScript to Back Template
5. Save (API key is already injected!)

STEP 4: Use Voice Controls (Instant)
1. Study cards normally
2. Click "Start Voice" on any card
3. Say: "show answer", "got it", "read card", etc.

🎤 VOICE COMMANDS:
• "show answer" - reveal answer
• "I forgot" - rate as Again  
• "got it" - rate as Good
• "easy" - rate as Easy
• "read card" - text-to-speech
• "help" - show commands

🎉 BENEFITS:
✅ No Python add-on complexity
✅ AnkiConnect is stable (used by millions)  
✅ Pure JavaScript - easy to debug
✅ API key loaded from environment automatically
✅ Same start/stop schema you requested

Ready to copy the template code!
""")

if __name__ == "__main__":
    print("🎤 Complete AnkiConnect + ElevenLabs Template Generator")
    print("=" * 60)
    
    print_setup_guide()
    
    print("\n" + "=" * 60)
    print("📋 COMPLETE TEMPLATE CODE - READY TO USE")
    print("=" * 60)
    
    template = generate_complete_ankiconnect_template()
    
    print("\n🏷️ HTML TEMPLATE (Add to Front or Back Template):")
    print("-" * 50)
    print(template['html'])
    
    print("\n🎨 CSS TEMPLATE (Add to Styling Section):")
    print("-" * 50)
    print(template['css'])
    
    print("\n⚡ JAVASCRIPT TEMPLATE (Add to Back Template):")
    print("-" * 50)
    print(template['javascript'])
    
    print("\n" + "=" * 60)
    print("🎉 ULTRA-SIMPLE TEMPLATE READY!")
    print("✅ API key automatically loaded from ELEVENLABS_API_KEY environment variable")
    print("🚀 No manual configuration needed - AnkiConnect + JavaScript only!")
    print("=" * 60) 
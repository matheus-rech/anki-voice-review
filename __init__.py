"""
Complete Voice Review Add-on for Anki - Personal Edition
Automatically injects voice controls into all cards using AnkiConnect + ElevenLabs APIs
Pre-configured with your personal ElevenLabs API key for immediate use
No manual template editing required - works independently
"""

import logging
import json
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-review-addon")

try:
    # Anki imports
    from aqt import mw, gui_hooks
    from aqt.utils import showInfo, showWarning
    from aqt.qt import QAction, QMenu
    from anki.hooks import addHook

    # Import our modules
    from .utils.config_manager import ConfigManager
    from .utils.personal_config import get_personal_config
    
    ANKI_AVAILABLE = True
    logger.info("Voice Review Add-on: Anki environment detected")
except ImportError as e:
    ANKI_AVAILABLE = False
    logger.warning(f"Anki not available: {e}")

class PersonalVoiceReviewAddon:
    """
    Personal Voice Review Add-on - Pre-configured for You
    Automatically injects voice controls into all Anki cards
    Uses AnkiConnect + ElevenLabs APIs with your personal API key
    Ready to use out of the box!
    """
    
    def __init__(self):
        self.config_manager = None
        self.voice_controls_active = False
        self.personal_config = None
        
        if ANKI_AVAILABLE:
            self.initialize()
    
    def initialize(self):
        """Initialize your personal add-on"""
        try:
            logger.info("Initializing Personal Voice Review Add-on...")
            
            # Initialize configuration
            self.config_manager = ConfigManager()
            
            # Initialize personal configuration with your API key
            self.personal_config = get_personal_config()
            
            # Log API key status
            status = self.personal_config.get_status_info()
            if status['configured']:
                logger.info(f"ElevenLabs API key: {status['message']} ({status['key_suffix']})")
            else:
                logger.warning("ElevenLabs API key: Not available")
            
            # Set up Anki hooks for automatic injection
            self._setup_hooks()
            
            # Set up menu
            self._setup_menu()
            
            logger.info("Personal Voice Review Add-on initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize add-on: {e}")
            if ANKI_AVAILABLE:
                showWarning(f"Voice Review Add-on initialization failed: {str(e)}")
    
    def _setup_hooks(self):
        """Set up Anki hooks for automatic voice control injection"""
        # Hook into card display to automatically inject voice controls
        gui_hooks.webview_will_set_content.append(self._inject_voice_controls)
        
        # Hook for JavaScript commands from cards
        gui_hooks.webview_did_receive_js_message.append(self._handle_js_message)
        
        # Hook for profile loading
        gui_hooks.profile_did_open.append(self._on_profile_opened)
    
    def _inject_voice_controls(self, web_content, context):
        """Automatically inject voice controls into all card content"""
        try:
            # Only inject into reviewer context (not browser, editor, etc.)
            if not hasattr(context, 'card') or context.card is None:
                return
            
            logger.info("Injecting voice controls into card")
            
            # Get the complete voice control system
            voice_html, voice_css, voice_js = self._get_complete_voice_system()
            
            # Inject CSS into head
            if '<head>' in web_content.html:
                web_content.html = web_content.html.replace(
                    '<head>', 
                    f'<head><style>{voice_css}</style>'
                )
            else:
                web_content.html = f'<style>{voice_css}</style>' + web_content.html
            
            # Inject HTML and JavaScript into body
            if '</body>' in web_content.html:
                web_content.html = web_content.html.replace(
                    '</body>', 
                    f'{voice_html}<script>{voice_js}</script></body>'
                )
            else:
                web_content.html += f'{voice_html}<script>{voice_js}</script>'
            
        except Exception as e:
            logger.error(f"Failed to inject voice controls: {e}")
    
    def _get_complete_voice_system(self):
        """Get the complete voice control system with your personal settings"""
        
        # HTML for voice control panel
        voice_html = '''
        <!-- Personal Voice Controls - Auto-Injected -->
        <div id="voice-controls" class="voice-control-panel">
            <div class="voice-status-section">
                <div id="voice-status" class="voice-status ready">Voice Ready</div>
                <div id="session-stats" class="session-stats"></div>
            </div>
            
            <div class="voice-main-controls">
                <button id="start-voice-btn" class="voice-btn primary" title="Start voice session">
                    <span class="btn-icon">🎤</span>
                    <span class="btn-text">Start Voice</span>
                </button>
            </div>
            
            <div id="voice-buttons" class="voice-buttons" style="display: none;">
                <button id="mic-btn" class="voice-btn mic-btn" title="Toggle microphone">
                    <span class="btn-icon">🎙️</span>
                </button>
                
                <button id="read-btn" class="voice-btn" title="Read card aloud">
                    <span class="btn-icon">🔊</span>
                    <span class="btn-text">Read</span>
                </button>
                
                <button id="help-btn" class="voice-btn" title="Show commands">
                    <span class="btn-icon">❓</span>
                    <span class="btn-text">Help</span>
                </button>
            </div>
            
            <div id="voice-feedback" class="voice-feedback"></div>
        </div>
        '''
        
        # CSS for voice control styling (unchanged)
        voice_css = '''
        /* Personal Voice Control Panel - Auto-Injected */
        .voice-control-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            min-width: 200px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

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

        .session-stats {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.8);
            margin-top: 2px;
        }

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
        }

        .voice-btn.primary {
            background: rgba(255, 255, 255, 0.9);
            color: #667eea;
            font-weight: 600;
            padding: 10px 16px;
        }

        .voice-btn.primary:hover { background: white; }
        .voice-btn.primary.active { background: #f44336; color: white; }

        .voice-buttons {
            display: flex;
            justify-content: space-between;
            gap: 5px;
            margin-bottom: 10px;
        }

        .mic-btn.listening {
            background: #4caf50;
            animation: voice-pulse 1.5s infinite;
        }

        @keyframes voice-pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }

        .voice-feedback {
            font-size: 11px;
            padding: 6px 8px;
            border-radius: 6px;
            margin-top: 8px;
            text-align: center;
            min-height: 16px;
            transition: all 0.3s ease;
        }

        .voice-feedback.info { background: rgba(33, 150, 243, 0.2); color: #1976d2; }
        .voice-feedback.success { background: rgba(76, 175, 80, 0.2); color: #388e3c; }
        .voice-feedback.warning { background: rgba(255, 152, 0, 0.2); color: #f57c00; }
        .voice-feedback.error { background: rgba(244, 67, 54, 0.2); color: #d32f2f; }

        .btn-icon { font-size: 14px; line-height: 1; }
        .btn-text { font-size: 11px; font-weight: 500; }

        @media (max-width: 768px) {
            .voice-control-panel { bottom: 10px; right: 10px; left: 10px; min-width: auto; }
            .voice-buttons { flex-wrap: wrap; }
            .voice-btn { flex: 1; min-width: 0; }
            .btn-text { display: none; }
        }
        '''
        
        # JavaScript with your personal API key pre-configured
        api_key = self.personal_config.get_api_key() or 'NOT_CONFIGURED'
        voice_id = self.personal_config.get_voice_id()
        voice_settings = self.personal_config.get_voice_settings()
        
        voice_js = f'''
        // Personal Voice Control System - Pre-configured for You
        (function() {{
            // Prevent multiple initialization
            if (window.voiceControlsInitialized) return;
            window.voiceControlsInitialized = true;
            
            console.log('🎯 Personal Voice Controls: Pre-configured and ready!');
            
            const ELEVENLABS_API_KEY = '{api_key}';
            const VOICE_ID = '{voice_id}';
            const VOICE_SETTINGS = {json.dumps(voice_settings)};
            const ANKICONNECT_URL = 'http://localhost:8765';
            
            let voiceSession = {{
                active: false,
                listening: false,
                connected: false,
                stats: {{ cardsReviewed: 0, startTime: null, correctCount: 0 }}
            }};
            
            let ankiConnect = null;
            let elevenLabs = null;
            
            // AnkiConnect API
            class AnkiConnectAPI {{
                constructor(url = ANKICONNECT_URL) {{
                    this.url = url;
                }}
                
                async invoke(action, params = {{}}) {{
                    try {{
                        const response = await fetch(this.url, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ action, version: 6, params }})
                        }});
                        const result = await response.json();
                        if (result.error) throw new Error(result.error);
                        return result.result;
                    }} catch (error) {{
                        console.error('AnkiConnect error:', error);
                        throw error;
                    }}
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
            
            // ElevenLabs API with your personal settings
            class PersonalElevenLabsAPI {{
                constructor(apiKey, voiceId = VOICE_ID) {{
                    this.apiKey = apiKey;
                    this.voiceId = voiceId;
                    this.baseUrl = 'https://api.elevenlabs.io/v1';
                    this.voiceSettings = VOICE_SETTINGS;
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
                                voice_settings: this.voiceSettings
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
            
            // Core functions
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
                        showFeedback('Reading card with your voice...', 'info');
                        await elevenLabs.speak(text);
                    }} else {{
                        showFeedback('No content to read', 'warning');
                    }}
                }} catch (error) {{
                    showFeedback(`Error: ${{error.message}}`, 'error');
                }}
            }}
            
            async function startVoiceSession() {{
                if (voiceSession.active) {{
                    stopVoiceSession();
                    return;
                }}
                
                updateVoiceStatus('Connecting...', 'starting');
                showFeedback('Starting your personal voice session...');
                
                try {{
                    if (ELEVENLABS_API_KEY === 'NOT_CONFIGURED') {{
                        throw new Error('Personal API key not available. Please check add-on installation.');
                    }}
                    
                    ankiConnect = new AnkiConnectAPI();
                    elevenLabs = new PersonalElevenLabsAPI(ELEVENLABS_API_KEY);
                    
                    showFeedback('Testing AnkiConnect...', 'info');
                    const ankiOk = await ankiConnect.testConnection();
                    if (!ankiOk) {{
                        throw new Error('AnkiConnect not available. Install add-on code: 2055492159');
                    }}
                    
                    showFeedback('Testing your ElevenLabs connection...', 'info');
                    const elevenLabsOk = await elevenLabs.testConnection();
                    if (!elevenLabsOk) {{
                        throw new Error('ElevenLabs API connection failed. Check your internet connection.');
                    }}
                    
                    voiceSession.active = true;
                    voiceSession.connected = true;
                    voiceSession.stats.startTime = Date.now();
                    voiceSession.stats.cardsReviewed = 0;
                    voiceSession.stats.correctCount = 0;
                    
                    const startBtn = document.getElementById('start-voice-btn');
                    const voiceButtons = document.getElementById('voice-buttons');
                    
                    if (startBtn) {{
                        startBtn.textContent = 'Stop Voice';
                        startBtn.classList.add('active');
                    }}
                    if (voiceButtons) voiceButtons.style.display = 'flex';
                    
                    initializeSpeechRecognition();
                    
                    updateVoiceStatus('Personal Voice Active', 'active');
                    showFeedback('🎤 Your personal voice controls are active!', 'success');
                    
                    setTimeout(() => {{
                        elevenLabs.speak("Personal voice controls activated. Ready for hands-free studying!");
                    }}, 1000);
                    
                }} catch (error) {{
                    updateVoiceStatus('Connection Failed', 'error');
                    showFeedback(`Failed: ${{error.message}}`, 'error');
                }}
            }}
            
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
                    showFeedback(`Session complete: ${{voiceSession.stats.cardsReviewed}} cards, ${{duration}}s, ${{accuracy}}% accuracy`, 'success');
                }}
            }}
            
            function initializeSpeechRecognition() {{
                if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {{
                    showFeedback('Speech recognition not supported in this browser', 'warning');
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
            
            function showVoiceHelp() {{
                const helpText = `Personal Voice Commands:
Navigation: "show answer", "next card"  
Rating: "I forgot", "hard", "got it", "easy"
Audio: "read card", "repeat"
Help: "help"

Speak naturally - your personal voice system understands!`;
                showFeedback(helpText, 'info');
                if (elevenLabs) {{
                    elevenLabs.speak("Your personal voice commands: show answer, I forgot, got it, easy, read card, help.");
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
            
            // Initialize event listeners
            function initializePersonalVoiceControls() {{
                const startBtn = document.getElementById('start-voice-btn');
                if (startBtn) {{
                    startBtn.addEventListener('click', startVoiceSession);
                }}
                
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
                
                const readBtn = document.getElementById('read-btn');
                if (readBtn) {{
                    readBtn.addEventListener('click', readCurrentCard);
                }}
                
                const helpBtn = document.getElementById('help-btn');
                if (helpBtn) {{
                    helpBtn.addEventListener('click', showVoiceHelp);
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
                
                updateVoiceStatus('Voice Ready', 'ready');
                showFeedback('🎯 Personal voice controls ready! Pre-configured for you.');
                
                console.log('🎤 Personal Voice Controls Initialized');
                console.log('  • Pre-configured with your API key');
                console.log('  • Optimized voice settings');
                console.log('  • AnkiConnect + ElevenLabs integration');
                console.log('  • Keyboard shortcuts: Ctrl+V (start/stop), Ctrl+R (read)');
            }}
            
            // Initialize when DOM is ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initializePersonalVoiceControls);
            }} else {{
                initializePersonalVoiceControls();
            }}
        }})();
        '''
        
        return voice_html, voice_css, voice_js
    
    def _handle_js_message(self, handled, message, context):
        """Handle JavaScript messages from voice control cards"""
        if message.startswith("voice_addon:"):
            command = message.replace("voice_addon:", "")
            logger.info(f"Received voice command: {command}")
            
            if command == "get_config":
                return (True, {"success": True})
                
            elif command == "check_status":
                status = self.get_status()
                return (True, status)
        
        return handled
    
    def _on_profile_opened(self):
        """Called when a profile is opened"""
        logger.info("Profile opened - personal voice controls will be automatically injected")
    
    def _setup_menu(self):
        """Set up the Personal Voice Review menu"""
        try:
            # Create Personal Voice Review submenu
            voice_menu = QMenu("Personal Voice Review", mw)
            
            # Status action
            status_action = QAction("Voice Controls Status", mw)
            status_action.setStatusTip("Show your personal voice controls status")
            status_action.triggered.connect(self._show_status)
            voice_menu.addAction(status_action)
            
            voice_menu.addSeparator()
            
            # Configuration action  
            config_action = QAction("Personal Configuration", mw)
            config_action.setStatusTip("View your personal configuration")
            config_action.triggered.connect(self._show_config)
            voice_menu.addAction(config_action)
            
            # Help action
            help_action = QAction("Help", mw)
            help_action.setStatusTip("Show personal voice controls help")
            help_action.triggered.connect(self._show_help)
            voice_menu.addAction(help_action)
            
            # Add to Tools menu
            mw.form.menuTools.addSeparator()
            mw.form.menuTools.addMenu(voice_menu)
            
            logger.info("Personal Voice Review menu added to Tools menu")
            
        except Exception as e:
            logger.error(f"Failed to setup menu: {e}")
    
    def _show_status(self):
        """Show your personal voice controls status"""
        try:
            status = self.get_status()
            personal_status = self.personal_config.get_status_info()
            
            status_text = "🎯 Personal Voice Controls Status:\n\n"
            
            if personal_status['configured']:
                status_text += f"✅ ElevenLabs API Key: {personal_status['message']} ({personal_status['key_suffix']})\n"
            else:
                status_text += "❌ ElevenLabs API Key: Not available\n"
            
            status_text += "✅ Voice Controls: Auto-injected into all cards\n"
            status_text += "✅ AnkiConnect: Required (install code: 2055492159)\n"
            status_text += f"✅ Voice ID: {self.personal_config.get_voice_id()}\n"
            status_text += "✅ Voice Settings: Optimized for quality\n\n"
            
            status_text += "📱 How to Use:\n"
            status_text += "1. Study any card normally\n"
            status_text += "2. Click 'Start Voice' button (auto-appears)\n"
            status_text += "3. Say: 'show answer', 'got it', 'read card'\n"
            status_text += "4. Click 'Stop Voice' when done\n\n"
            
            status_text += "⌨️ Keyboard Shortcuts:\n"
            status_text += "• Ctrl+V: Start/stop voice session\n"
            status_text += "• Ctrl+R: Read current card\n\n"
            
            status_text += "🎯 PRE-CONFIGURED FOR YOU:\n"
            status_text += "This add-on is personally configured with your API key\n"
            status_text += "and optimized settings for immediate use!"
            
            showInfo(status_text, title="Personal Voice Controls Status")
            
        except Exception as e:
            logger.error(f"Error showing status: {e}")
            showInfo(f"Error showing status: {e}")
    
    def _show_config(self):
        """Show your personal configuration"""
        try:
            personal_status = self.personal_config.get_status_info()
            
            config_text = "🎯 Personal Voice Controls Configuration:\n\n"
            
            if personal_status['configured']:
                config_text += f"✅ ElevenLabs API Key: {personal_status['message']} ({personal_status['key_suffix']})\n"
            else:
                config_text += "❌ ElevenLabs API Key: Not available\n"
            
            config_text += f"✅ Voice ID: {self.personal_config.get_voice_id()}\n"
            config_text += f"✅ Voice Settings: Optimized (stability: {self.personal_config.get_voice_settings()['stability']})\n\n"
            
            config_text += "📋 System Requirements:\n"
            config_text += "1. AnkiConnect add-on (Code: 2055492159)\n"
            config_text += "2. That's it! Your API key is pre-configured.\n\n"
            
            config_text += "🎯 Personal Features:\n"
            config_text += "• Pre-configured with your ElevenLabs API key\n"
            config_text += "• Optimized voice settings for quality\n"
            config_text += "• Automatic injection into all cards\n"
            config_text += "• Natural language voice commands\n"
            config_text += "• Session statistics tracking\n"
            config_text += "• Ready to use out of the box\n\n"
            
            config_text += self.personal_config.get_setup_message()
            
            showInfo(config_text, title="Personal Voice Controls Configuration")
            
        except Exception as e:
            logger.error(f"Error showing config: {e}")
            showInfo(f"Error showing configuration: {e}")
    
    def _show_help(self):
        """Show personal voice controls help"""
        try:
            help_text = """🎯 Personal Voice Controls Help

🚀 PRE-CONFIGURED FOR YOU:
Your add-on is ready to use with your personal ElevenLabs API key
and optimized voice settings. No setup required!

📋 REQUIREMENTS:
1. AnkiConnect add-on (Code: 2055492159)
2. That's it! Everything else is pre-configured.

🎯 HOW TO USE:
1. Study any card normally
2. Voice control panel appears automatically
3. Click "Start Voice" button
4. Use voice commands naturally

🎤 VOICE COMMANDS:
Navigation:
• "show answer" - reveal answer
• "next card" - advance to next

Rating (Natural Language):
• "I forgot" / "again" - Rate as Again (1)
• "hard" / "difficult" - Rate as Hard (2)  
• "got it" / "correct" - Rate as Good (3)
• "easy" / "perfect" - Rate as Easy (4)

Audio:
• "read card" - Text-to-speech with your voice
• "repeat" - Read card again
• "help" - Show available commands

⌨️ KEYBOARD SHORTCUTS:
• Ctrl+V - Start/stop voice session
• Ctrl+R - Read current card

🔧 PERSONAL FEATURES:
• Pre-configured with your API key
• Optimized voice settings for quality
• Automatic injection via Anki hooks
• Session statistics tracking
• Professional voice synthesis

🎉 BENEFITS:
• Zero setup required - ready to use
• Works with ALL card types automatically
• High-quality voice synthesis with your settings
• Natural language understanding
• Hands-free studying experience

🎯 This is YOUR personal voice control system!
Ready for immediate hands-free studying! 🚀"""
            
            showInfo(help_text, title="Personal Voice Controls - Help")
            
        except Exception as e:
            logger.error(f"Error showing help: {e}")
            showInfo(f"Error showing help: {e}")
    
    def get_status(self) -> dict:
        """Get your personal add-on status"""
        personal_status = self.personal_config.get_status_info()
        
        return {
            'voice_controls_active': True,  # Always active (auto-injected)
            'api_key_configured': personal_status['configured'],
            'api_key_source': personal_status.get('source', 'none'),
            'voice_id': self.personal_config.get_voice_id(),
            'auto_injection': True,
            'personal_edition': True
        }

# Global personal addon instance
addon_instance: Optional[PersonalVoiceReviewAddon] = None

def get_personal_addon() -> PersonalVoiceReviewAddon:
    """Get your personal addon instance"""
    global addon_instance
    if addon_instance is None:
        addon_instance = PersonalVoiceReviewAddon()
    return addon_instance

# Initialize when module is imported
if ANKI_AVAILABLE:
    addon_instance = get_personal_addon()

# Export for other modules
__all__ = ['PersonalVoiceReviewAddon', 'get_personal_addon', 'ANKI_AVAILABLE'] 
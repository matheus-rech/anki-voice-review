// Voice Review with AnkiConnect + Direct ElevenLabs API
// Ultra-simple: No Python add-on needed, just AnkiConnect + ElevenLabs
console.log('AnkiConnect + ElevenLabs Direct API Voice Controls Loaded');

// Configuration
let config = {
    elevenlabs: {
        apiKey: '', // Set this in the script or via prompt
        voiceId: 'cgSgspJ2msm6clMCkdW9', // Jessica voice
        baseUrl: 'https://api.elevenlabs.io/v1'
    },
    ankiConnect: {
        url: 'http://localhost:8765', // Default AnkiConnect port
        version: 6
    }
};

// Voice session state
let voiceSession = {
    active: false,
    listening: false,
    connected: false,
    currentCard: null,
    stats: { cardsReviewed: 0, startTime: null, correctCount: 0 }
};

// AnkiConnect API class
class AnkiConnectAPI {
    constructor(url = 'http://localhost:8765') {
        this.url = url;
    }
    
    async invoke(action, params = {}) {
        const response = await fetch(this.url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: action,
                version: 6,
                params: params
            })
        });
        
        const result = await response.json();
        if (result.error) {
            throw new Error(result.error);
        }
        return result.result;
    }
    
    // Answer current card
    async answerCard(ease) {
        try {
            await this.invoke('guiAnswerCard', { ease: ease });
            return true;
        } catch (error) {
            console.error('Error answering card:', error);
            return false;
        }
    }
    
    // Get current card info
    async getCurrentCard() {
        try {
            const cardInfo = await this.invoke('guiCurrentCard');
            return cardInfo;
        } catch (error) {
            console.error('Error getting current card:', error);
            return null;
        }
    }
    
    // Show answer
    async showAnswer() {
        try {
            await this.invoke('guiShowAnswer');
            return true;
        } catch (error) {
            console.error('Error showing answer:', error);
            return false;
        }
    }
    
    // Test connection
    async testConnection() {
        try {
            const version = await this.invoke('version');
            return version >= 6;
        } catch (error) {
            console.error('AnkiConnect connection failed:', error);
            return false;
        }
    }
}

// ElevenLabs API class (same as before but simplified)
class ElevenLabsAPI {
    constructor(apiKey, voiceId = 'cgSgspJ2msm6clMCkdW9') {
        this.apiKey = apiKey;
        this.voiceId = voiceId;
        this.baseUrl = 'https://api.elevenlabs.io/v1';
    }
    
    async testConnection() {
        try {
            const response = await fetch(`${this.baseUrl}/user`, {
                headers: { 'xi-api-key': this.apiKey }
            });
            return response.ok;
        } catch (error) {
            console.error('ElevenLabs API test failed:', error);
            return false;
        }
    }
    
    async speak(text) {
        try {
            const response = await fetch(`${this.baseUrl}/text-to-speech/${this.voiceId}`, {
                method: 'POST',
                headers: {
                    'Accept': 'audio/mpeg',
                    'Content-Type': 'application/json',
                    'xi-api-key': this.apiKey
                },
                body: JSON.stringify({
                    text: text.substring(0, 500), // Limit length
                    model_id: 'eleven_monolingual_v1',
                    voice_settings: { stability: 0.5, similarity_boost: 0.5 }
                })
            });
            
            if (!response.ok) throw new Error(`TTS failed: ${response.status}`);
            
            const audioBlob = await response.blob();
            const audio = new Audio(URL.createObjectURL(audioBlob));
            
            return new Promise((resolve) => {
                audio.onended = resolve;
                audio.play();
            });
            
        } catch (error) {
            console.error('Text-to-speech error:', error);
            showFeedback(`TTS Error: ${error.message}`, 'error');
        }
    }
}

// Global instances
let ankiConnect = null;
let elevenLabs = null;

// Voice commands with AnkiConnect
const voiceCommands = {
    // Navigation
    'next card': () => ankiConnect?.showAnswer(),
    'show answer': () => ankiConnect?.showAnswer(),
    'next': () => ankiConnect?.showAnswer(),
    
    // Rating commands  
    'again': () => answerCard(1),
    'hard': () => answerCard(2),
    'good': () => answerCard(3),
    'easy': () => answerCard(4),
    
    // Natural language ratings
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
    
    // Special commands
    'read card': () => readCurrentCard(),
    'repeat': () => readCurrentCard(),
    'help': () => showVoiceHelp()
};

// Answer card using AnkiConnect
async function answerCard(ease) {
    try {
        const success = await ankiConnect.answerCard(ease);
        if (success) {
            voiceSession.stats.cardsReviewed++;
            if (ease >= 3) voiceSession.stats.correctCount++;
            updateSessionStats();
            
            const messages = { 1: "Again", 2: "Hard", 3: "Good", 4: "Easy" };
            showFeedback(`✓ Rated: ${messages[ease]}`, 'success');
            return true;
        }
    } catch (error) {
        console.error('Error answering card:', error);
        showFeedback(`Error rating card: ${error.message}`, 'error');
    }
    return false;
}

// Read current card using AnkiConnect
async function readCurrentCard() {
    try {
        showFeedback('Getting card content...', 'info');
        
        // Get current card from AnkiConnect
        const cardInfo = await ankiConnect.getCurrentCard();
        if (!cardInfo) {
            showFeedback('No card available', 'warning');
            return;
        }
        
        // Extract text content (remove HTML)
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = cardInfo.question || cardInfo.answer || '';
        let text = tempDiv.textContent || tempDiv.innerText || '';
        
        // Clean up text
        text = text.replace(/\s+/g, ' ').trim();
        text = text.replace(/Show Answer|Type in the answer/gi, '');
        
        if (text && elevenLabs) {
            showFeedback('Reading card...', 'info');
            await elevenLabs.speak(text);
        } else {
            showFeedback('No content to read', 'warning');
        }
        
    } catch (error) {
        console.error('Error reading card:', error);
        showFeedback(`Error reading card: ${error.message}`, 'error');
    }
}

// Start voice session with both APIs
async function startVoiceSession() {
    if (voiceSession.active) {
        stopVoiceSession();
        return;
    }
    
    updateVoiceStatus('Connecting...', 'starting');
    showFeedback('Starting voice session...');
    
    try {
        // Get ElevenLabs API key if not set
        if (!config.elevenlabs.apiKey) {
            const apiKey = prompt('Enter your ElevenLabs API key:');
            if (!apiKey) {
                showFeedback('API key required', 'error');
                return;
            }
            config.elevenlabs.apiKey = apiKey;
        }
        
        // Initialize APIs
        ankiConnect = new AnkiConnectAPI(config.ankiConnect.url);
        elevenLabs = new ElevenLabsAPI(config.elevenlabs.apiKey, config.elevenlabs.voiceId);
        
        // Test connections
        showFeedback('Testing AnkiConnect...', 'info');
        const ankiOk = await ankiConnect.testConnection();
        if (!ankiOk) {
            throw new Error('AnkiConnect not available. Make sure AnkiConnect add-on is installed and Anki is running.');
        }
        
        showFeedback('Testing ElevenLabs API...', 'info');
        const elevenLabsOk = await elevenLabs.testConnection();
        if (!elevenLabsOk) {
            throw new Error('ElevenLabs API connection failed. Check your API key.');
        }
        
        // Start voice session
        voiceSession.active = true;
        voiceSession.connected = true;
        voiceSession.stats.startTime = Date.now();
        voiceSession.stats.cardsReviewed = 0;
        voiceSession.stats.correctCount = 0;
        
        // Update UI
        const startBtn = document.getElementById('start-voice-btn');
        const voiceButtons = document.getElementById('voice-buttons');
        
        if (startBtn) {
            startBtn.textContent = 'Stop Voice';
            startBtn.classList.add('active');
        }
        if (voiceButtons) voiceButtons.style.display = 'flex';
        
        // Initialize speech recognition
        initializeSpeechRecognition();
        
        updateVoiceStatus('Voice Active', 'active');
        showFeedback('🎤 Voice controls active! Try "show answer", "got it", or "read card"', 'success');
        
        // Welcome message
        setTimeout(() => {
            elevenLabs.speak("Voice controls activated. You can say show answer, got it, read card, or help for commands.");
        }, 1000);
        
    } catch (error) {
        console.error('Failed to start voice session:', error);
        updateVoiceStatus('Connection Failed', 'error');
        showFeedback(`Failed to start: ${error.message}`, 'error');
    }
}

// Stop voice session
function stopVoiceSession() {
    voiceSession.active = false;
    voiceSession.listening = false;
    voiceSession.connected = false;
    
    // Stop speech recognition
    if (window.voiceRecognition) {
        try {
            window.voiceRecognition.stop();
        } catch (e) {
            console.error('Error stopping recognition:', e);
        }
    }
    
    // Reset APIs
    ankiConnect = null;
    elevenLabs = null;
    
    // Update UI
    const startBtn = document.getElementById('start-voice-btn');
    const voiceButtons = document.getElementById('voice-buttons');
    
    if (startBtn) {
        startBtn.textContent = 'Start Voice';
        startBtn.classList.remove('active');
    }
    if (voiceButtons) voiceButtons.style.display = 'none';
    
    updateVoiceStatus('Voice Inactive', 'inactive');
    updateMicrophoneStatus(false);
    
    // Show session summary
    if (voiceSession.stats.cardsReviewed > 0) {
        const duration = Math.floor((Date.now() - voiceSession.stats.startTime) / 1000);
        const accuracy = Math.round((voiceSession.stats.correctCount / voiceSession.stats.cardsReviewed) * 100);
        showFeedback(`Session complete! ${voiceSession.stats.cardsReviewed} cards in ${duration}s (${accuracy}% accuracy)`, 'success');
    } else {
        showFeedback('Voice session ended');
    }
}

// Speech recognition (same as before)
function initializeSpeechRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showFeedback('Speech recognition not supported', 'warning');
        return;
    }
    
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    window.voiceRecognition = new SpeechRecognitionAPI();
    
    window.voiceRecognition.continuous = true;
    window.voiceRecognition.interimResults = false;
    window.voiceRecognition.lang = 'en-US';
    
    window.voiceRecognition.onstart = () => {
        voiceSession.listening = true;
        updateMicrophoneStatus(true);
    };
    
    window.voiceRecognition.onresult = (event) => {
        const lastResult = event.results[event.results.length - 1];
        if (lastResult.isFinal) {
            const transcript = lastResult[0].transcript.toLowerCase().trim();
            console.log('Voice command:', transcript);
            showFeedback(`Heard: "${transcript}"`);
            handleVoiceCommand(transcript);
        }
    };
    
    window.voiceRecognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        showFeedback(`Speech error: ${event.error}`, 'warning');
    };
    
    window.voiceRecognition.onend = () => {
        voiceSession.listening = false;
        updateMicrophoneStatus(false);
        
        // Restart if session is still active
        if (voiceSession.active) {
            setTimeout(() => {
                try { window.voiceRecognition.start(); } catch (e) {}
            }, 500);
        }
    };
    
    try {
        window.voiceRecognition.start();
    } catch (error) {
        console.error('Failed to start speech recognition:', error);
        showFeedback('Failed to start voice recognition', 'error');
    }
}

// Handle voice commands
async function handleVoiceCommand(transcript) {
    try {
        let processed = false;
        
        // Check for exact and partial matches
        for (const [command, action] of Object.entries(voiceCommands)) {
            if (transcript.includes(command) || command.includes(transcript)) {
                await action();
                showFeedback(`✓ ${command}`, 'success');
                processed = true;
                break;
            }
        }
        
        if (!processed) {
            showFeedback(`Command not recognized: "${transcript}". Try "help" for commands.`, 'warning');
        }
        
    } catch (error) {
        console.error('Error processing voice command:', error);
        showFeedback(`Error: ${error.message}`, 'error');
    }
}

// Show voice help
function showVoiceHelp() {
    const helpText = `Available voice commands:

Navigation: "show answer", "next card"
Rating: "I forgot", "hard", "got it", "easy"  
Audio: "read card", "repeat"
Session: "help"

Natural language works too:
"That was difficult", "Perfect!", "No idea"`;

    showFeedback(helpText, 'info');
    
    if (elevenLabs) {
        elevenLabs.speak("Available commands: show answer, I forgot, got it, easy, read card, and help.");
    }
}

// UI Helper Functions (same as before)
function showFeedback(message, type = 'info') {
    const feedback = document.getElementById('voice-feedback');
    if (!feedback) return;
    
    feedback.textContent = message;
    feedback.className = `voice-feedback ${type}`;
    
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            if (feedback.textContent === message) {
                feedback.textContent = '';
                feedback.className = 'voice-feedback';
            }
        }, 4000);
    }
}

function updateVoiceStatus(status, className) {
    const statusElement = document.getElementById('voice-status');
    if (statusElement) {
        statusElement.textContent = status;
        statusElement.className = `voice-status ${className}`;
    }
}

function updateMicrophoneStatus(listening) {
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {
        micBtn.classList.toggle('listening', listening);
        micBtn.title = listening ? 'Listening...' : 'Click to toggle microphone';
    }
}

function updateSessionStats() {
    const statsElement = document.getElementById('session-stats');
    if (statsElement && voiceSession.stats.startTime) {
        const duration = Math.floor((Date.now() - voiceSession.stats.startTime) / 1000);
        const accuracy = voiceSession.stats.cardsReviewed > 0 
            ? Math.round((voiceSession.stats.correctCount / voiceSession.stats.cardsReviewed) * 100)
            : 0;
        
        statsElement.textContent = `${voiceSession.stats.cardsReviewed} cards, ${duration}s, ${accuracy}% accuracy`;
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey) {
        switch (event.key.toLowerCase()) {
            case 'v':
                event.preventDefault();
                startVoiceSession();
                break;
            case 'm':
                event.preventDefault();
                if (window.voiceRecognition && voiceSession.active) {
                    if (voiceSession.listening) {
                        window.voiceRecognition.stop();
                    } else {
                        window.voiceRecognition.start();
                    }
                }
                break;
            case 'r':
                event.preventDefault();
                if (voiceSession.active) {
                    readCurrentCard();
                }
                break;
        }
    }
});

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('AnkiConnect + ElevenLabs Voice Controls Initialized');
    
    // Add event listeners
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) startBtn.addEventListener('click', startVoiceSession);
    
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {
        micBtn.addEventListener('click', () => {
            if (voiceSession.active && window.voiceRecognition) {
                if (voiceSession.listening) {
                    window.voiceRecognition.stop();
                } else {
                    window.voiceRecognition.start();
                }
            }
        });
    }
    
    updateVoiceStatus('Voice Ready', 'ready');
    showFeedback('Voice controls ready! Install AnkiConnect add-on first, then click "Start Voice".');
    
    console.log('🎤 Ultra-Simple Voice Controls Ready:');
    console.log('  • Requires: AnkiConnect add-on + ElevenLabs API key');
    console.log('  • No Python add-on needed!');
    console.log('  • Pure JavaScript + REST APIs');
});

// Configuration helper
function setElevenLabsApiKey(apiKey) {
    config.elevenlabs.apiKey = apiKey;
    console.log('ElevenLabs API key configured');
} 
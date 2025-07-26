// Direct ElevenLabs API Voice Controls for Anki Cards
// No MCP server needed - direct API integration
console.log('ElevenLabs Direct API Voice Controls Loaded');

// Configuration - will be loaded from Anki add-on config
let elevenLabsConfig = {
    apiKey: '', // Will be loaded from config
    voiceId: 'cgSgspJ2msm6clMCkdW9', // Jessica voice
    agentId: 'agent_5301k0wccfefeaxtkqr0kce7v66a', // Your conversational agent
    baseUrl: 'https://api.elevenlabs.io/v1'
};

// Voice session state (same schema as before)
let voiceSession = {
    active: false,
    listening: false,
    apiConnected: false,
    connecting: false,
    currentCard: null,
    sessionStats: {
        cardsReviewed: 0,
        startTime: null,
        correctCount: 0
    }
};

// Natural language command mappings
const voiceCommands = {
    // Card navigation
    'next card': () => window.pycmd && window.pycmd('ans'),
    'show answer': () => window.pycmd && window.pycmd('ans'),
    'next': () => window.pycmd && window.pycmd('ans'),
    
    // Rating commands
    'again': () => answerCard(1),
    'hard': () => answerCard(2), 
    'good': () => answerCard(3),
    'easy': () => answerCard(4),
    
    // Natural language ratings
    'i forgot': () => answerCard(1),
    'forgot': () => answerCard(1),
    'missed': () => answerCard(1),
    'no': () => answerCard(1),
    'wrong': () => answerCard(1),
    
    'difficult': () => answerCard(2),
    'struggled': () => answerCard(2),
    'almost': () => answerCard(2),
    'close': () => answerCard(2),
    
    'correct': () => answerCard(3),
    'yes': () => answerCard(3),
    'got it': () => answerCard(3),
    'remembered': () => answerCard(3),
    'right': () => answerCard(3),
    
    'perfect': () => answerCard(4),
    'instant': () => answerCard(4),
    'obvious': () => answerCard(4),
    'simple': () => answerCard(4),
    'too easy': () => answerCard(4),
    
    // Special commands
    'read card': () => readCurrentCard(),
    'repeat': () => readCurrentCard(),
    'help': () => showVoiceHelp()
};

// Direct ElevenLabs API Class
class ElevenLabsAPI {
    constructor(config) {
        this.config = config;
        this.conversationId = null;
    }
    
    // Test API connection
    async testConnection() {
        try {
            const response = await fetch(`${this.config.baseUrl}/user`, {
                headers: {
                    'xi-api-key': this.config.apiKey
                }
            });
            return response.ok;
        } catch (error) {
            console.error('ElevenLabs API connection test failed:', error);
            return false;
        }
    }
    
    // Text-to-Speech
    async speak(text) {
        try {
            const response = await fetch(`${this.config.baseUrl}/text-to-speech/${this.config.voiceId}`, {
                method: 'POST',
                headers: {
                    'Accept': 'audio/mpeg',
                    'Content-Type': 'application/json',
                    'xi-api-key': this.config.apiKey
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
            
            if (!response.ok) {
                throw new Error(`TTS API error: ${response.status}`);
            }
            
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            return new Promise((resolve) => {
                audio.onended = resolve;
                audio.play();
            });
            
        } catch (error) {
            console.error('Text-to-speech error:', error);
            showFeedback(`TTS Error: ${error.message}`, 'error');
        }
    }
    
    // Conversational AI (optional enhancement)
    async getAIResponse(userInput, cardContext) {
        try {
            // This would use ElevenLabs conversational AI if available
            // For now, we'll process commands locally
            return this.processLocalCommand(userInput, cardContext);
        } catch (error) {
            console.error('AI response error:', error);
            return null;
        }
    }
    
    // Local command processing (fallback)
    processLocalCommand(input, context) {
        const command = input.toLowerCase().trim();
        
        // Enhanced natural language processing
        for (const [phrase, action] of Object.entries(voiceCommands)) {
            if (command.includes(phrase) || phrase.includes(command)) {
                return {
                    command: phrase,
                    action: action,
                    confidence: this.calculateConfidence(command, phrase)
                };
            }
        }
        
        return null;
    }
    
    calculateConfidence(input, command) {
        // Simple confidence calculation based on word overlap
        const inputWords = input.split(' ');
        const commandWords = command.split(' ');
        const overlap = inputWords.filter(word => commandWords.includes(word)).length;
        return overlap / Math.max(inputWords.length, commandWords.length);
    }
}

// Global API instance
let elevenLabsAPI = null;

// Answer card function
function answerCard(ease) {
    try {
        if (window.pycmd) {
            window.pycmd(`ease${ease}`);
            voiceSession.sessionStats.cardsReviewed++;
            if (ease >= 3) voiceSession.sessionStats.correctCount++;
            updateSessionStats();
            
            // Provide audio feedback
            const feedbackMessages = {
                1: "Again",
                2: "Hard", 
                3: "Good",
                4: "Easy"
            };
            showFeedback(`✓ Rated: ${feedbackMessages[ease]}`, 'success');
            return true;
        }
    } catch (error) {
        console.error('Error answering card:', error);
    }
    return false;
}

// Read current card content aloud
async function readCurrentCard() {
    try {
        // Get card content from the page
        const cardContent = getCardContent();
        if (cardContent && elevenLabsAPI) {
            showFeedback('Reading card...', 'info');
            await elevenLabsAPI.speak(cardContent);
        } else {
            showFeedback('No card content to read', 'warning');
        }
    } catch (error) {
        console.error('Error reading card:', error);
        showFeedback('Error reading card', 'error');
    }
}

// Extract card content for TTS
function getCardContent() {
    // Try to get the main card content
    const cardElement = document.querySelector('.card') || 
                       document.querySelector('#qa') ||
                       document.querySelector('.qa');
                       
    if (cardElement) {
        // Clean up HTML and get text content
        let text = cardElement.textContent || cardElement.innerText || '';
        
        // Clean up the text
        text = text.replace(/\s+/g, ' ').trim();
        
        // Remove common Anki artifacts
        text = text.replace(/Show Answer|Type in the answer|Reveal Answer/gi, '');
        text = text.replace(/^\s*[\d\-\*\•]\s*/, ''); // Remove list markers
        
        return text.length > 500 ? text.substring(0, 500) + '...' : text;
    }
    
    return null;
}

// Show available voice commands
function showVoiceHelp() {
    const helpText = `Available voice commands:
    
Navigation: "next card", "show answer"
Rating: "I forgot", "hard", "got it", "easy"  
Audio: "read card", "repeat"
Session: "help"

You can also use natural language like:
"That was difficult", "Perfect!", "No idea", etc.`;

    showFeedback(helpText, 'info');
    
    // Also speak the help if TTS is available
    if (elevenLabsAPI) {
        elevenLabsAPI.speak("Available commands: next card, show answer, I forgot, hard, got it, easy, read card, and help.");
    }
}

// Check API connection (replaces MCP server check)
async function checkAPIConnection() {
    if (!elevenLabsAPI || !elevenLabsConfig.apiKey) {
        return false;
    }
    
    try {
        return await elevenLabsAPI.testConnection();
    } catch (error) {
        console.error('API connection check failed:', error);
        return false;
    }
}

// Start API connection (replaces MCP server startup)
async function startAPIConnection() {
    if (voiceSession.connecting || voiceSession.apiConnected) {
        return voiceSession.apiConnected;
    }
    
    voiceSession.connecting = true;
    updateVoiceStatus('Connecting to ElevenLabs...', 'starting');
    showFeedback('Connecting to ElevenLabs API...');
    
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) startBtn.disabled = true;

    try {
        // Load configuration from Anki add-on
        await loadElevenLabsConfig();
        
        // Initialize API
        elevenLabsAPI = new ElevenLabsAPI(elevenLabsConfig);
        
        // Test connection
        const connected = await elevenLabsAPI.testConnection();
        
        if (connected) {
            voiceSession.apiConnected = true;
            updateVoiceStatus('ElevenLabs Connected', 'connected');
            showFeedback('Connected to ElevenLabs API!', 'success');
            return true;
        } else {
            throw new Error('API connection test failed');
        }
        
    } catch (error) {
        console.error('Error connecting to ElevenLabs API:', error);
        updateVoiceStatus('Connection Failed', 'error');
        showFeedback(`Connection failed: ${error.message}. Check your API key.`, 'error');
        return false;
        
    } finally {
        voiceSession.connecting = false;
        if (startBtn) startBtn.disabled = false;
    }
}

// Load configuration from Anki add-on
async function loadElevenLabsConfig() {
    try {
        // Try to get config from Anki add-on via pycmd
        if (typeof window.pycmd !== 'undefined') {
            // This will be handled by the Python add-on
            window.pycmd('voice_addon:get_config');
            
            // Wait for config to be loaded (will be set by Python callback)
            let retries = 0;
            while (!elevenLabsConfig.apiKey && retries < 10) {
                await new Promise(resolve => setTimeout(resolve, 200));
                retries++;
            }
        }
        
        // If no API key is configured, show setup message
        if (!elevenLabsConfig.apiKey) {
            throw new Error('ElevenLabs API key not configured. Please set it in the add-on configuration.');
        }
        
    } catch (error) {
        // For testing purposes, allow manual configuration
        console.warn('Could not load config from add-on:', error);
        
        // Show configuration prompt
        const apiKey = prompt('Enter your ElevenLabs API key (for testing):');
        if (apiKey) {
            elevenLabsConfig.apiKey = apiKey;
        } else {
            throw new Error('API key is required');
        }
    }
}

// Set config from Python add-on (called by Python)
function setElevenLabsConfig(config) {
    elevenLabsConfig = { ...elevenLabsConfig, ...config };
    console.log('ElevenLabs configuration updated');
}

// Start voice session (same interface as before)
async function startVoiceSession() {
    if (voiceSession.active) {
        stopVoiceSession();
        return;
    }
    
    updateVoiceStatus('Initializing...', 'starting');
    showFeedback('Starting voice session...');
    
    // Start API connection (replaces MCP server startup)
    const connected = await startAPIConnection();
    
    if (!connected) {
        updateVoiceStatus('Connection Failed', 'error');
        return;
    }
    
    // Start voice session
    voiceSession.active = true;
    voiceSession.sessionStats.startTime = Date.now();
    voiceSession.sessionStats.cardsReviewed = 0;
    voiceSession.sessionStats.correctCount = 0;
    
    // Show controls
    const voiceButtons = document.getElementById('voice-buttons');
    const startBtn = document.getElementById('start-voice-btn');
    
    if (voiceButtons) voiceButtons.style.display = 'flex';
    if (startBtn) {
        startBtn.textContent = 'Stop Voice';
        startBtn.classList.add('active');
    }
    
    // Initialize speech recognition
    initializeSpeechRecognition();
    
    updateVoiceStatus('Voice Active', 'active');
    showFeedback('Voice controls active! Try "next card", "read card", or "I forgot"', 'success');
    
    // Welcome message with TTS
    if (elevenLabsAPI) {
        setTimeout(() => {
            elevenLabsAPI.speak("Voice controls activated. You can say next card, read card, or rate cards by saying I forgot, got it, or too easy.");
        }, 1000);
    }
}

// Stop voice session
function stopVoiceSession() {
    voiceSession.active = false;
    voiceSession.listening = false;
    voiceSession.apiConnected = false;
    
    // Stop speech recognition
    if (window.voiceRecognition) {
        try {
            window.voiceRecognition.stop();
        } catch (e) {
            console.error('Error stopping recognition:', e);
        }
    }
    
    // Reset API
    elevenLabsAPI = null;
    
    // Update UI
    const voiceButtons = document.getElementById('voice-buttons');
    const startBtn = document.getElementById('start-voice-btn');
    
    if (voiceButtons) voiceButtons.style.display = 'none';
    if (startBtn) {
        startBtn.textContent = 'Start Voice';
        startBtn.classList.remove('active');
    }
    
    updateVoiceStatus('Voice Inactive', 'inactive');
    updateMicrophoneStatus(false);
    
    // Show session summary
    if (voiceSession.sessionStats.cardsReviewed > 0) {
        const duration = Math.floor((Date.now() - voiceSession.sessionStats.startTime) / 1000);
        const accuracy = Math.round((voiceSession.sessionStats.correctCount / voiceSession.sessionStats.cardsReviewed) * 100);
        showFeedback(`Session complete! ${voiceSession.sessionStats.cardsReviewed} cards in ${duration}s (${accuracy}% accuracy)`, 'success');
    } else {
        showFeedback('Voice session ended');
    }
}

// Enhanced speech recognition
function initializeSpeechRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showFeedback('Speech recognition not supported in this browser', 'warning');
        return;
    }
    
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    window.voiceRecognition = new SpeechRecognitionAPI();
    
    // Configuration
    window.voiceRecognition.continuous = true;
    window.voiceRecognition.interimResults = false;
    window.voiceRecognition.lang = 'en-US';
    window.voiceRecognition.maxAlternatives = 3;
    
    // Event handlers
    window.voiceRecognition.onstart = function() {
        console.log('Speech recognition started');
        voiceSession.listening = true;
        updateMicrophoneStatus(true);
    };
    
    window.voiceRecognition.onresult = function(event) {
        const lastResult = event.results[event.results.length - 1];
        if (lastResult.isFinal) {
            const transcript = lastResult[0].transcript.toLowerCase().trim();
            console.log('Voice command received:', transcript);
            
            showFeedback(`Heard: "${transcript}"`);
            handleVoiceCommand(transcript);
        }
    };
    
    window.voiceRecognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        handleSpeechError(event.error);
    };
    
    window.voiceRecognition.onend = function() {
        console.log('Speech recognition ended');
        voiceSession.listening = false;
        updateMicrophoneStatus(false);
        
        // Restart if session is still active
        if (voiceSession.active) {
            setTimeout(() => {
                try {
                    window.voiceRecognition.start();
                } catch (e) {
                    console.error('Failed to restart recognition:', e);
                }
            }, 500);
        }
    };
    
    // Start recognition
    try {
        window.voiceRecognition.start();
    } catch (error) {
        console.error('Failed to start speech recognition:', error);
        showFeedback('Failed to start voice recognition', 'error');
    }
}

// Handle voice commands with AI enhancement
async function handleVoiceCommand(transcript) {
    try {
        // First try local command processing
        let processed = false;
        
        // Check for exact matches
        if (voiceCommands[transcript]) {
            voiceCommands[transcript]();
            showFeedback(`✓ ${transcript}`, 'success');
            processed = true;
        } else {
            // Check for partial matches
            for (const [command, action] of Object.entries(voiceCommands)) {
                if (transcript.includes(command) || command.includes(transcript)) {
                    action();
                    showFeedback(`✓ ${command}`, 'success');
                    processed = true;
                    break;
                }
            }
        }
        
        // If not processed locally and AI is available, try AI processing
        if (!processed && elevenLabsAPI) {
            const cardContext = getCardContent();
            const aiResponse = await elevenLabsAPI.getAIResponse(transcript, cardContext);
            
            if (aiResponse && aiResponse.action) {
                aiResponse.action();
                showFeedback(`✓ ${aiResponse.command} (AI: ${Math.round(aiResponse.confidence * 100)}%)`, 'success');
                processed = true;
            }
        }
        
        // If still not processed
        if (!processed) {
            showFeedback(`Command not recognized: "${transcript}". Try "help" for available commands.`, 'warning');
            
            // Provide audio feedback
            if (elevenLabsAPI) {
                elevenLabsAPI.speak("Command not recognized. Say help for available commands.");
            }
        }
        
    } catch (error) {
        console.error('Error processing voice command:', error);
        showFeedback(`Error processing command: ${error.message}`, 'error');
    }
}

// Handle speech recognition errors
function handleSpeechError(error) {
    const errorMessages = {
        'no-speech': 'No speech detected. Try speaking louder.',
        'network': 'Network error. Check your internet connection.',
        'not-allowed': 'Microphone access denied. Please allow microphone access.',
        'service-not-allowed': 'Speech service not allowed. Check browser permissions.',
        'bad-grammar': 'Speech not recognized. Try rephrasing.',
        'language-not-supported': 'Language not supported.'
    };
    
    const message = errorMessages[error] || `Speech error: ${error}`;
    showFeedback(message, 'warning');
    
    // Try to restart recognition after error
    setTimeout(() => {
        if (voiceSession.active && !voiceSession.listening) {
            try {
                window.voiceRecognition.start();
            } catch (e) {
                console.error('Failed to restart recognition after error:', e);
            }
        }
    }, 1000);
}

// UI Helper Functions (same as before)
function showFeedback(message, type = 'info') {
    const feedback = document.getElementById('voice-feedback');
    if (!feedback) return;
    
    feedback.textContent = message;
    feedback.className = `voice-feedback ${type}`;
    
    // Auto-hide success and info messages
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
    if (statsElement && voiceSession.sessionStats.startTime) {
        const duration = Math.floor((Date.now() - voiceSession.sessionStats.startTime) / 1000);
        const accuracy = voiceSession.sessionStats.cardsReviewed > 0 
            ? Math.round((voiceSession.sessionStats.correctCount / voiceSession.sessionStats.cardsReviewed) * 100)
            : 0;
        
        statsElement.textContent = `${voiceSession.sessionStats.cardsReviewed} cards, ${duration}s, ${accuracy}% accuracy`;
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
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
document.addEventListener('DOMContentLoaded', function() {
    console.log('ElevenLabs Direct API Voice Controls Initialized');
    
    // Add event listeners
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) {
        startBtn.addEventListener('click', startVoiceSession);
    }
    
    const micBtn = document.getElementById('mic-btn');
    if (micBtn) {
        micBtn.addEventListener('click', function() {
            if (voiceSession.active && window.voiceRecognition) {
                if (voiceSession.listening) {
                    window.voiceRecognition.stop();
                } else {
                    window.voiceRecognition.start();
                }
            }
        });
    }
    
    // Show initial status
    updateVoiceStatus('Voice Ready', 'ready');
    showFeedback('Voice controls ready! Click "Start Voice" to connect to ElevenLabs API.');
    
    console.log('🎤 Voice Controls Ready:');
    console.log('  • Click "Start Voice" to connect to ElevenLabs API');
    console.log('  • Say "help" for available commands');
    console.log('  • Keyboard shortcuts: Ctrl+V (start/stop), Ctrl+M (mic), Ctrl+R (read card)');
}); 
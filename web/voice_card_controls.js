// Enhanced Voice Control for Anki Cards
// Works with or without MCP server
console.log('Voice card controls loaded');

// Global voice session state
let voiceSession = {
    active: false,
    listening: false,
    mcpConnected: false,
    serverStarting: false,
    currentCard: null,
    sessionStats: {
        cardsReviewed: 0,
        startTime: null,
        correctCount: 0
    },
    fallbackMode: false // New: tracks if we're in fallback mode
};

// Natural language mappings for voice commands
const voiceCommands = {
    // Card navigation
    'next card': () => window.pycmd && window.pycmd('ans'),
    'show answer': () => window.pycmd && window.pycmd('ans'),
    'next': () => window.pycmd && window.pycmd('ans'),
    
    // Rating commands (fallback to basic Anki commands)
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
    'too easy': () => answerCard(4)
};

// Answer card function that works with basic Anki
function answerCard(ease) {
    try {
        if (window.pycmd) {
            window.pycmd(`ease${ease}`);
            voiceSession.sessionStats.cardsReviewed++;
            if (ease >= 3) voiceSession.sessionStats.correctCount++;
            updateSessionStats();
            return true;
        }
    } catch (error) {
        console.error('Error answering card:', error);
    }
    return false;
}

// Check if MCP server is available (enhanced with fallback)
async function checkMCPConnection() {
    try {
        const response = await fetch('http://localhost:8000/health', {
            method: 'GET',
            timeout: 2000
        });
        return response.ok;
    } catch (error) {
        console.log('MCP server not available, using fallback mode');
        return false;
    }
}

// Start MCP server with better error handling
async function startMCPServer() {
    if (voiceSession.serverStarting || voiceSession.mcpConnected) {
        return voiceSession.mcpConnected;
    }
    
    voiceSession.serverStarting = true;
    updateVoiceStatus('Starting MCP Server...', 'starting');
    showFeedback('Starting MCP server, please wait...');
    
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) startBtn.disabled = true;

    try {
        // Try to start via Anki's Python command interface
        if (typeof window.pycmd !== 'undefined') {
            window.pycmd('voice_addon:start_mcp_server');
            
            // Wait for server to start with timeout
            let retries = 0;
            const maxRetries = 10; // Reduced from 30 to fail faster
            
            while (retries < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 500));
                const connected = await checkMCPConnection();
                if (connected) {
                    voiceSession.mcpConnected = true;
                    voiceSession.fallbackMode = false;
                    updateVoiceStatus('MCP Connected', 'connected');
                    showFeedback('MCP server started successfully!');
                    return true;
                }
                retries++;
            }
            
            // If we get here, MCP didn't start but that's ok
            console.log('MCP server timeout, switching to fallback mode');
            voiceSession.fallbackMode = true;
            updateVoiceStatus('Basic Mode', 'fallback');
            showFeedback('Using basic voice controls (MCP server unavailable)');
            return true; // Return true so voice controls still work
        }
        
    } catch (error) {
        console.error('Error starting MCP server:', error);
        voiceSession.fallbackMode = true;
        updateVoiceStatus('Basic Mode', 'fallback');
        showFeedback('Using basic voice controls');
        return true; // Return true for fallback mode
        
    } finally {
        voiceSession.serverStarting = false;
        if (startBtn) startBtn.disabled = false;
    }
}

// Enhanced voice session start
async function startVoiceSession() {
    if (voiceSession.active) {
        stopVoiceSession();
        return;
    }
    
    updateVoiceStatus('Initializing...', 'starting');
    showFeedback('Initializing voice controls...');
    
    // Always try to start/connect MCP, but don't fail if it doesn't work
    await startMCPServer();
    
    // Start voice session regardless of MCP status
    voiceSession.active = true;
    voiceSession.sessionStats.startTime = Date.now();
    voiceSession.sessionStats.cardsReviewed = 0;
    voiceSession.sessionStats.correctCount = 0;
    
    // Show appropriate controls
    const voiceButtons = document.getElementById('voice-buttons');
    const startBtn = document.getElementById('start-voice-btn');
    
    if (voiceButtons) voiceButtons.style.display = 'flex';
    if (startBtn) {
        startBtn.textContent = 'Stop Voice';
        startBtn.classList.add('active');
    }
    
    // Initialize speech recognition
    initializeSpeechRecognition();
    
    // Update status based on mode
    if (voiceSession.fallbackMode) {
        updateVoiceStatus('Voice Active (Basic)', 'active-fallback');
        showFeedback('Voice controls active! Say "next card", "I forgot", "got it", etc.');
    } else {
        updateVoiceStatus('Voice Active (AI)', 'active');
        showFeedback('Voice controls with AI active! Try natural language commands.');
    }
}

// Enhanced speech recognition with better error handling
function initializeSpeechRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showFeedback('Speech recognition not supported in this browser');
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
            
            // Show what was heard
            showFeedback(`Heard: "${transcript}"`);
            
            // Process the command
            handleVoiceCommand(transcript);
        }
    };
    
    window.voiceRecognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        
        // Handle different error types
        switch (event.error) {
            case 'no-speech':
                showFeedback('No speech detected. Try speaking louder.');
                break;
            case 'network':
                showFeedback('Network error. Check your internet connection.');
                break;
            case 'not-allowed':
                showFeedback('Microphone access denied. Please allow microphone access.');
                break;
            default:
                showFeedback(`Speech error: ${event.error}`);
        }
        
        // Try to restart recognition after a short delay
        setTimeout(() => {
            if (voiceSession.active && !voiceSession.listening) {
                try {
                    window.voiceRecognition.start();
                } catch (e) {
                    console.error('Failed to restart recognition:', e);
                }
            }
        }, 1000);
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
                    showFeedback('Voice recognition stopped. Click microphone to restart.');
                }
            }, 500);
        }
    };
    
    // Start recognition
    try {
        window.voiceRecognition.start();
    } catch (error) {
        console.error('Failed to start speech recognition:', error);
        showFeedback('Failed to start voice recognition. Try again.');
    }
}

// Enhanced command handling
function handleVoiceCommand(transcript) {
    // Check for exact matches first
    if (voiceCommands[transcript]) {
        try {
            voiceCommands[transcript]();
            showFeedback(`✓ ${transcript}`, 'success');
            return;
        } catch (error) {
            console.error('Error executing command:', error);
        }
    }
    
    // Check for partial matches
    for (const [command, action] of Object.entries(voiceCommands)) {
        if (transcript.includes(command) || command.includes(transcript)) {
            try {
                action();
                showFeedback(`✓ ${command}`, 'success');
                return;
            } catch (error) {
                console.error('Error executing command:', error);
            }
        }
    }
    
    // If no match found
    showFeedback(`Command not recognized: "${transcript}"`);
    console.log('Available commands:', Object.keys(voiceCommands));
}

// Enhanced feedback system
function showFeedback(message, type = 'info') {
    const feedback = document.getElementById('voice-feedback');
    if (!feedback) return;
    
    feedback.textContent = message;
    feedback.className = `voice-feedback ${type}`;
    
    // Auto-hide success messages, keep errors visible
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            if (feedback.textContent === message) {
                feedback.textContent = '';
                feedback.className = 'voice-feedback';
            }
        }, 3000);
    }
}

// Enhanced status updates
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

// Enhanced session stop
function stopVoiceSession() {
    voiceSession.active = false;
    voiceSession.listening = false;
    
    // Stop speech recognition
    if (window.voiceRecognition) {
        try {
            window.voiceRecognition.stop();
        } catch (e) {
            console.error('Error stopping recognition:', e);
        }
    }
    
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
        }
    }
});

// Auto-initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Voice controls initialized - Basic mode available, MCP optional');
    
    // Check if voice panel exists and add event listeners
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
    showFeedback('Voice controls ready! Click "Start Voice" to begin.');
}); 
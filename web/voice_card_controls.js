// Voice Control JavaScript for Anki Cards
// This file contains the enhanced voice control system with automatic MCP server startup

let voiceSession = {
    active: false,
    listening: false,
    mcpConnected: false,
    serverStarting: false,
    currentCard: null,
    sessionStats: {
        cardsReviewed: 0,
        correctAnswers: 0,
        startTime: null
    }
};

// Initialize voice controls when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeVoiceControls();
    checkMCPConnection();
});

function initializeVoiceControls() {
    console.log('🎤 Voice Control System Loaded');
    updateVoiceStatus('Voice Ready', 'ready');
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'v' && e.ctrlKey) {
            e.preventDefault();
            toggleVoiceSession();
        }
        if (e.key === 'n' && e.ctrlKey && voiceSession.active) {
            e.preventDefault();
            nextCard();
        }
        if (e.key === 's' && e.ctrlKey && voiceSession.active) {
            e.preventDefault();
            showAnswer();
        }
    });
    
    // Add minimize/maximize functionality
    let panel = document.getElementById('voice-controls');
    if (panel) {
        panel.addEventListener('dblclick', function() {
            toggleMinimizePanel();
        });
    }
    
    // Show available commands
    console.log('📋 Available Commands:');
    console.log('   • Navigation: "next card", "show answer"');
    console.log('   • Rating: "I forgot" (1), "hard" (2), "got it" (3), "easy" (4)');
    console.log('   • Session: "start", "stop"');
    console.log('⌨️  Keyboard Shortcuts:');
    console.log('   • Ctrl+V: Toggle voice session');
    console.log('   • Ctrl+N: Next card');
    console.log('   • Ctrl+S: Show answer');
    console.log('   • Double-click panel: Minimize/maximize');
}

async function checkMCPConnection() {
    try {
        const response = await fetch('http://localhost:8000/health', {
            method: 'GET',
            timeout: 2000
        });
        
        if (response.ok) {
            voiceSession.mcpConnected = true;
            updateVoiceStatus('MCP Connected', 'connected');
            return true;
        } else {
            throw new Error('MCP server not responding');
        }
    } catch (error) {
        console.log('MCP server not available:', error);
        voiceSession.mcpConnected = false;
        return false;
    }
}

async function startMCPServer() {
    if (voiceSession.serverStarting) {
        return false;
    }

    voiceSession.serverStarting = true;
    updateVoiceStatus('Starting MCP Server...', 'starting');
    showFeedback('Starting MCP server, please wait...');
    
    // Disable start button during startup
    const startBtn = document.getElementById('start-voice-btn');
    if (startBtn) startBtn.disabled = true;

    try {
        // Try to call the Anki addon's MCP server start function
        if (typeof window.pycmd !== 'undefined') {
            // Anki's Python command interface
            window.pycmd('voice_addon:start_mcp_server');
            
            // Wait for server to start
            let retries = 0;
            const maxRetries = 30; // 15 seconds max
            
            while (retries < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 500));
                
                if (await checkMCPConnection()) {
                    voiceSession.mcpConnected = true;
                    voiceSession.serverStarting = false;
                    updateVoiceStatus('MCP Connected', 'connected');
                    showFeedback('MCP server started successfully!');
                    
                    if (startBtn) startBtn.disabled = false;
                    return true;
                }
                retries++;
            }
            
            throw new Error('Server startup timeout');
            
        } else {
            // Fallback: try to start via direct API call
            const response = await fetch('http://localhost:8000/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'start_server' })
            });
            
            if (response.ok) {
                voiceSession.mcpConnected = true;
                voiceSession.serverStarting = false;
                updateVoiceStatus('MCP Connected', 'connected');
                showFeedback('MCP server started successfully!');
                
                if (startBtn) startBtn.disabled = false;
                return true;
            } else {
                throw new Error('Failed to start server via API');
            }
        }
        
    } catch (error) {
        console.error('Error starting MCP server:', error);
        voiceSession.serverStarting = false;
        updateVoiceStatus('Server Start Failed', 'disconnected');
        showFeedback('Failed to start MCP server. Please start manually: Tools → Voice Review → Start MCP Server');
        
        if (startBtn) startBtn.disabled = false;
        return false;
    }
}

async function startVoiceSession() {
    // First check if MCP server is connected
    if (!voiceSession.mcpConnected) {
        updateVoiceStatus('Connecting...', 'processing');
        showFeedback('Checking MCP server connection...');
        
        // Try to connect first
        const connected = await checkMCPConnection();
        
        if (!connected) {
            // If not connected, try to start the server automatically
            showFeedback('MCP server not running. Starting automatically...');
            const started = await startMCPServer();
            
            if (!started) {
                // If auto-start failed, show instructions
                updateVoiceStatus('Start Required', 'disconnected');
                showFeedback('Please start MCP server manually: Tools → Voice Review → Start MCP Server');
                return;
            }
        }
    }
    
    // At this point, MCP server should be connected
    voiceSession.active = true;
    voiceSession.sessionStats.startTime = new Date();
    
    updateVoiceStatus('Voice Active', 'recording');
    showVoiceButtons(true);
    showFeedback('Voice session started! Say "next card" or click the button to begin.');
    
    // Initialize speech recognition if available
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        initializeSpeechRecognition();
    } else {
        showFeedback('Speech recognition not supported in this browser. Use Chrome/Edge for best experience.');
    }
    
    console.log('Voice session started');
}

function stopVoiceSession() {
    voiceSession.active = false;
    voiceSession.listening = false;
    
    updateVoiceStatus('Voice Ready', 'ready');
    showVoiceButtons(false);
    showFeedback('Voice session ended.');
    
    // Stop speech recognition
    if (window.voiceRecognition) {
        window.voiceRecognition.stop();
    }
    
    // Show session summary
    if (voiceSession.sessionStats.cardsReviewed > 0) {
        const duration = Math.round((new Date() - voiceSession.sessionStats.startTime) / 1000);
        const accuracy = Math.round((voiceSession.sessionStats.correctAnswers / voiceSession.sessionStats.cardsReviewed) * 100);
        showFeedback(`Session complete! ${voiceSession.sessionStats.cardsReviewed} cards in ${duration}s (${accuracy}% accuracy)`);
    }
    
    console.log('Voice session stopped');
}

function toggleVoiceSession() {
    if (voiceSession.active) {
        stopVoiceSession();
    } else {
        startVoiceSession();
    }
}

function processVoiceCommand(command) {
    console.log('Voice command:', command);
    showFeedback(`Heard: "${command}"`);
    
    // Enhanced natural language processing
    const easeMap = {
        'again': 'again', 'hard': 'hard', 'good': 'good', 'easy': 'easy',
        'repeat': 'again', 'forgot': 'again', 'missed': 'again', 'no': 'again',
        'totally forgot': 'again', 'completely forgot': 'again', 'no idea': 'again',
        'blank': 'again', 'drawing a blank': 'again', 'clueless': 'again',
        'difficult': 'hard', 'struggled': 'hard', 'almost': 'hard',
        'pretty hard': 'hard', 'took a while': 'hard', 'challenging': 'hard',
        'eventually got it': 'hard', 'figured it out': 'hard',
        'correct': 'good', 'yes': 'good', 'got it': 'good', 'remembered': 'good',
        'knew that': 'good', 'right answer': 'good', 'of course': 'good',
        'recognized it': 'good', 'came to me': 'good',
        'perfect': 'easy', 'instant': 'easy', 'obvious': 'easy', 'simple': 'easy',
        'immediately': 'easy', 'too simple': 'easy', 'way too easy': 'easy',
        'piece of cake': 'easy', 'no problem': 'easy', 'super obvious': 'easy'
    };
    
    // Check for rating commands first (most specific)
    for (const [phrase, rating] of Object.entries(easeMap)) {
        if (command.includes(phrase)) {
            rateCard(rating);
            return;
        }
    }
    
    // Check for navigation commands
    if (command.includes('next card') || command.includes('continue') || command.includes('next')) {
        nextCard();
    } else if (command.includes('show answer') || command.includes('reveal') || command.includes('answer')) {
        showAnswer();
    } else if (command.includes('stop') || command.includes('end session')) {
        stopVoiceSession();
    } else if (command.includes('start') || command.includes('begin')) {
        if (!voiceSession.active) startVoiceSession();
    } else {
        showFeedback(`Unrecognized command: "${command}". Try: next card, show answer, I forgot, too easy`);
    }
}

// Helper functions that need to be implemented based on the specific Anki interface
function nextCard() {
    console.log('Next card requested');
    // Implementation depends on Anki interface
}

function showAnswer() {
    console.log('Show answer requested');
    // Implementation depends on Anki interface
}

function rateCard(difficulty) {
    console.log(`Card rated: ${difficulty}`);
    // Implementation depends on Anki interface
}

function updateVoiceStatus(text, status) {
    const statusText = document.getElementById('status-text');
    const statusIndicator = document.getElementById('status-indicator');
    if (statusText) statusText.textContent = text;
    if (statusIndicator) statusIndicator.className = `status-indicator ${status}`;
}

function showVoiceButtons(show) {
    const startBtn = document.getElementById('start-voice-btn');
    const stopBtn = document.getElementById('stop-voice-btn');
    const nextBtn = document.getElementById('next-card-btn');
    const answerBtn = document.getElementById('show-answer-btn');
    
    if (startBtn) startBtn.style.display = show ? 'none' : 'flex';
    if (stopBtn) stopBtn.style.display = show ? 'flex' : 'none';
    if (nextBtn) nextBtn.style.display = show ? 'flex' : 'none';
    if (answerBtn) answerBtn.style.display = show ? 'flex' : 'none';
}

function showFeedback(message) {
    const feedback = document.getElementById('voice-feedback');
    const feedbackText = document.getElementById('feedback-text');
    
    if (feedback && feedbackText) {
        feedbackText.textContent = message;
        feedback.style.display = 'block';
        
        // Auto-hide after 3 seconds unless it's an error or important message
        if (!message.includes('Error') && !message.includes('Failed') && !message.includes('Please')) {
            setTimeout(() => {
                feedback.style.display = 'none';
            }, 3000);
        }
    }
    
    console.log('Voice Feedback:', message);
}

function initializeSpeechRecognition() {
    // Speech recognition implementation
    console.log('Speech recognition initialized');
}

function toggleMinimizePanel() {
    const panel = document.getElementById('voice-controls');
    if (panel) {
        panel.classList.toggle('minimized');
    }
} 
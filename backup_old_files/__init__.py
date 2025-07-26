# voice_review_addon/__init__.py
"""
Anki Voice Review Add-on with ElevenLabs Conversational AI
Enables hands-free flashcard review using AI voice assistant
"""

from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.qt import QWebChannel, pyqtSlot
from aqt.utils import showInfo, showWarning
from aqt.reviewer import Reviewer
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import threading
import json
import logging
import os
import sqlite3
import requests
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import html2text
import re
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import websockets
import base64
import time
from concurrent.futures import ThreadPoolExecutor

# Configure logging
log_file = os.path.join(mw.addonManager.addonsFolder(__name__), 'voice_review.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ElevenLabs Agent Configuration
ELEVENLABS_AGENT_ID = "agent_5301k0wccfefeaxtkqr0kce7v66a"

class ReviewMode(Enum):
    """Different review modes available"""
    NORMAL = "normal"
    SPEED = "speed"  # Shorter time limits
    FOCUS = "focus"  # No hints, stricter ratings
    PRACTICE = "practice"  # No scheduling updates

class SessionState(Enum):
    """Review session states"""
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"

class VoiceStreamHandler:
    """Handle real-time voice streaming with ElevenLabs WebSocket API"""
    
    def __init__(self, agent_id: str, api_key: str):
        self.agent_id = agent_id
        self.api_key = api_key
        self.websocket_url = f"wss://api.elevenlabs.io/v1/convai/conversation"
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.connection_lock = asyncio.Lock()
        self.message_queue = asyncio.Queue()
        self.response_callbacks = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def connect(self):
        """Establish WebSocket connection with retry logic"""
        if self.connected and self.ws and not self.ws.closed:
            return True
            
        async with self.connection_lock:
            try:
                headers = {
                    "xi-agent-id": self.agent_id,
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json"
                }
                
                self.ws = await websockets.connect(
                    self.websocket_url,
                    extra_headers=headers,
                    ping_interval=30,
                    ping_timeout=10
                )
                
                self.connected = True
                self.reconnect_attempts = 0
                logger.info(f"WebSocket connected to ElevenLabs ConvAI")
                
                # Start listening for messages
                asyncio.create_task(self._message_listener())
                
                return True
                
            except Exception as e:
                logger.error(f"WebSocket connection failed: {e}")
                self.connected = False
                return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        if self.ws and not self.ws.closed:
            await self.ws.close()
        self.connected = False
        logger.info("WebSocket disconnected")
    
    async def _message_listener(self):
        """Listen for incoming WebSocket messages"""
        try:
            async for message in self.ws:
                await self._handle_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
            await self._handle_reconnection()
        except Exception as e:
            logger.error(f"Message listener error: {e}")
    
    async def _handle_message(self, message: dict):
        """Process incoming WebSocket messages"""
        message_type = message.get("type", "")
        
        if message_type == "audio":
            # Handle audio response from ElevenLabs
            audio_data = base64.b64decode(message.get("audio", ""))
            await self._process_audio_response(audio_data)
            
        elif message_type == "transcript":
            # Handle transcript from user speech
            transcript = message.get("text", "")
            confidence = message.get("confidence", 0.0)
            await self._process_transcript(transcript, confidence)
            
        elif message_type == "conversation_event":
            # Handle conversation state changes
            event_type = message.get("event", "")
            await self._process_conversation_event(event_type, message)
            
        elif message_type == "error":
            # Handle errors
            error_msg = message.get("message", "Unknown error")
            logger.error(f"ElevenLabs WebSocket error: {error_msg}")
    
    async def _handle_reconnection(self):
        """Handle automatic reconnection with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return
            
        self.reconnect_attempts += 1
        backoff_time = min(30, 2 ** self.reconnect_attempts)
        
        logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} in {backoff_time}s")
        await asyncio.sleep(backoff_time)
        
        if await self.connect():
            logger.info("WebSocket reconnected successfully")
        else:
            await self._handle_reconnection()
    
    async def stream_audio(self, audio_data: bytes, format: str = "pcm"):
        """Stream audio to ElevenLabs with error handling"""
        if not self.connected:
            if not await self.connect():
                raise ConnectionError("Failed to establish WebSocket connection")
        
        try:
            message = {
                "type": "audio",
                "audio": base64.b64encode(audio_data).decode(),
                "format": format,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.ws.send(json.dumps(message))
            logger.debug(f"Sent audio chunk: {len(audio_data)} bytes")
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed during audio streaming")
            self.connected = False
            await self._handle_reconnection()
            raise
        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
            raise
    
    async def send_text(self, text: str, context: dict = None):
        """Send text message to ElevenLabs"""
        if not self.connected:
            if not await self.connect():
                raise ConnectionError("Failed to establish WebSocket connection")
        
        try:
            message = {
                "type": "text",
                "text": text,
                "timestamp": int(time.time() * 1000)
            }
            
            if context:
                message["context"] = context
                
            await self.ws.send(json.dumps(message))
            logger.debug(f"Sent text message: {text[:100]}...")
            
        except Exception as e:
            logger.error(f"Text sending error: {e}")
            raise
    
    async def _process_audio_response(self, audio_data: bytes):
        """Process audio response from ElevenLabs"""
        # This can be extended to play audio through Anki's audio system
        logger.debug(f"Received audio response: {len(audio_data)} bytes")
        
        # For now, we'll save to a temporary file and trigger Anki's audio player
        temp_audio_file = os.path.join(mw.addonManager.addonsFolder(__name__), "temp_response.wav")
        
        try:
            with open(temp_audio_file, "wb") as f:
                f.write(audio_data)
            
            # Schedule audio playback on main thread
            if hasattr(mw, 'reviewer') and mw.reviewer:
                def play_audio():
                    from aqt.sound import av_player
                    av_player.play_file(temp_audio_file)
                
                mw.taskman.run_on_main(play_audio)
                
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
    
    async def _process_transcript(self, transcript: str, confidence: float):
        """Process speech transcript from user"""
        logger.info(f"Transcript received (confidence: {confidence:.2f}): {transcript}")
        
        # Only process high-confidence transcripts
        if confidence >= 0.7:
            # Forward to webhook processing
            def process_on_main():
                try:
                    # Get the server instance if available
                    if hasattr(mw, 'voice_server') and mw.voice_server:
                        # Process through existing webhook logic
                        context = {
                            "source": "websocket_stream",
                            "confidence": confidence,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Create a mock request for processing
                        event_data = {
                            "type": "user_speech",
                            "transcript": transcript,
                            "confidence": confidence,
                            "context": context
                        }
                        
                        # Process through conversation event handler
                        result = mw.voice_server._handle_conversation_event(event_data)
                        logger.debug(f"Processed transcript result: {result}")
                        
                except Exception as e:
                    logger.error(f"Transcript processing error: {e}")
            
            mw.taskman.run_on_main(process_on_main)
    
    async def _process_conversation_event(self, event_type: str, message: dict):
        """Process conversation state events"""
        logger.info(f"Conversation event: {event_type}")
        
        # Forward to main thread for Anki integration
        def handle_event():
            try:
                if hasattr(mw, 'voice_server') and mw.voice_server:
                    # Process through existing webhook handlers
                    mw.voice_server._handle_conversation_event(message)
            except Exception as e:
                logger.error(f"Conversation event processing error: {e}")
        
        mw.taskman.run_on_main(handle_event)
    
    def start_streaming_session(self):
        """Start a new streaming session (thread-safe)"""
        def run_async():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.connect())
            except Exception as e:
                logger.error(f"Streaming session error: {e}")
        
        self.executor.submit(run_async)
    
    def stop_streaming_session(self):
        """Stop the streaming session"""
        def run_async():
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.disconnect())
            except Exception as e:
                logger.error(f"Stop streaming error: {e}")
        
        self.executor.submit(run_async)

class ElevenLabsIntegration:
    """Enhanced ElevenLabs integration options for different widget types"""
    
    @staticmethod
    def create_floating_widget(agent_id: str = None, parent=None):
        """Create a floating, draggable widget with enhanced functionality"""
        if not agent_id:
            agent_id = ELEVENLABS_AGENT_ID
            
        # Create the floating widget HTML template
        widget_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Study Buddy</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #f5f5f7;
                }}
                
                #voice-widget {{
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    width: 350px;
                    height: 500px;
                    z-index: 9999;
                    resize: both;
                    overflow: auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    border: 1px solid #e0e0e0;
                    min-width: 300px;
                    min-height: 400px;
                    max-width: 800px;
                    max-height: 800px;
                }}
                
                .widget-header {{
                    cursor: move;
                    background: linear-gradient(135deg, #007bff, #0056b3);
                    color: white;
                    padding: 12px 15px;
                    border-radius: 12px 12px 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    user-select: none;
                    font-weight: 600;
                    font-size: 14px;
                }}
                
                .widget-controls {{
                    display: flex;
                    gap: 8px;
                }}
                
                .control-btn {{
                    background: rgba(255,255,255,0.2);
                    border: none;
                    color: white;
                    width: 24px;
                    height: 24px;
                    border-radius: 4px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    transition: background 0.2s;
                }}
                
                .control-btn:hover {{
                    background: rgba(255,255,255,0.3);
                }}
                
                .widget-content {{
                    height: calc(100% - 48px);
                    position: relative;
                    background: white;
                    border-radius: 0 0 12px 12px;
                }}
                
                .elevenlabs-iframe {{
                    width: 100%;
                    height: 100%;
                    border: none;
                    border-radius: 0 0 12px 12px;
                }}
                
                .widget-status {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    z-index: 10;
                }}
                
                .minimized {{
                    height: 48px !important;
                    resize: none;
                }}
                
                .minimized .widget-content {{
                    display: none;
                }}
                
                .resize-handle {{
                    position: absolute;
                    bottom: 0;
                    right: 0;
                    width: 16px;
                    height: 16px;
                    background: linear-gradient(-45deg, transparent 30%, #999 30%, #999 40%, transparent 40%);
                    cursor: nw-resize;
                }}
                
                @media (max-width: 480px) {{
                    #voice-widget {{
                        width: calc(100vw - 40px);
                        height: calc(100vh - 100px);
                        bottom: 10px;
                        right: 10px;
                        left: 10px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div id="voice-widget">
                <div class="widget-header" id="widget-header">
                    <span>🎯 AI Study Buddy</span>
                    <div class="widget-controls">
                        <button class="control-btn" onclick="toggleSettings()" title="Settings">⚙️</button>
                        <button class="control-btn" onclick="minimizeWidget()" title="Minimize">−</button>
                        <button class="control-btn" onclick="closeWidget()" title="Close">×</button>
                    </div>
                </div>
                <div class="widget-content">
                    <div class="widget-status" id="status">Connecting...</div>
                    <iframe 
                        src="https://elevenlabs.io/convai/embed/{agent_id}?theme=light"
                        class="elevenlabs-iframe"
                        id="elevenlabs-frame"
                        allow="microphone">
                    </iframe>
                    <div class="resize-handle"></div>
                </div>
            </div>
            
            <script>
                // Widget state management
                let isMinimized = false;
                let isDragging = false;
                let currentX, currentY, initialX, initialY;
                let xOffset = 0, yOffset = 0;
                
                // Load saved position and size
                function loadWidgetState() {{
                    const savedState = localStorage.getItem('ankiVoiceWidget');
                    if (savedState) {{
                        const state = JSON.parse(savedState);
                        const widget = document.getElementById('voice-widget');
                        if (state.position) {{
                            widget.style.bottom = 'auto';
                            widget.style.right = 'auto';
                            widget.style.left = state.position.x + 'px';
                            widget.style.top = state.position.y + 'px';
                        }}
                        if (state.size) {{
                            widget.style.width = state.size.width + 'px';
                            widget.style.height = state.size.height + 'px';
                        }}
                        if (state.minimized) {{
                            minimizeWidget();
                        }}
                    }}
                }}
                
                // Save widget state
                function saveWidgetState() {{
                    const widget = document.getElementById('voice-widget');
                    const rect = widget.getBoundingClientRect();
                    const state = {{
                        position: {{ x: rect.left, y: rect.top }},
                        size: {{ width: rect.width, height: rect.height }},
                        minimized: isMinimized
                    }};
                    localStorage.setItem('ankiVoiceWidget', JSON.stringify(state));
                }}
                
                // Drag functionality
                function dragStart(e) {{
                    if (e.target.closest('.control-btn')) return;
                    
                    if (e.type === "touchstart") {{
                        initialX = e.touches[0].clientX - xOffset;
                        initialY = e.touches[0].clientY - yOffset;
                    }} else {{
                        initialX = e.clientX - xOffset;
                        initialY = e.clientY - yOffset;
                    }}
                    
                    if (e.target === document.getElementById('widget-header') || 
                        e.target.closest('.widget-header')) {{
                        isDragging = true;
                    }}
                }}
                
                function dragEnd(e) {{
                    initialX = currentX;
                    initialY = currentY;
                    isDragging = false;
                    saveWidgetState();
                }}
                
                function drag(e) {{
                    if (isDragging) {{
                        e.preventDefault();
                        
                        if (e.type === "touchmove") {{
                            currentX = e.touches[0].clientX - initialX;
                            currentY = e.touches[0].clientY - initialY;
                        }} else {{
                            currentX = e.clientX - initialX;
                            currentY = e.clientY - initialY;
                        }}
                        
                        xOffset = currentX;
                        yOffset = currentY;
                        
                        const widget = document.getElementById('voice-widget');
                        widget.style.bottom = 'auto';
                        widget.style.right = 'auto';
                        widget.style.left = currentX + 'px';
                        widget.style.top = currentY + 'px';
                    }}
                }}
                
                // Widget controls
                function minimizeWidget() {{
                    const widget = document.getElementById('voice-widget');
                    isMinimized = !isMinimized;
                    
                    if (isMinimized) {{
                        widget.classList.add('minimized');
                    }} else {{
                        widget.classList.remove('minimized');
                    }}
                    saveWidgetState();
                }}
                
                function closeWidget() {{
                    if (confirm('Close AI Study Buddy?')) {{
                        document.getElementById('voice-widget').style.display = 'none';
                        // Send close event to parent if in Anki
                        if (window.parent && window.parent.closeVoiceWidget) {{
                            window.parent.closeVoiceWidget();
                        }}
                    }}
                }}
                
                function toggleSettings() {{
                    // Toggle iframe src to show settings
                    const iframe = document.getElementById('elevenlabs-frame');
                    const currentSrc = iframe.src;
                    if (currentSrc.includes('settings=true')) {{
                        iframe.src = `https://elevenlabs.io/convai/embed/{agent_id}?theme=light`;
                    }} else {{
                        iframe.src = `https://elevenlabs.io/convai/embed/{agent_id}?theme=light&settings=true`;
                    }}
                }}
                
                // Status monitoring
                function updateStatus() {{
                    const iframe = document.getElementById('elevenlabs-frame');
                    const status = document.getElementById('status');
                    
                    iframe.onload = function() {{
                        status.textContent = 'Connected';
                        setTimeout(() => {{
                            status.style.display = 'none';
                        }}, 2000);
                    }};
                    
                    iframe.onerror = function() {{
                        status.textContent = 'Connection Error';
                        status.style.background = 'rgba(220,53,69,0.8)';
                    }};
                }}
                
                // Initialize
                document.addEventListener('DOMContentLoaded', function() {{
                    const header = document.getElementById('widget-header');
                    
                    // Mouse events
                    header.addEventListener('mousedown', dragStart);
                    document.addEventListener('mousemove', drag);
                    document.addEventListener('mouseup', dragEnd);
                    
                    // Touch events
                    header.addEventListener('touchstart', dragStart);
                    document.addEventListener('touchmove', drag);
                    document.addEventListener('touchend', dragEnd);
                    
                    // Load saved state
                    loadWidgetState();
                    updateStatus();
                    
                    // Auto-save state on resize
                    const widget = document.getElementById('voice-widget');
                    new ResizeObserver(saveWidgetState).observe(widget);
                }});
                
                // Keyboard shortcuts
                document.addEventListener('keydown', function(e) {{
                    if (e.ctrlKey || e.metaKey) {{
                        switch(e.key) {{
                            case 'm':
                                e.preventDefault();
                                minimizeWidget();
                                break;
                            case 'q':
                                e.preventDefault();
                                closeWidget();
                                break;
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return widget_html
    
    @staticmethod 
    def create_sidebar_integration(agent_id: str = None, parent=None):
        """Create enhanced sidebar integration with QDockWidget"""
        if not agent_id:
            agent_id = ELEVENLABS_AGENT_ID
        
        # Create the dock widget
        widget = QDockWidget("🎯 AI Study Buddy", parent)
        
        # Enhanced features and styling
        widget.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        
        # Set allowed dock areas
        widget.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        
        # Create web view container
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        
        # Status indicator
        status_label = QLabel("🔵 Connected")
        status_label.setStyleSheet("""
            QLabel {
                color: #28a745;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        
        # Control buttons
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh AI Assistant")
        refresh_btn.setMaximumSize(24, 24)
        
        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Settings")
        settings_btn.setMaximumSize(24, 24)
        
        # Style buttons
        button_style = """
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f8f9fa;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #e9ecef;
            }
            QPushButton:pressed {
                background: #dee2e6;
            }
        """
        refresh_btn.setStyleSheet(button_style)
        settings_btn.setStyleSheet(button_style)
        
        toolbar_layout.addWidget(status_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(refresh_btn)
        toolbar_layout.addWidget(settings_btn)
        
        # Create web view
        web_view = QWebEngineView()
        web_view.setUrl(QUrl(f"https://elevenlabs.io/convai/embed/{agent_id}?theme=light&sidebar=true"))
        
        # Connect buttons
        refresh_btn.clicked.connect(lambda: web_view.reload())
        settings_btn.clicked.connect(lambda: web_view.setUrl(
            QUrl(f"https://elevenlabs.io/convai/embed/{agent_id}?theme=light&sidebar=true&settings=true")
        ))
        
        # Monitor web view status
        def update_status():
            status_label.setText("🟡 Loading...")
            status_label.setStyleSheet("QLabel { color: #ffc107; font-weight: bold; font-size: 11px; }")
        
        def on_load_finished(success):
            if success:
                status_label.setText("🟢 Connected")
                status_label.setStyleSheet("QLabel { color: #28a745; font-weight: bold; font-size: 11px; }")
            else:
                status_label.setText("🔴 Error")
                status_label.setStyleSheet("QLabel { color: #dc3545; font-weight: bold; font-size: 11px; }")
        
        web_view.loadStarted.connect(update_status)
        web_view.loadFinished.connect(on_load_finished)
        
        # Add to layout
        layout.addWidget(toolbar)
        layout.addWidget(web_view)
        
        widget.setWidget(container)
        
        # Store references for later use
        widget.web_view = web_view
        widget.status_label = status_label
        widget.agent_id = agent_id
        
        return widget
    
    @staticmethod
    def create_popup_integration(agent_id: str = None, parent=None):
        """Create a popup window integration"""
        if not agent_id:
            agent_id = ELEVENLABS_AGENT_ID
            
        # Create popup window
        popup = QDialog(parent)
        popup.setWindowTitle("AI Study Buddy")
        popup.setModal(False)
        popup.resize(400, 600)
        
        # Set window flags for better behavior
        popup.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Create layout
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create web view
        web_view = QWebEngineView()
        web_view.setUrl(QUrl(f"https://elevenlabs.io/convai/embed/{agent_id}?theme=light&popup=true"))
        
        layout.addWidget(web_view)
        
        # Store reference
        popup.web_view = web_view
        popup.agent_id = agent_id
        
        return popup
    
    @staticmethod
    def get_widget_preferences():
        """Get user preferences for widget type and configuration"""
        return {
            "widget_type": "sidebar",  # floating, sidebar, popup
            "auto_start": True,
            "remember_position": True,
            "minimize_on_startup": False,
            "theme": "light",  # light, dark, auto
            "size": {
                "width": 350,
                "height": 500
            },
            "dock_area": "right"  # left, right, bottom
        }

class WidgetManager:
    """Manages ElevenLabs widget instances and state persistence"""
    
    def __init__(self):
        self.active_widgets = {}
        self.preferences = self._load_preferences()
        
    def _load_preferences(self):
        """Load widget preferences from Anki config"""
        try:
            config = mw.addonManager.getConfig(__name__)
            widget_prefs = config.get('widget_preferences', {})
            
            # Merge with defaults
            defaults = ElevenLabsIntegration.get_widget_preferences()
            defaults.update(widget_prefs)
            return defaults
        except:
            return ElevenLabsIntegration.get_widget_preferences()
    
    def _save_preferences(self):
        """Save widget preferences to Anki config"""
        try:
            config = mw.addonManager.getConfig(__name__)
            config['widget_preferences'] = self.preferences
            mw.addonManager.writeConfig(__name__, config)
        except Exception as e:
            logger.error(f"Failed to save widget preferences: {e}")
    
    def create_widget(self, widget_type: str = None, agent_id: str = None, parent=None):
        """Create a widget based on type and preferences"""
        if not widget_type:
            widget_type = self.preferences.get('widget_type', 'sidebar')
        
        if not agent_id:
            agent_id = ELEVENLABS_AGENT_ID
        
        # Close existing widget of same type
        if widget_type in self.active_widgets:
            self.close_widget(widget_type)
        
        try:
            if widget_type == 'floating':
                widget = self._create_floating_widget(agent_id, parent)
            elif widget_type == 'sidebar':
                widget = self._create_sidebar_widget(agent_id, parent)
            elif widget_type == 'popup':
                widget = self._create_popup_widget(agent_id, parent)
            else:
                raise ValueError(f"Unknown widget type: {widget_type}")
            
            self.active_widgets[widget_type] = widget
            logger.info(f"Created {widget_type} widget with agent {agent_id}")
            return widget
            
        except Exception as e:
            logger.error(f"Failed to create {widget_type} widget: {e}")
            return None
    
    def _create_floating_widget(self, agent_id: str, parent):
        """Create floating widget with web view"""
        # Create a QDialog for the floating widget
        dialog = QDialog(parent)
        dialog.setWindowTitle("AI Study Buddy")
        dialog.setModal(False)
        
        # Set window flags for floating behavior
        dialog.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Apply size from preferences
        size = self.preferences.get('size', {'width': 350, 'height': 500})
        dialog.resize(size['width'], size['height'])
        
        # Create layout
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create web view with floating widget HTML
        web_view = QWebEngineView()
        html_content = ElevenLabsIntegration.create_floating_widget(agent_id, parent)
        web_view.setHtml(html_content)
        
        layout.addWidget(web_view)
        
        # Store references
        dialog.web_view = web_view
        dialog.agent_id = agent_id
        dialog.widget_type = 'floating'
        
        # Show the dialog
        dialog.show()
        
        return dialog
    
    def _create_sidebar_widget(self, agent_id: str, parent):
        """Create sidebar widget using QDockWidget"""
        widget = ElevenLabsIntegration.create_sidebar_integration(agent_id, parent)
        
        # Apply preferences
        dock_area = self.preferences.get('dock_area', 'right')
        if dock_area == 'left':
            area = Qt.DockWidgetArea.LeftDockWidgetArea
        elif dock_area == 'bottom':
            area = Qt.DockWidgetArea.BottomDockWidgetArea
        else:
            area = Qt.DockWidgetArea.RightDockWidgetArea
        
        # Add to main window
        if parent and hasattr(parent, 'addDockWidget'):
            parent.addDockWidget(area, widget)
        elif mw:
            mw.addDockWidget(area, widget)
        
        widget.show()
        return widget
    
    def _create_popup_widget(self, agent_id: str, parent):
        """Create popup widget"""
        widget = ElevenLabsIntegration.create_popup_integration(agent_id, parent)
        
        # Apply size preferences
        size = self.preferences.get('size', {'width': 400, 'height': 600})
        widget.resize(size['width'], size['height'])
        
        # Show popup
        widget.show()
        return widget
    
    def close_widget(self, widget_type: str):
        """Close a specific widget type"""
        if widget_type in self.active_widgets:
            try:
                widget = self.active_widgets[widget_type]
                widget.close()
                del self.active_widgets[widget_type]
                logger.info(f"Closed {widget_type} widget")
            except Exception as e:
                logger.error(f"Error closing {widget_type} widget: {e}")
    
    def close_all_widgets(self):
        """Close all active widgets"""
        for widget_type in list(self.active_widgets.keys()):
            self.close_widget(widget_type)
    
    def get_active_widgets(self):
        """Get list of active widget types"""
        return list(self.active_widgets.keys())
    
    def is_widget_active(self, widget_type: str):
        """Check if a widget type is currently active"""
        return widget_type in self.active_widgets
    
    def set_preference(self, key: str, value):
        """Set a widget preference"""
        self.preferences[key] = value
        self._save_preferences()
    
    def get_preference(self, key: str, default=None):
        """Get a widget preference"""
        return self.preferences.get(key, default)
    
    def toggle_widget(self, widget_type: str = None):
        """Toggle widget visibility"""
        if not widget_type:
            widget_type = self.preferences.get('widget_type', 'sidebar')
        
        if self.is_widget_active(widget_type):
            self.close_widget(widget_type)
        else:
            self.create_widget(widget_type)
    
    def switch_widget_type(self, new_type: str):
        """Switch from current widget type to new type"""
        current_type = self.preferences.get('widget_type', 'sidebar')
        
        if current_type != new_type:
            # Close current widget
            if self.is_widget_active(current_type):
                self.close_widget(current_type)
            
            # Update preference
            self.set_preference('widget_type', new_type)
            
            # Create new widget
            self.create_widget(new_type)
    
    def refresh_active_widgets(self):
        """Refresh all active widgets"""
        for widget_type, widget in self.active_widgets.items():
            try:
                if hasattr(widget, 'web_view'):
                    widget.web_view.reload()
                logger.info(f"Refreshed {widget_type} widget")
            except Exception as e:
                logger.error(f"Error refreshing {widget_type} widget: {e}")

@dataclass
class ReviewSession:
    """Tracks a review session"""
    id: str
    start_time: datetime
    mode: ReviewMode
    state: SessionState
    cards_reviewed: int = 0
    correct_count: int = 0
    streak: int = 0
    best_streak: int = 0
    paused_duration: timedelta = timedelta()
    last_pause_time: Optional[datetime] = None

class AnkiBridge(QObject):
    """Bridge between web view and Anki for bidirectional communication"""
    
    @pyqtSlot(str, result=str)
    def process_command(self, command):
        """Handle commands from the web interface"""
        try:
            if command == "start_focus_mode":
                # Directly start a focus session
                if voice_server:
                    response = requests.post(
                        f"http://127.0.0.1:{voice_server.config.port}/start_session",
                        json={"mode": "focus"},
                        timeout=5
                    )
                    if response.status_code == 200:
                        return json.dumps({"success": True, "message": "Focus session started!"})
                    else:
                        return json.dumps({"success": False, "message": "Failed to start session"})
                else:
                    return json.dumps({"success": False, "message": "Voice server not running"})
            
            elif command == "start_normal_mode":
                if voice_server:
                    response = requests.post(
                        f"http://127.0.0.1:{voice_server.config.port}/start_session",
                        json={"mode": "normal"},
                        timeout=5
                    )
                    if response.status_code == 200:
                        return json.dumps({"success": True, "message": "Normal session started!"})
                    else:
                        return json.dumps({"success": False, "message": "Failed to start session"})
                else:
                    return json.dumps({"success": False, "message": "Voice server not running"})
            
            elif command == "start_speed_mode":
                if voice_server:
                    response = requests.post(
                        f"http://127.0.0.1:{voice_server.config.port}/start_session",
                        json={"mode": "speed"},
                        timeout=5
                    )
                    if response.status_code == 200:
                        return json.dumps({"success": True, "message": "Speed session started!"})
                    else:
                        return json.dumps({"success": False, "message": "Failed to start session"})
                else:
                    return json.dumps({"success": False, "message": "Voice server not running"})
            
            elif command == "show_deck_list":
                try:
                    decks = [{"name": d.name, "id": d.id} for d in mw.col.decks.all_names_and_ids()]
                    return json.dumps({"success": True, "decks": decks})
                except Exception as e:
                    return json.dumps({"success": False, "error": str(e)})
            
            elif command == "get_server_status":
                if voice_server:
                    try:
                        response = requests.get(f"http://127.0.0.1:{voice_server.config.port}/health", timeout=2)
                        if response.status_code == 200:
                            return json.dumps({"success": True, "status": "running", "port": voice_server.config.port})
                    except:
                        pass
                return json.dumps({"success": False, "status": "stopped"})
            
            else:
                return json.dumps({"success": False, "message": f"Unknown command: {command}"})
                
        except Exception as e:
            logger.error(f"AnkiBridge error: {str(e)}")
            return json.dumps({"success": False, "error": str(e)})
    
    @pyqtSlot(result=str)
    def get_current_stats(self):
        """Get current session statistics"""
        try:
            if voice_server and voice_server.current_session:
                accuracy = 0
                if voice_server.current_session.cards_reviewed > 0:
                    accuracy = round(
                        voice_server.current_session.correct_count / 
                        voice_server.current_session.cards_reviewed * 100
                    )
                
                return json.dumps({
                    "success": True,
                    "session_active": True,
                    "cards_reviewed": voice_server.current_session.cards_reviewed,
                    "streak": voice_server.current_session.streak,
                    "best_streak": voice_server.current_session.best_streak,
                    "accuracy": accuracy,
                    "mode": voice_server.current_session.mode.value,
                    "state": voice_server.current_session.state.value
                })
            else:
                # Get basic Anki stats even without active session
                try:
                    counts = mw.col.sched.counts()
                    return json.dumps({
                        "success": True,
                        "session_active": False,
                        "pending_cards": {
                            "new": counts[0],
                            "learning": counts[1], 
                            "review": counts[2],
                            "total": sum(counts)
                        }
                    })
                except:
                    return json.dumps({"success": True, "session_active": False})
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            return json.dumps({"success": False, "error": str(e)})
    
    @pyqtSlot(str, result=str)
    def get_deck_stats(self, deck_name):
        """Get statistics for a specific deck"""
        try:
            deck_id = mw.col.decks.id(deck_name)
            if deck_id:
                # Switch to deck temporarily to get stats
                original_deck = mw.col.decks.current()['id']
                mw.col.decks.select(deck_id)
                counts = mw.col.sched.counts()
                mw.col.decks.select(original_deck)  # Restore original deck
                
                return json.dumps({
                    "success": True,
                    "deck_name": deck_name,
                    "new": counts[0],
                    "learning": counts[1],
                    "review": counts[2],
                    "total": sum(counts)
                })
            else:
                return json.dumps({"success": False, "error": "Deck not found"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

class VoiceReviewConfig:
    """Configuration for voice review"""
    def __init__(self):
        self.port = 5000
        self.host = '127.0.0.1'
        self.enable_ai_hints = True
        self.session_timeout_minutes = 30
        self.streak_encouragement_threshold = 5
        self.difficulty_threshold = 0.3  # Cards answered "again" more than 30% are difficult
        self.auto_start = False
        self.show_voice_assistant = True
        
        # Security and rate limiting
        self.max_requests_per_minute = 100
        self.webhook_secret = None  # Optional ElevenLabs webhook secret for verification
        self.enable_webhook_auth = False  # Enable webhook signature verification
        
        # Load from Anki config
        self.load_config()
    
    def load_config(self):
        """Load configuration from Anki"""
        config = mw.addonManager.getConfig(__name__) or {}
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def save_config(self):
        """Save configuration to Anki"""
        config = {
            'port': self.port,
            'host': self.host,
            'enable_ai_hints': self.enable_ai_hints,
            'session_timeout_minutes': self.session_timeout_minutes,
            'auto_start': self.auto_start,
            'show_voice_assistant': self.show_voice_assistant,
            'max_requests_per_minute': self.max_requests_per_minute,
            'enable_webhook_auth': self.enable_webhook_auth
            # Note: webhook_secret is not saved to config for security
        }
        mw.addonManager.writeConfig(__name__, config)

class VoiceAssistantWidget(QDockWidget):
    """Enhanced ElevenLabs conversational agent with new integration"""
    
    def __init__(self, parent=None, widget_type: str = 'sidebar'):
        super().__init__("🎯 AI Study Buddy", parent)
        self.agent_id = ELEVENLABS_AGENT_ID
        self.widget_type = widget_type
        
        # Initialize widget manager
        self.widget_manager = WidgetManager()
        
        # Use enhanced integration based on type
        if widget_type == 'sidebar':
            self._init_as_sidebar()
        elif widget_type == 'floating':
            self._init_as_floating()
        else:
            self._init_as_sidebar()  # Default fallback
    
    def _init_as_sidebar(self):
        """Initialize as enhanced sidebar widget"""
        # Get enhanced sidebar widget
        enhanced_widget = ElevenLabsIntegration.create_sidebar_integration(self.agent_id, self.parent())
        
        # Copy properties from enhanced widget
        self.setFeatures(enhanced_widget.features())
        self.setAllowedAreas(enhanced_widget.allowedAreas())
        self.setWidget(enhanced_widget.widget())
        
        # Store references from enhanced widget
        self.web_view = enhanced_widget.web_view
        self.status_label = enhanced_widget.status_label
        
    def _init_as_floating(self):
        """Initialize as floating widget"""
        # Create web view for floating content
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)
        
        # Load ElevenLabs conversational interface
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    margin: 0;
                    padding: 10px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #f5f5f5;
                }}
                #agent-container {{
                    width: 100%;
                    height: 100%;
                    min-height: 350px;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .status {{
                    padding: 10px;
                    background: #e8f4f8;
                    border-radius: 5px;
                    margin-bottom: 10px;
                    font-size: 14px;
                }}
                .error {{
                    background: #ffe8e8;
                    color: #d00;
                }}
                .controls {{
                    margin: 10px 0;
                    display: flex;
                    gap: 10px;
                }}
                .control-btn {{
                    padding: 8px 16px;
                    border: none;
                    border-radius: 5px;
                    background: #007bff;
                    color: white;
                    cursor: pointer;
                    font-size: 14px;
                }}
                .control-btn:hover {{
                    background: #0056b3;
                }}
                .tip {{
                    background: #fff3cd;
                    border: 1px solid #ffeaa7;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                    font-size: 13px;
                }}
            </style>
        </head>
        <body>
            <div class="status">🤖 AI Study Buddy Ready - Make sure your review server is running!</div>
            
            <div class="controls">
                <button class="control-btn" onclick="startNormalSession()">📚 Normal Study</button>
                <button class="control-btn" onclick="startSpeedSession()">⚡ Speed Mode</button>
                <button class="control-btn" onclick="startFocusSession()">🎯 Focus Mode</button>
                <button class="control-btn" onclick="showStats()">📊 Statistics</button>
            </div>
            
            <div id="agent-container">
                <iframe
                    id="elevenlabs-agent"
                    src="https://elevenlabs.io/convai/embed/{self.agent_id}"
                    width="100%"
                    height="350"
                    frameborder="0"
                    allow="microphone"
                    style="border-radius: 10px;">
                </iframe>
            </div>
            
            <div class="tip">
                💡 <strong>Tip:</strong> You can say things like "I don't remember" instead of "again", 
                or "that was tough" instead of "hard". The AI understands natural language!
            </div>
            
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                let ankiBridge;
                
                // Initialize QWebChannel connection
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    ankiBridge = channel.objects.anki;
                    initializeUI();
                }});
                
                function initializeUI() {{
                    checkServerStatus();
                    setInterval(checkServerStatus, 5000);
                    updateStats();
                    setInterval(updateStats, 3000);
                }}
                
                // Enhanced server status check using bridge
                async function checkServerStatus() {{
                    if (!ankiBridge) return;
                    
                    try {{
                        const statusResponse = await new Promise((resolve) => {{
                            ankiBridge.process_command('get_server_status', resolve);
                        }});
                        const status = JSON.parse(statusResponse);
                        
                        if (status.success && status.status === 'running') {{
                            document.querySelector('.status').textContent = 
                                `✅ Connected to Anki (Port ${{status.port}}) - Ready for voice commands!`;
                            document.querySelector('.status').className = 'status';
                        }} else {{
                            document.querySelector('.status').className = 'status error';
                            document.querySelector('.status').textContent = 
                                '❌ Voice server not running - Start from Tools → Voice Review!';
                        }}
                    }} catch (e) {{
                        document.querySelector('.status').className = 'status error';
                        document.querySelector('.status').textContent = 
                            '❌ Connection error - Check Anki bridge';
                    }}
                }}
                
                // Update statistics display
                async function updateStats() {{
                    if (!ankiBridge) return;
                    
                    try {{
                        const statsResponse = await new Promise((resolve) => {{
                            ankiBridge.get_current_stats(resolve);
                        }});
                        const stats = JSON.parse(statsResponse);
                        
                        if (stats.success) {{
                            updateStatsDisplay(stats);
                        }}
                    }} catch (e) {{
                        console.error('Failed to get stats:', e);
                    }}
                }}
                
                function updateStatsDisplay(stats) {{
                    let statusText = '';
                    if (stats.session_active) {{
                        statusText = `📊 Session: ${{stats.cards_reviewed}} cards, ${{stats.streak}} streak, ${{stats.accuracy}}% accuracy`;
                    }} else if (stats.pending_cards) {{
                        statusText = `📚 Ready: ${{stats.pending_cards.total}} cards waiting (${{stats.pending_cards.new}} new, ${{stats.pending_cards.review}} review)`;
                    }}
                    
                    if (statusText) {{
                        let statsDiv = document.getElementById('live-stats');
                        if (!statsDiv) {{
                            statsDiv = document.createElement('div');
                            statsDiv.id = 'live-stats';
                            statsDiv.style.cssText = 'margin: 10px 0; padding: 8px; background: #e8f4f8; border-radius: 5px; font-size: 13px;';
                            document.querySelector('.controls').parentNode.insertBefore(statsDiv, document.querySelector('.controls').nextSibling);
                        }}
                        statsDiv.textContent = statusText;
                    }}
                }}
                
                // Enhanced quick start functions using bridge
                async function startNormalSession() {{
                    if (!ankiBridge) return;
                    try {{
                        const response = await new Promise((resolve) => {{
                            ankiBridge.process_command('start_normal_mode', resolve);
                        }});
                        const result = JSON.parse(response);
                        showMessage(result.message || 'Normal session starting...');
                    }} catch (e) {{
                        showMessage('Failed to start normal session');
                    }}
                }}
                
                async function startSpeedSession() {{
                    if (!ankiBridge) return;
                    try {{
                        const response = await new Promise((resolve) => {{
                            ankiBridge.process_command('start_speed_mode', resolve);
                        }});
                        const result = JSON.parse(response);
                        showMessage(result.message || 'Speed session starting...');
                    }} catch (e) {{
                        showMessage('Failed to start speed session');
                    }}
                }}
                
                async function startFocusSession() {{
                    if (!ankiBridge) return;
                    try {{
                        const response = await new Promise((resolve) => {{
                            ankiBridge.process_command('start_focus_mode', resolve);
                        }});
                        const result = JSON.parse(response);
                        showMessage(result.message || 'Focus session starting...');
                    }} catch (e) {{
                        showMessage('Failed to start focus session');
                    }}
                }}
                
                async function showStats() {{
                    if (!ankiBridge) return;
                    try {{
                        const response = await new Promise((resolve) => {{
                            ankiBridge.get_current_stats(resolve);
                        }});
                        const stats = JSON.parse(response);
                        if (stats.success) {{
                            let message = stats.session_active 
                                ? `Current Session: ${{stats.cards_reviewed}} cards reviewed, ${{stats.streak}} current streak, ${{stats.best_streak}} best streak, ${{stats.accuracy}}% accuracy`
                                : 'No active session. Start reviewing to see statistics!';
                            showMessage(message);
                        }}
                    }} catch (e) {{
                        showMessage('Failed to get statistics');
                    }}
                }}
                
                function showMessage(message) {{
                    const tip = document.querySelector('.tip');
                    const original = tip.innerHTML;
                    tip.innerHTML = `<strong>📢 ${{message}}</strong>`;
                    tip.style.background = '#d4edda';
                    setTimeout(() => {{
                        tip.innerHTML = original;
                        tip.style.background = '#fff3cd';
                    }}, 3000);
                }}
                
                // Fallback for browsers without QWebChannel
                if (typeof QWebChannel === 'undefined') {{
                    console.warn('QWebChannel not available, using fallback');
                    async function checkServerStatus() {{
                        try {{
                            const response = await fetch('http://127.0.0.1:5000/health');
                            const data = await response.json();
                            if (data.status === 'healthy') {{
                                document.querySelector('.status').textContent = 
                                    '✅ Connected to Anki - Say "start session" to begin!';
                                document.querySelector('.status').className = 'status';
                            }}
                        }} catch (e) {{
                            document.querySelector('.status').className = 'status error';
                            document.querySelector('.status').textContent = 
                                '❌ Anki server not running - Start the voice server from Tools → Voice Review!';
                        }}
                    }}
                    checkServerStatus();
                    setInterval(checkServerStatus, 5000);
                }}
            </script>
        </body>
        </html>
        """
        
        self.web_view.setHtml(html_content)
        
        # Set up QWebChannel bridge
        self.bridge = AnkiBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("anki", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        self.setWidget(self.web_view)
        self.setFloating(False)
    
    def switch_widget_type(self, new_type: str):
        """Switch widget type using widget manager"""
        if hasattr(self, 'widget_manager'):
            self.widget_manager.switch_widget_type(new_type)
            # Update this widget's type
            self.widget_type = new_type
    
    def refresh_widget(self):
        """Refresh the widget content"""
        if hasattr(self, 'web_view'):
            self.web_view.reload()
    
    def get_widget_preferences(self):
        """Get current widget preferences"""
        if hasattr(self, 'widget_manager'):
            return self.widget_manager.preferences
        return {}
    
    def set_widget_preference(self, key: str, value):
        """Set a widget preference"""
        if hasattr(self, 'widget_manager'):
            self.widget_manager.set_preference(key, value)
    
    def toggle_widget_visibility(self):
        """Toggle widget visibility using widget manager"""
        if hasattr(self, 'widget_manager'):
            self.widget_manager.toggle_widget(self.widget_type)

class VoiceAssistantDialog(QDialog):
    """Floating voice assistant window"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anki AI Study Buddy")
        self.setMinimumSize(450, 600)
        
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🎓 Anki AI Study Buddy")
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 5px;
        """)
        layout.addWidget(header)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("📚 Start Session")
        self.start_btn.clicked.connect(self.start_session)
        button_layout.addWidget(self.start_btn)
        
        self.stats_btn = QPushButton("📊 View Stats")
        self.stats_btn.clicked.connect(self.show_stats)
        button_layout.addWidget(self.stats_btn)
        
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        button_layout.addWidget(self.settings_btn)
        
        layout.addLayout(button_layout)
        
        # Embedded agent
        self.web_view = QWebEngineView()
        self.web_view.setHtml(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 10px; background: #f5f5f5; }}
                .container {{ background: white; border-radius: 10px; padding: 10px; }}
                .stats-bar {{ 
                    background: #e8f4f8; 
                    padding: 8px; 
                    border-radius: 5px; 
                    margin-bottom: 10px; 
                    font-size: 13px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div id="stats-display" class="stats-bar">Loading session info...</div>
            <div class="container">
                <iframe
                    src="https://elevenlabs.io/convai/embed/{ELEVENLABS_AGENT_ID}"
                    width="100%"
                    height="450"
                    frameborder="0"
                    allow="microphone"
                    style="border-radius: 10px;">
                </iframe>
            </div>
            
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                let ankiBridge;
                
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    ankiBridge = channel.objects.anki;
                    updateStatsDisplay();
                    setInterval(updateStatsDisplay, 3000);
                }});
                
                async function updateStatsDisplay() {{
                    if (!ankiBridge) return;
                    
                    try {{
                        const response = await new Promise((resolve) => {{
                            ankiBridge.get_current_stats(resolve);
                        }});
                        const stats = JSON.parse(response);
                        
                        let display = '';
                        if (stats.success && stats.session_active) {{
                            display = `📊 Active Session: ${{stats.cards_reviewed}} cards • ${{stats.streak}} streak • ${{stats.accuracy}}% accuracy`;
                        }} else if (stats.success && stats.pending_cards) {{
                            display = `📚 ${{stats.pending_cards.total}} cards waiting • ${{stats.pending_cards.new}} new • ${{stats.pending_cards.review}} review`;
                        }} else {{
                            display = '💬 Ready to start reviewing - say "start session" to begin!';
                        }}
                        
                        document.getElementById('stats-display').textContent = display;
                    }} catch (e) {{
                        document.getElementById('stats-display').textContent = '⚠️ Connection issue with Anki';
                    }}
                }}
            </script>
        </body>
        </html>
        """)
        
        # Set up QWebChannel bridge for dialog too
        self.bridge = AnkiBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("anki", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        layout.addWidget(self.web_view)
        
        # Tips section
        tips = QTextBrowser()
        tips.setMaximumHeight(100)
        tips.setHtml("""
        <html>
        <body style="font-family: Arial; font-size: 12px;">
        <b>Voice Commands:</b><br>
        • "Start session" / "Let's study" - Begin reviewing<br>
        • "Next card" / "Continue" - Get next question<br>
        • "Show answer" / "I give up" - Reveal answer<br>
        • "Hint please" / "Help me" - Get a hint<br>
        • Natural responses work: "I forgot", "Got it", "Too easy"
        </body>
        </html>
        """)
        layout.addWidget(tips)
        
        self.setLayout(layout)
    
    def start_session(self):
        """Show session start hint"""
        QMessageBox.information(self, "Start Session", 
            "Say 'Hey, let's start studying' or 'Begin session' to the AI assistant!")
    
    def show_stats(self):
        """Show Anki statistics"""
        mw.onStats()
    
    def show_settings(self):
        """Show configuration dialog"""
        open_config_dialog()

class RateLimiter:
    """Simple rate limiter for webhook requests"""
    
    def __init__(self, max_requests_per_minute=100):
        self.max_requests = max_requests_per_minute
        self.requests = {}  # IP -> list of timestamps
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = datetime.now()
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request from client_ip is allowed"""
        now = datetime.now()
        
        # Cleanup old entries periodically
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            self._cleanup_old_requests(now)
            self.last_cleanup = now
        
        # Get or create request history for this IP
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Remove requests older than 1 minute
        one_minute_ago = now - timedelta(minutes=1)
        self.requests[client_ip] = [
            timestamp for timestamp in self.requests[client_ip] 
            if timestamp > one_minute_ago
        ]
        
        # Check if under limit
        if len(self.requests[client_ip]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return False
        
        # Add current request
        self.requests[client_ip].append(now)
        return True
    
    def _cleanup_old_requests(self, now: datetime):
        """Remove old request histories to prevent memory buildup"""
        cutoff = now - timedelta(minutes=5)  # Keep last 5 minutes
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                timestamp for timestamp in self.requests[ip] 
                if timestamp > cutoff
            ]
            # Remove empty entries
            if not self.requests[ip]:
                del self.requests[ip]

class AnkiVoiceReviewServer:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for webhook access
        self.config = VoiceReviewConfig()
        
        # State management
        self.current_card = None
        self.is_showing_answer = False
        self.current_session: Optional[ReviewSession] = None
        self.review_history: List[Dict] = []
        
        # Utilities
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_images = True
        self.h2t.ignore_links = True
        self.h2t.body_width = 0  # Don't wrap text
        
        # Rate limiting and security
        max_requests = getattr(self.config, 'max_requests_per_minute', 100)
        self.rate_limiter = RateLimiter(max_requests_per_minute=max_requests)
        
        # Voice streaming handler
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if api_key:
            self.voice_stream_handler = VoiceStreamHandler(ELEVENLABS_AGENT_ID, api_key)
        else:
            self.voice_stream_handler = None
            logger.warning("ELEVENLABS_API_KEY not found, WebSocket streaming disabled")
        
        # Database for session history
        self.init_database()
        self.setup_routes()
        self.setup_error_handlers()
    
    def init_database(self):
        """Initialize SQLite database for session tracking"""
        db_path = os.path.join(mw.addonManager.addonsFolder(__name__), 'sessions.db')
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                mode TEXT,
                cards_reviewed INTEGER,
                correct_count INTEGER,
                best_streak INTEGER,
                total_duration_seconds INTEGER
            )
        ''')
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS review_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                card_id INTEGER,
                question TEXT,
                answer TEXT,
                user_rating TEXT,
                review_time TIMESTAMP,
                time_to_answer_seconds REAL,
                hints_used INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        ''')
        self.db.commit()
    
    def setup_error_handlers(self):
        """Setup Flask error handlers"""
        @self.app.errorhandler(404)
        def not_found(e):
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        
        @self.app.errorhandler(500)
        def internal_error(e):
            logger.error(f"Internal server error: {str(e)}")
            return jsonify({"success": False, "error": "Internal server error"}), 500
    
    def verify_webhook_signature(self, signature: str, payload: bytes) -> bool:
        """Verify ElevenLabs webhook signature"""
        if not self.config.webhook_secret or not self.config.enable_webhook_auth:
            return True  # Skip verification if not configured
        
        try:
            expected_signature = hmac.new(
                self.config.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Remove 'sha256=' prefix if present
            if signature.startswith('sha256='):
                signature = signature[7:]
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def create_pwa_manifest(self):
        """Create a PWA manifest for mobile access"""
        return {
            "name": "Anki Voice Study Buddy",
            "short_name": "Anki Voice",
            "description": "Review Anki cards hands-free with AI",
            "start_url": "/mobile",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#f5f5f5",
            "theme_color": "#007bff",
            "scope": "/",
            "lang": "en",
            "icons": [
                {
                    "src": "/static/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/static/icon-512.png", 
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ],
            "screenshots": [
                {
                    "src": "/static/screenshot-mobile.png",
                    "sizes": "390x844",
                    "type": "image/png",
                    "form_factor": "narrow"
                }
            ],
            "categories": ["education", "productivity"],
            "shortcuts": [
                {
                    "name": "Start Review",
                    "short_name": "Review",
                    "description": "Start a new review session",
                    "url": "/mobile?action=start",
                    "icons": [{"src": "/static/icon-192.png", "sizes": "192x192"}]
                },
                {
                    "name": "Statistics",
                    "short_name": "Stats",
                    "description": "View your study statistics",
                    "url": "/mobile?action=stats",
                    "icons": [{"src": "/static/icon-192.png", "sizes": "192x192"}]
                }
            ]
        }
    
    def create_mobile_interface_html(self):
        """Create mobile-optimized HTML interface"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Anki Voice">
    <meta name="theme-color" content="#007bff">
    <title>Anki Voice Study Buddy</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <link rel="icon" href="/static/icon-192.png">
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }
        
        .container {
            max-width: 420px;
            margin: 0 auto;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-top: env(safe-area-inset-top, 20px);
        }
        
        .logo {
            font-size: 3rem;
            margin-bottom: 10px;
        }
        
        .title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .subtitle {
            font-size: 1rem;
            opacity: 0.8;
        }
        
        .status-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            background: #ff6b6b;
        }
        
        .status-dot.connected {
            background: #51cf66;
        }
        
        .status-text {
            font-weight: 500;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat-item {
            text-align: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            display: block;
        }
        
        .stat-label {
            font-size: 0.8rem;
            opacity: 0.8;
            margin-top: 5px;
        }
        
        .action-buttons {
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin: 30px 0;
            flex-grow: 1;
        }
        
        .action-btn {
            padding: 18px 25px;
            border: none;
            border-radius: 25px;
            font-size: 1.1rem;
            font-weight: 600;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        .action-btn:hover, .action-btn:focus {
            transform: translateY(-2px);
            background: rgba(255, 255, 255, 0.3);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        }
        
        .action-btn:active {
            transform: translateY(0);
        }
        
        .action-btn.primary {
            background: linear-gradient(45deg, #007bff, #0056b3);
            border: none;
        }
        
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .voice-container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            flex-grow: 1;
            min-height: 300px;
        }
        
        .voice-iframe {
            width: 100%;
            height: 100%;
            min-height: 300px;
            border: none;
            border-radius: 15px;
            background: white;
        }
        
        .tips {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 15px;
            margin-top: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-bottom: env(safe-area-inset-bottom, 20px);
        }
        
        .tips h4 {
            margin-bottom: 10px;
            font-size: 1rem;
        }
        
        .tips ul {
            list-style: none;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        
        .tips li {
            margin-bottom: 5px;
            opacity: 0.9;
        }
        
        .tips li:before {
            content: "💬 ";
            margin-right: 5px;
        }
        
        .install-prompt {
            position: fixed;
            bottom: 20px;
            left: 20px;
            right: 20px;
            background: #007bff;
            color: white;
            padding: 15px;
            border-radius: 15px;
            display: none;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            z-index: 1000;
        }
        
        .install-prompt.show {
            display: flex;
        }
        
        .install-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
        }
        
        .close-btn {
            background: none;
            border: none;
            color: white;
            font-size: 1.2rem;
            cursor: pointer;
            padding: 5px;
        }
        
        @media (max-width: 375px) {
            .container {
                padding: 15px;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
        
        @media (max-height: 600px) {
            .voice-container {
                min-height: 200px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🎓</div>
            <div class="title">Anki Voice Study</div>
            <div class="subtitle">Hands-free flashcard review</div>
        </div>
        
        <div class="status-card">
            <div class="status-indicator">
                <div class="status-dot" id="statusDot"></div>
                <span class="status-text" id="statusText">Connecting...</span>
            </div>
            
            <div class="stats-grid" id="statsGrid">
                <div class="stat-item">
                    <span class="stat-value" id="cardsReviewed">-</span>
                    <span class="stat-label">Reviewed</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value" id="currentStreak">-</span>
                    <span class="stat-label">Streak</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value" id="accuracy">-</span>
                    <span class="stat-label">Accuracy</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value" id="pending">-</span>
                    <span class="stat-label">Pending</span>
                </div>
            </div>
        </div>
        
        <div class="action-buttons">
            <button class="action-btn primary" onclick="startSession()" id="startBtn">
                📚 Start Review Session
            </button>
            <button class="action-btn" onclick="showVoiceAssistant()" id="voiceBtn">
                🎤 Voice Assistant
            </button>
            <button class="action-btn" onclick="viewStats()" id="statsBtn">
                📊 View Statistics
            </button>
        </div>
        
        <div class="voice-container" id="voiceContainer" style="display: none;">
            <iframe class="voice-iframe" id="voiceIframe" 
                    src="https://elevenlabs.io/convai/embed/{{ agent_id }}"
                    allow="microphone">
            </iframe>
        </div>
        
        <div class="tips">
            <h4>Voice Commands:</h4>
            <ul>
                <li>"Start session" to begin reviewing</li>
                <li>"Next card" for the next question</li>
                <li>"Show answer" to reveal the solution</li>
                <li>"Again/Hard/Good/Easy" to rate cards</li>
                <li>"Statistics" to view your progress</li>
            </ul>
        </div>
    </div>
    
    <div class="install-prompt" id="installPrompt">
        <div>
            <strong>Install Anki Voice</strong><br>
            <small>Add to home screen for quick access</small>
        </div>
        <div>
            <button class="install-btn" onclick="installApp()">Install</button>
            <button class="close-btn" onclick="hideInstallPrompt()">&times;</button>
        </div>
    </div>
    
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        let ankiBridge;
        let deferredPrompt;
        let isSessionActive = false;
        
        // Service Worker Registration
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
                .then(registration => console.log('SW registered'))
                .catch(error => console.log('SW registration failed'));
        }
        
        // PWA Install Prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            showInstallPrompt();
        });
        
        function showInstallPrompt() {
            document.getElementById('installPrompt').classList.add('show');
        }
        
        function hideInstallPrompt() {
            document.getElementById('installPrompt').classList.remove('show');
        }
        
        function installApp() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {
                    if (choiceResult.outcome === 'accepted') {
                        console.log('User accepted the install prompt');
                    }
                    deferredPrompt = null;
                    hideInstallPrompt();
                });
            }
        }
        
        // Initialize QWebChannel if available
        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                ankiBridge = channel.objects.anki;
                initializeApp();
            });
        } else {
            // Fallback for web access
            initializeApp();
        }
        
        function initializeApp() {
            checkServerStatus();
            updateStats();
            setInterval(updateStats, 5000);
            
            // Check URL parameters for actions
            const urlParams = new URLSearchParams(window.location.search);
            const action = urlParams.get('action');
            if (action === 'start') {
                startSession();
            } else if (action === 'stats') {
                viewStats();
            }
        }
        
        async function checkServerStatus() {
            try {
                let status;
                if (ankiBridge) {
                    const response = await new Promise((resolve) => {
                        ankiBridge.process_command('get_server_status', resolve);
                    });
                    status = JSON.parse(response);
                } else {
                    const response = await fetch('/health');
                    status = await response.json();
                }
                
                const statusDot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');
                
                if (status.success && status.status === 'running') {
                    statusDot.classList.add('connected');
                    statusText.textContent = 'Connected to Anki';
                    document.getElementById('startBtn').disabled = false;
                } else {
                    statusDot.classList.remove('connected');
                    statusText.textContent = 'Server not running';
                    document.getElementById('startBtn').disabled = true;
                }
            } catch (error) {
                const statusDot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');
                statusDot.classList.remove('connected');
                statusText.textContent = 'Connection error';
                document.getElementById('startBtn').disabled = true;
            }
        }
        
        async function updateStats() {
            try {
                let stats;
                if (ankiBridge) {
                    const response = await new Promise((resolve) => {
                        ankiBridge.get_current_stats(resolve);
                    });
                    stats = JSON.parse(response);
                } else {
                    // Fallback for web access
                    return;
                }
                
                if (stats.success) {
                    if (stats.session_active) {
                        document.getElementById('cardsReviewed').textContent = stats.cards_reviewed;
                        document.getElementById('currentStreak').textContent = stats.streak;
                        document.getElementById('accuracy').textContent = stats.accuracy + '%';
                        document.getElementById('pending').textContent = '-';
                        isSessionActive = true;
                        updateButtonStates();
                    } else if (stats.pending_cards) {
                        document.getElementById('cardsReviewed').textContent = '-';
                        document.getElementById('currentStreak').textContent = '-';
                        document.getElementById('accuracy').textContent = '-';
                        document.getElementById('pending').textContent = stats.pending_cards.total;
                        isSessionActive = false;
                        updateButtonStates();
                    }
                }
            } catch (error) {
                console.error('Failed to update stats:', error);
            }
        }
        
        function updateButtonStates() {
            const startBtn = document.getElementById('startBtn');
            if (isSessionActive) {
                startBtn.textContent = '📚 Session Active';
                startBtn.onclick = showVoiceAssistant;
            } else {
                startBtn.textContent = '📚 Start Review Session';
                startBtn.onclick = startSession;
            }
        }
        
        async function startSession() {
            try {
                if (ankiBridge) {
                    const response = await new Promise((resolve) => {
                        ankiBridge.process_command('start_normal_mode', resolve);
                    });
                    const result = JSON.parse(response);
                    if (result.success) {
                        showMessage('Session started! 🎉');
                        showVoiceAssistant();
                    } else {
                        showMessage('Failed to start session: ' + result.message);
                    }
                } else {
                    // Fallback for web access
                    const response = await fetch('/start_session', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({mode: 'normal'})
                    });
                    const result = await response.json();
                    if (result.success) {
                        showMessage('Session started! 🎉');
                        showVoiceAssistant();
                    }
                }
            } catch (error) {
                showMessage('Error starting session');
            }
        }
        
        function showVoiceAssistant() {
            const voiceContainer = document.getElementById('voiceContainer');
            const actionButtons = document.querySelector('.action-buttons');
            
            if (voiceContainer.style.display === 'none') {
                voiceContainer.style.display = 'block';
                actionButtons.style.display = 'none';
                document.getElementById('voiceBtn').textContent = '📱 Show Controls';
                document.getElementById('voiceBtn').onclick = hideVoiceAssistant;
            } else {
                hideVoiceAssistant();
            }
        }
        
        function hideVoiceAssistant() {
            const voiceContainer = document.getElementById('voiceContainer');
            const actionButtons = document.querySelector('.action-buttons');
            
            voiceContainer.style.display = 'none';
            actionButtons.style.display = 'flex';
            document.getElementById('voiceBtn').textContent = '🎤 Voice Assistant';
            document.getElementById('voiceBtn').onclick = showVoiceAssistant;
        }
        
        async function viewStats() {
            try {
                if (ankiBridge) {
                    const response = await new Promise((resolve) => {
                        ankiBridge.get_current_stats(resolve);
                    });
                    const stats = JSON.parse(response);
                    if (stats.success && stats.session_active) {
                        showMessage(`Session: ${stats.cards_reviewed} cards, ${stats.accuracy}% accuracy, ${stats.streak} streak`);
                    } else {
                        showMessage('No active session. Start reviewing to see statistics!');
                    }
                } else {
                    showMessage('Statistics available in desktop app');
                }
            } catch (error) {
                showMessage('Error getting statistics');
            }
        }
        
        function showMessage(message) {
            // Create a temporary toast message
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px 25px;
                border-radius: 25px;
                z-index: 10000;
                font-weight: 500;
                backdrop-filter: blur(10px);
            `;
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 3000);
        }
        
        // Handle offline/online events
        window.addEventListener('online', () => {
            showMessage('Back online! 🌐');
            checkServerStatus();
        });
        
        window.addEventListener('offline', () => {
            showMessage('You are offline 📵');
        });
    </script>
</body>
</html>
        """
    
    def setup_routes(self):
        """Define all webhook endpoints"""
        
        @self.app.before_request
        def verify_webhook():
            """Verify webhook requests and apply rate limiting"""
            # In production, verify webhook signatures
            if request.method == 'POST':
                # Log request for debugging
                logger.debug(f"Webhook received: {request.path}")
                logger.debug(f"Headers: {dict(request.headers)}")
                logger.debug(f"Body: {request.get_data(as_text=True)}")
                
                # Verify ElevenLabs webhook signature (if configured)
                signature = request.headers.get('X-ElevenLabs-Signature')
                if signature and self.config.enable_webhook_auth:
                    payload = request.get_data()
                    if not self.verify_webhook_signature(signature, payload):
                        logger.warning(f"Invalid webhook signature from {request.remote_addr}")
                        return jsonify({"error": "Invalid webhook signature"}), 401
            
            # Apply rate limiting to all requests
            client_ip = request.remote_addr or 'unknown'
            if not self.rate_limiter.is_allowed(client_ip):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            # Log all requests (keeping original functionality)
            logger.debug(f"Request: {request.method} {request.path} from {client_ip}")
            if request.json:
                logger.debug(f"Payload: {request.json}")
            elif request.method == 'POST' and request.data:
                logger.debug(f"Raw data: {request.get_data(as_text=True)[:200]}...")  # Limit log size
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                "success": True,
                "status": "healthy",
                "session_active": self.current_session is not None,
                "anki_connected": mw.col is not None
            })
        
        @self.app.route('/webhook/conversation_event', methods=['POST'])
        def handle_conversation_event():
            """Handle conversation events from ElevenLabs"""
            try:
                data = request.json or {}
                event_type = data.get('event_type')
                
                logger.info(f"Conversation event: {event_type}")
                
                if event_type == 'session_started':
                    # Initialize session when conversation starts
                    return self._handle_start_session(data)
                
                elif event_type == 'user_intent':
                    intent = data.get('intent', '').lower()
                    entities = data.get('entities', {})
                    user_message = data.get('user_message', '')
                    
                    logger.debug(f"User intent: {intent}, entities: {entities}")
                    
                    # Route based on detected intent
                    intent_handlers = {
                        'start_review': lambda: self._handle_start_session(data),
                        'start_session': lambda: self._handle_start_session(data),
                        'next_card': lambda: self._handle_next_card(),
                        'show_answer': lambda: self._handle_show_answer(),
                        'rate_card': lambda: self._handle_answer_card(entities),
                        'answer_card': lambda: self._handle_answer_card(entities),
                        'get_hint': lambda: self._handle_get_hint(),
                        'pause': lambda: self._handle_pause_session(),
                        'resume': lambda: self._handle_resume_session(),
                        'statistics': lambda: self._handle_get_statistics(data),
                        'end_session': lambda: self._handle_end_session(),
                        'explain': lambda: self._handle_explain_concept(),
                        'related_cards': lambda: self._handle_get_related_cards()
                    }
                    
                    # Try exact intent match first
                    handler = intent_handlers.get(intent)
                    if handler:
                        return handler()
                    
                    # Fallback: intent detection from user message
                    return self._detect_intent_from_message(user_message, entities)
                
                elif event_type == 'session_ended':
                    return self._handle_end_session()
                
                elif event_type == 'user_speech':
                    # Handle direct speech recognition results
                    transcript = data.get('transcript', '').lower()
                    confidence = data.get('confidence', 0.0)
                    
                    if confidence > 0.7:  # High confidence threshold
                        return self._process_speech_command(transcript)
                    else:
                        return jsonify({
                            "success": False,
                            "message": "Could not understand speech clearly. Please try again.",
                            "confidence": confidence
                        })
                
                else:
                    logger.warning(f"Unknown event type: {event_type}")
                    return jsonify({
                        "success": False,
                        "message": f"Unknown event type: {event_type}"
                    })
                    
            except Exception as e:
                logger.error(f"Conversation webhook error: {str(e)}")
                return jsonify({
                    "success": False,
                    "error": "Internal server error",
                    "message": "An error occurred processing your request"
                }), 500
        
        @self.app.route('/webhook/audio_stream', methods=['POST'])
        def handle_audio_stream():
            """Handle real-time audio streaming for immediate feedback"""
            try:
                data = request.json or {}
                stream_type = data.get('stream_type')
                
                if stream_type == 'partial_transcript':
                    # Handle partial speech recognition
                    partial_text = data.get('text', '').lower()
                    
                    # Provide immediate feedback for common commands
                    quick_responses = {
                        'next': "Getting next card...",
                        'answer': "Showing answer...",
                        'hint': "Generating hint...",
                        'again': "Marked as 'again'",
                        'good': "Marked as 'good'",
                        'easy': "Marked as 'easy'",
                        'hard': "Marked as 'hard'"
                    }
                    
                    for command, response in quick_responses.items():
                        if command in partial_text:
                            return jsonify({
                                "success": True,
                                "immediate_feedback": response,
                                "recognized_command": command
                            })
                
                elif stream_type == 'audio_chunk':
                    # Handle audio processing (for future enhancement)
                    return jsonify({
                        "success": True,
                        "message": "Audio chunk received"
                    })
                
                return jsonify({"success": True})
                
            except Exception as e:
                logger.error(f"Audio stream error: {str(e)}")
                return jsonify({"error": "Stream processing error"}), 500
        
        @self.app.route('/manifest.json', methods=['GET'])
        def serve_manifest():
            """Serve PWA manifest for mobile installation"""
            manifest = self.create_pwa_manifest()
            response = jsonify(manifest)
            response.headers['Content-Type'] = 'application/manifest+json'
            response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
            return response
        
        @self.app.route('/mobile', methods=['GET'])
        def mobile_interface():
            """Serve mobile-optimized interface"""
            try:
                html_content = self.create_mobile_interface_html()
                # Replace template variable with actual agent ID
                html_content = html_content.replace('{{ agent_id }}', ELEVENLABS_AGENT_ID)
                
                # Add headers for PWA
                response = self.app.response_class(
                    response=html_content,
                    status=200,
                    mimetype='text/html'
                )
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                return response
            except Exception as e:
                logger.error(f"Error serving mobile interface: {str(e)}")
                return jsonify({"error": "Failed to load mobile interface"}), 500
        
        @self.app.route('/offline.html', methods=['GET'])
        def offline_page():
            """Serve offline page for PWA"""
            offline_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline - Anki Voice</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            text-align: center;
        }
        .offline-container {
            padding: 40px 20px;
            max-width: 400px;
        }
        .offline-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }
        p {
            font-size: 1.1rem;
            line-height: 1.6;
            margin-bottom: 30px;
            opacity: 0.9;
        }
        .retry-btn {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }
        .retry-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="offline-container">
        <div class="offline-icon">📵</div>
        <h1>You're Offline</h1>
        <p>
            The AI Study Buddy needs an internet connection to work with your Anki cards.
            Please check your connection and try again.
        </p>
        <button class="retry-btn" onclick="window.location.reload()">
            Try Again
        </button>
    </div>
</body>
</html>
            """
            return self.app.response_class(
                response=offline_html,
                status=200,
                mimetype='text/html'
            )
        
        @self.app.route('/pwa-info', methods=['GET'])
        def pwa_info():
            """Provide PWA installation info and status"""
            return jsonify({
                "name": "Anki Voice Study Buddy",
                "installable": True,
                "features": [
                    "Offline access to interface",
                    "Native app-like experience",
                    "Home screen installation",
                    "Background sync capabilities",
                    "Push notifications (future)"
                ],
                "requirements": [
                    "HTTPS connection (or localhost)",
                    "Web app manifest",
                    "Service worker",
                    "Installability criteria met"
                ],
                "shortcuts": [
                    {"name": "Start Review", "url": "/mobile?action=start"},
                    {"name": "Statistics", "url": "/mobile?action=stats"}
                ]
            })
        
        # Voice Streaming WebSocket Endpoints
        @self.app.route('/stream/start', methods=['POST'])
        def start_voice_stream():
            """Start WebSocket voice streaming session"""
            try:
                if not self.voice_stream_handler:
                    return jsonify({
                        "success": False,
                        "error": "Voice streaming not available - ELEVENLABS_API_KEY not configured"
                    }), 400
                
                # Start streaming session in background
                self.voice_stream_handler.start_streaming_session()
                
                return jsonify({
                    "success": True,
                    "message": "Voice streaming session started",
                    "websocket_url": self.voice_stream_handler.websocket_url,
                    "agent_id": self.voice_stream_handler.agent_id
                })
                
            except Exception as e:
                logger.error(f"Start voice stream error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @self.app.route('/stream/stop', methods=['POST'])
        def stop_voice_stream():
            """Stop WebSocket voice streaming session"""
            try:
                if not self.voice_stream_handler:
                    return jsonify({
                        "success": False,
                        "error": "Voice streaming not available"
                    }), 400
                
                self.voice_stream_handler.stop_streaming_session()
                
                return jsonify({
                    "success": True,
                    "message": "Voice streaming session stopped"
                })
                
            except Exception as e:
                logger.error(f"Stop voice stream error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @self.app.route('/stream/status', methods=['GET'])
        def stream_status():
            """Get voice streaming status"""
            try:
                if not self.voice_stream_handler:
                    return jsonify({
                        "success": True,
                        "available": False,
                        "connected": False,
                        "reason": "ELEVENLABS_API_KEY not configured"
                    })
                
                return jsonify({
                    "success": True,
                    "available": True,
                    "connected": self.voice_stream_handler.connected,
                    "reconnect_attempts": self.voice_stream_handler.reconnect_attempts,
                    "max_reconnect_attempts": self.voice_stream_handler.max_reconnect_attempts,
                    "websocket_url": self.voice_stream_handler.websocket_url
                })
                
            except Exception as e:
                logger.error(f"Stream status error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @self.app.route('/stream/send_audio', methods=['POST'])
        def send_audio_stream():
            """Send audio data via WebSocket streaming"""
            try:
                if not self.voice_stream_handler:
                    return jsonify({
                        "success": False,
                        "error": "Voice streaming not available"
                    }), 400
                
                # Get audio data from request
                audio_data = request.data
                if not audio_data:
                    return jsonify({
                        "success": False,
                        "error": "No audio data provided"
                    }), 400
                
                # Get audio format from headers
                audio_format = request.headers.get('X-Audio-Format', 'pcm')
                
                # Send audio asynchronously
                async def send_audio():
                    try:
                        await self.voice_stream_handler.stream_audio(audio_data, audio_format)
                        return True
                    except Exception as e:
                        logger.error(f"Audio streaming error: {e}")
                        return False
                
                # Run in thread pool to avoid blocking
                result = self.voice_stream_handler.executor.submit(
                    lambda: asyncio.run(send_audio())
                ).result(timeout=5)
                
                if result:
                    return jsonify({
                        "success": True,
                        "message": "Audio sent successfully",
                        "bytes_sent": len(audio_data)
                    })
                else:
                    return jsonify({
                        "success": False,
                        "error": "Failed to send audio"
                    }), 500
                
            except Exception as e:
                logger.error(f"Send audio stream error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @self.app.route('/stream/send_text', methods=['POST'])
        def send_text_stream():
            """Send text message via WebSocket streaming"""
            try:
                if not self.voice_stream_handler:
                    return jsonify({
                        "success": False,
                        "error": "Voice streaming not available"
                    }), 400
                
                data = request.json or {}
                text = data.get('text', '')
                context = data.get('context', {})
                
                if not text:
                    return jsonify({
                        "success": False,
                        "error": "No text provided"
                    }), 400
                
                # Send text asynchronously
                async def send_text():
                    try:
                        await self.voice_stream_handler.send_text(text, context)
                        return True
                    except Exception as e:
                        logger.error(f"Text streaming error: {e}")
                        return False
                
                # Run in thread pool
                result = self.voice_stream_handler.executor.submit(
                    lambda: asyncio.run(send_text())
                ).result(timeout=5)
                
                if result:
                    return jsonify({
                        "success": True,
                        "message": "Text sent successfully",
                        "text_length": len(text)
                    })
                else:
                    return jsonify({
                        "success": False,
                        "error": "Failed to send text"
                    }), 500
                
            except Exception as e:
                logger.error(f"Send text stream error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @self.app.route('/start_session', methods=['POST'])
        def start_session():
            """Start a new review session"""
            try:
                data = request.json or {}
                mode = ReviewMode(data.get('mode', 'normal'))
                
                # End previous session if exists
                if self.current_session:
                    self._end_session()
                
                # Create new session
                import uuid
                self.current_session = ReviewSession(
                    id=str(uuid.uuid4()),
                    start_time=datetime.now(),
                    mode=mode,
                    state=SessionState.ACTIVE
                )
                
                # Get initial statistics
                stats = self._get_session_start_stats()
                
                return jsonify({
                    "success": True,
                    "message": f"Starting {mode.value} review session. {stats['message']}",
                    "session_id": self.current_session.id,
                    "stats": stats
                })
            except Exception as e:
                logger.error(f"Error starting session: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/get_next_card', methods=['POST'])
        def get_next_card():
            """Get the next due card"""
            try:
                # Ensure session is active
                if not self.current_session or self.current_session.state != SessionState.ACTIVE:
                    return jsonify({
                        "success": False,
                        "message": "No active session. Please say 'start session' first."
                    })
                
                # Save review data for previous card if exists
                if self.current_card and hasattr(self, '_current_card_start_time'):
                    self._log_card_review()
                
                self.current_card = mw.col.sched.getCard()
                self.is_showing_answer = False
                self._current_card_start_time = datetime.now()
                self._hints_used = 0
                
                if not self.current_card:
                    summary = self._get_session_summary()
                    return jsonify({
                        "success": True,
                        "message": f"Congratulations! You've completed all your reviews. {summary}",
                        "cards_remaining": 0,
                        "session_complete": True
                    })
                
                # Get card content
                question = self.clean_html(self.current_card.question())
                card_stats = self._get_card_stats()
                
                # Check for difficult cards and offer help
                difficulty_hint = ""
                if self._is_difficult_card():
                    difficulty_hint = " This card has been challenging recently. Take your time, and remember you can ask for a hint if needed."
                
                return jsonify({
                    "success": True,
                    "message": f"{card_stats}. The question is: {question}{difficulty_hint}",
                    "question": question,
                    "cards_remaining": self._get_remaining_cards(),
                    "card_type": self.current_card.template()['name'],
                    "deck": mw.col.decks.name(self.current_card.did),
                    "tags": self.current_card.note().tags,
                    "streak": self.current_session.streak
                })
            except Exception as e:
                logger.error(f"Error getting next card: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/show_answer', methods=['POST'])
        def show_answer():
            """Reveal the answer to current card"""
            try:
                if not self.current_card:
                    return jsonify({
                        "success": False,
                        "message": "No card is currently loaded. Say 'next card' to get a card."
                    })
                
                if self.is_showing_answer:
                    return jsonify({
                        "success": True,
                        "message": "The answer is already showing. How well did you remember it? You can say: again, hard, good, or easy."
                    })
                
                answer = self.clean_html(self.current_card.answer())
                self.is_showing_answer = True
                
                # Provide rating guidance based on session mode
                rating_guidance = self._get_rating_guidance()
                
                return jsonify({
                    "success": True,
                    "message": f"The answer is: {answer}. {rating_guidance}",
                    "answer": answer,
                    "time_taken": (datetime.now() - self._current_card_start_time).total_seconds()
                })
            except Exception as e:
                logger.error(f"Error showing answer: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/answer_card', methods=['POST'])
        def answer_card():
            """Submit an answer rating"""
            try:
                data = request.json
                rating = data.get('rating', '').lower()
                
                if not self.current_card:
                    return jsonify({
                        "success": False,
                        "message": "No card to answer. Say 'next card' first."
                    })
                
                if not self.is_showing_answer:
                    return jsonify({
                        "success": False,
                        "message": "Please look at the answer first by saying 'show answer'."
                    })
                
                # Expanded rating mappings for natural language
                ease_map = {
                    # Standard ratings
                    'again': 1, 'hard': 2, 'good': 3, 'easy': 4,
                    # Natural variations
                    'repeat': 1, 'forgot': 1, 'missed': 1, 'no': 1, 'incorrect': 1,
                    'difficult': 2, 'struggled': 2, 'almost': 2, 'partial': 2,
                    'correct': 3, 'yes': 3, 'got it': 3, 'remembered': 3,
                    'perfect': 4, 'instant': 4, 'obvious': 4, 'simple': 4
                }
                
                ease = ease_map.get(rating)
                if not ease:
                    suggestions = "again (if you didn't remember), hard (if difficult), good (if you got it), or easy (if very simple)"
                    return jsonify({
                        "success": False,
                        "message": f"I didn't understand '{rating}'. Please say: {suggestions}"
                    })
                
                # Update streak
                if ease > 1:
                    self.current_session.streak += 1
                    self.current_session.correct_count += 1
                    if self.current_session.streak > self.current_session.best_streak:
                        self.current_session.best_streak = self.current_session.streak
                else:
                    self.current_session.streak = 0
                
                self.current_session.cards_reviewed += 1
                
                # Answer the card (unless in practice mode)
                if self.current_session.mode != ReviewMode.PRACTICE:
                    mw.col.sched.answerCard(self.current_card, ease)
                
                # Log the review
                self._log_card_review(rating)
                
                # Generate encouraging message
                message = self._generate_feedback_message(ease, rating)
                
                # Check for streak milestone
                if self.current_session.streak > 0 and self.current_session.streak % self.config.streak_encouragement_threshold == 0:
                    message += f" You're on a {self.current_session.streak} card streak! Keep it up!"
                
                return jsonify({
                    "success": True,
                    "message": message,
                    "streak": self.current_session.streak,
                    "total_reviewed": self.current_session.cards_reviewed,
                    "accuracy": round(self.current_session.correct_count / self.current_session.cards_reviewed * 100)
                })
            except Exception as e:
                logger.error(f"Error answering card: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/get_hint', methods=['POST'])
        def get_hint():
            """Provide a hint for the current card"""
            try:
                if not self.current_card:
                    return jsonify({
                        "success": False,
                        "message": "No card loaded. Say 'next card' first."
                    })
                
                if self.is_showing_answer:
                    return jsonify({
                        "success": False,
                        "message": "The answer is already showing. No need for a hint now!"
                    })
                
                # Track hint usage
                self._hints_used += 1
                
                # Get hint based on hint number
                hint = self._generate_progressive_hint(self._hints_used)
                
                return jsonify({
                    "success": True,
                    "message": hint,
                    "hint_number": self._hints_used
                })
            except Exception as e:
                logger.error(f"Error generating hint: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/explain_concept', methods=['POST'])
        def explain_concept():
            """Provide a detailed explanation of the current card's concept"""
            try:
                if not self.current_card:
                    return jsonify({
                        "success": False,
                        "message": "No card loaded to explain."
                    })
                
                explanation = self._generate_concept_explanation()
                
                return jsonify({
                    "success": True,
                    "message": explanation,
                    "explanation": explanation
                })
            except Exception as e:
                logger.error(f"Error explaining concept: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/get_related_cards', methods=['POST'])
        def get_related_cards():
            """Find cards related to current topic"""
            try:
                if not self.current_card:
                    return jsonify({
                        "success": False,
                        "message": "No card loaded to find related cards."
                    })
                
                related = self._find_related_cards()
                
                return jsonify({
                    "success": True,
                    "message": f"Found {related['count']} related cards. {related['summary']}",
                    "related_cards": related
                })
            except Exception as e:
                logger.error(f"Error finding related cards: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/pause_session', methods=['POST'])
        def pause_session():
            """Pause the review session"""
            try:
                if not self.current_session or self.current_session.state != SessionState.ACTIVE:
                    return jsonify({
                        "success": False,
                        "message": "No active session to pause."
                    })
                
                self.current_session.state = SessionState.PAUSED
                self.current_session.last_pause_time = datetime.now()
                
                return jsonify({
                    "success": True,
                    "message": "Session paused. Say 'resume' when you're ready to continue.",
                    "cards_reviewed": self.current_session.cards_reviewed
                })
            except Exception as e:
                logger.error(f"Error pausing session: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/resume_session', methods=['POST'])
        def resume_session():
            """Resume a paused session"""
            try:
                if not self.current_session:
                    return jsonify({
                        "success": False,
                        "message": "No session to resume. Say 'start session' to begin."
                    })
                
                if self.current_session.state != SessionState.PAUSED:
                    return jsonify({
                        "success": False,
                        "message": "Session is not paused."
                    })
                
                # Calculate pause duration
                if self.current_session.last_pause_time:
                    pause_duration = datetime.now() - self.current_session.last_pause_time
                    self.current_session.paused_duration += pause_duration
                
                self.current_session.state = SessionState.ACTIVE
                
                return jsonify({
                    "success": True,
                    "message": "Welcome back! Let's continue reviewing. Say 'next card' when ready.",
                    "cards_reviewed": self.current_session.cards_reviewed,
                    "current_streak": self.current_session.streak
                })
            except Exception as e:
                logger.error(f"Error resuming session: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/end_session', methods=['POST'])
        def end_session():
            """End the current review session"""
            try:
                if not self.current_session:
                    return jsonify({
                        "success": False,
                        "message": "No active session to end."
                    })
                
                summary = self._get_session_summary()
                self._end_session()
                
                return jsonify({
                    "success": True,
                    "message": f"Session ended. {summary}",
                    "summary": summary
                })
            except Exception as e:
                logger.error(f"Error ending session: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/get_statistics', methods=['POST'])
        def get_statistics():
            """Get detailed review statistics"""
            try:
                data = request.json or {}
                period = data.get('period', 'today')  # today, week, month, all
                
                stats = self._get_detailed_statistics(period)
                
                return jsonify({
                    "success": True,
                    "message": stats['summary'],
                    "stats": stats
                })
            except Exception as e:
                logger.error(f"Error getting statistics: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/set_review_mode', methods=['POST'])
        def set_review_mode():
            """Switch between different review modes"""
            try:
                data = request.json
                mode = data.get('mode', 'normal')
                
                if mode not in [m.value for m in ReviewMode]:
                    return jsonify({
                        "success": False,
                        "message": f"Unknown mode '{mode}'. Available modes: normal, speed, focus, practice"
                    })
                
                if self.current_session:
                    self.current_session.mode = ReviewMode(mode)
                    
                mode_descriptions = {
                    ReviewMode.NORMAL: "Standard review with full features",
                    ReviewMode.SPEED: "Quick reviews with time pressure",
                    ReviewMode.FOCUS: "Serious mode with no hints and stricter ratings",
                    ReviewMode.PRACTICE: "Practice mode - reviews don't affect scheduling"
                }
                
                return jsonify({
                    "success": True,
                    "message": f"Switched to {mode} mode. {mode_descriptions[ReviewMode(mode)]}",
                    "mode": mode
                })
            except Exception as e:
                logger.error(f"Error setting review mode: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
    
    # Helper methods
    
    # Webhook conversation flow helper methods
    def _handle_start_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle session start from conversation webhook"""
        try:
            mode = data.get('mode', 'normal')
            if mode not in [m.value for m in ReviewMode]:
                mode = 'normal'
            
            # End previous session if exists
            if self.current_session:
                self._end_session()
            
            # Create new session
            import uuid
            self.current_session = ReviewSession(
                id=str(uuid.uuid4()),
                start_time=datetime.now(),
                mode=ReviewMode(mode),
                state=SessionState.ACTIVE
            )
            
            # Get initial statistics
            stats = self._get_session_start_stats()
            
            return jsonify({
                "success": True,
                "message": f"Great! I've started a {mode} review session. {stats['message']} Let's begin reviewing!",
                "session_id": self.current_session.id,
                "stats": stats,
                "next_action": "say 'next card' to get your first question"
            })
        except Exception as e:
            logger.error(f"Error starting session: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_next_card(self) -> Dict[str, Any]:
        """Handle next card request from conversation"""
        try:
            # Ensure session is active
            if not self.current_session or self.current_session.state != SessionState.ACTIVE:
                return jsonify({
                    "success": False,
                    "message": "No active session. Please say 'start session' first to begin reviewing."
                })
            
            # Save review data for previous card if exists
            if self.current_card and hasattr(self, '_current_card_start_time'):
                self._log_card_review()
            
            self.current_card = mw.col.sched.getCard()
            self.is_showing_answer = False
            self._current_card_start_time = datetime.now()
            self._hints_used = 0
            
            if not self.current_card:
                summary = self._get_session_summary()
                return jsonify({
                    "success": True,
                    "message": f"Congratulations! You've completed all your reviews for now. {summary}",
                    "cards_remaining": 0,
                    "session_complete": True
                })
            
            # Get card content
            question = self.clean_html(self.current_card.question())
            card_stats = self._get_card_stats()
            
            # Check for difficult cards and offer help
            difficulty_hint = ""
            if self._is_difficult_card():
                difficulty_hint = " This card has been challenging recently. Take your time, and remember you can ask for a hint if needed."
            
            return jsonify({
                "success": True,
                "message": f"{card_stats}. The question is: {question}{difficulty_hint}",
                "question": question,
                "cards_remaining": self._get_remaining_cards(),
                "card_type": self.current_card.template()['name'],
                "deck": mw.col.decks.name(self.current_card.did),
                "streak": self.current_session.streak,
                "next_action": "think about the answer, then say 'show answer' when ready"
            })
        except Exception as e:
            logger.error(f"Error getting next card: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_show_answer(self) -> Dict[str, Any]:
        """Handle show answer request from conversation"""
        try:
            if not self.current_card:
                return jsonify({
                    "success": False,
                    "message": "No card is currently loaded. Say 'next card' to get a card first."
                })
            
            if self.is_showing_answer:
                return jsonify({
                    "success": True,
                    "message": "The answer is already showing. How well did you remember it? You can say: again, hard, good, or easy."
                })
            
            answer = self.clean_html(self.current_card.answer())
            self.is_showing_answer = True
            
            # Provide rating guidance based on session mode
            rating_guidance = self._get_rating_guidance()
            
            return jsonify({
                "success": True,
                "message": f"The answer is: {answer}. {rating_guidance}",
                "answer": answer,
                "time_taken": (datetime.now() - self._current_card_start_time).total_seconds(),
                "next_action": "rate how well you remembered: again, hard, good, or easy"
            })
        except Exception as e:
            logger.error(f"Error showing answer: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_answer_card(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Handle card rating from conversation"""
        try:
            rating = entities.get('rating', '').lower() if entities else ''
            
            if not self.current_card:
                return jsonify({
                    "success": False,
                    "message": "No card to answer. Say 'next card' first."
                })
            
            if not self.is_showing_answer:
                return jsonify({
                    "success": False,
                    "message": "Please look at the answer first by saying 'show answer'."
                })
            
            # Expanded rating mappings for natural language
            ease_map = {
                # Standard ratings
                'again': 1, 'hard': 2, 'good': 3, 'easy': 4,
                # Natural variations
                'repeat': 1, 'forgot': 1, 'missed': 1, 'no': 1, 'incorrect': 1, 'wrong': 1,
                'difficult': 2, 'struggled': 2, 'almost': 2, 'partial': 2, 'tough': 2,
                'correct': 3, 'yes': 3, 'got it': 3, 'remembered': 3, 'right': 3, 'ok': 3,
                'perfect': 4, 'instant': 4, 'obvious': 4, 'simple': 4, 'trivial': 4
            }
            
            ease = ease_map.get(rating)
            if not ease:
                suggestions = "again (if you didn't remember), hard (if difficult), good (if you got it), or easy (if very simple)"
                return jsonify({
                    "success": False,
                    "message": f"I didn't understand '{rating}'. Please say: {suggestions}",
                    "valid_ratings": list(ease_map.keys())
                })
            
            # Update streak
            if ease > 1:
                self.current_session.streak += 1
                self.current_session.correct_count += 1
                if self.current_session.streak > self.current_session.best_streak:
                    self.current_session.best_streak = self.current_session.streak
            else:
                self.current_session.streak = 0
            
            self.current_session.cards_reviewed += 1
            
            # Answer the card (unless in practice mode)
            if self.current_session.mode != ReviewMode.PRACTICE:
                mw.col.sched.answerCard(self.current_card, ease)
            
            # Log the review
            self._log_card_review(rating)
            
            # Generate encouraging message
            message = self._generate_feedback_message(ease, rating)
            
            # Check for streak milestone
            if self.current_session.streak > 0 and self.current_session.streak % self.config.streak_encouragement_threshold == 0:
                message += f" You're on a {self.current_session.streak} card streak! Keep it up!"
            
            return jsonify({
                "success": True,
                "message": message,
                "streak": self.current_session.streak,
                "total_reviewed": self.current_session.cards_reviewed,
                "accuracy": round(self.current_session.correct_count / self.current_session.cards_reviewed * 100),
                "next_action": "say 'next card' to continue"
            })
        except Exception as e:
            logger.error(f"Error answering card: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_get_hint(self) -> Dict[str, Any]:
        """Handle hint request from conversation"""
        try:
            if not self.current_card:
                return jsonify({
                    "success": False,
                    "message": "No card loaded. Say 'next card' first."
                })
            
            if self.is_showing_answer:
                return jsonify({
                    "success": False,
                    "message": "The answer is already showing. No need for a hint now!"
                })
            
            # Track hint usage
            self._hints_used += 1
            
            # Get hint based on hint number
            hint = self._generate_progressive_hint(self._hints_used)
            
            return jsonify({
                "success": True,
                "message": hint,
                "hint_number": self._hints_used,
                "next_action": "keep thinking, ask for another hint, or say 'show answer'"
            })
        except Exception as e:
            logger.error(f"Error generating hint: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_pause_session(self) -> Dict[str, Any]:
        """Handle session pause from conversation"""
        try:
            if not self.current_session or self.current_session.state != SessionState.ACTIVE:
                return jsonify({
                    "success": False,
                    "message": "No active session to pause."
                })
            
            self.current_session.state = SessionState.PAUSED
            self.current_session.last_pause_time = datetime.now()
            
            return jsonify({
                "success": True,
                "message": "Session paused. Say 'resume' when you're ready to continue studying.",
                "cards_reviewed": self.current_session.cards_reviewed,
                "next_action": "say 'resume' to continue"
            })
        except Exception as e:
            logger.error(f"Error pausing session: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_resume_session(self) -> Dict[str, Any]:
        """Handle session resume from conversation"""
        try:
            if not self.current_session:
                return jsonify({
                    "success": False,
                    "message": "No session to resume. Say 'start session' to begin."
                })
            
            if self.current_session.state != SessionState.PAUSED:
                return jsonify({
                    "success": False,
                    "message": "Session is not paused."
                })
            
            # Calculate pause duration
            if self.current_session.last_pause_time:
                pause_duration = datetime.now() - self.current_session.last_pause_time
                self.current_session.paused_duration += pause_duration
            
            self.current_session.state = SessionState.ACTIVE
            
            return jsonify({
                "success": True,
                "message": "Welcome back! Let's continue reviewing. Say 'next card' when you're ready.",
                "cards_reviewed": self.current_session.cards_reviewed,
                "current_streak": self.current_session.streak,
                "next_action": "say 'next card' to continue"
            })
        except Exception as e:
            logger.error(f"Error resuming session: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_end_session(self) -> Dict[str, Any]:
        """Handle session end from conversation"""
        try:
            if not self.current_session:
                return jsonify({
                    "success": False,
                    "message": "No active session to end."
                })
            
            summary = self._get_session_summary()
            self._end_session()
            
            return jsonify({
                "success": True,
                "message": f"Great work! Session ended. {summary} Thanks for studying with me!",
                "summary": summary,
                "next_action": "say 'start session' to begin a new review session"
            })
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle statistics request from conversation"""
        try:
            period = data.get('period', 'current')
            
            if period == 'current' and self.current_session:
                accuracy = 0
                if self.current_session.cards_reviewed > 0:
                    accuracy = round(self.current_session.correct_count / self.current_session.cards_reviewed * 100)
                
                message = f"In this session: {self.current_session.cards_reviewed} cards reviewed, "
                message += f"{accuracy}% accuracy, {self.current_session.streak} current streak, "
                message += f"{self.current_session.best_streak} best streak"
                
                return jsonify({
                    "success": True,
                    "message": message,
                    "current_session": True,
                    "stats": {
                        "cards_reviewed": self.current_session.cards_reviewed,
                        "accuracy": accuracy,
                        "streak": self.current_session.streak,
                        "best_streak": self.current_session.best_streak
                    }
                })
            else:
                stats = self._get_detailed_statistics(period)
                return jsonify({
                    "success": True,
                    "message": stats['summary'],
                    "stats": stats
                })
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_explain_concept(self) -> Dict[str, Any]:
        """Handle concept explanation request from conversation"""
        try:
            if not self.current_card:
                return jsonify({
                    "success": False,
                    "message": "No card loaded to explain."
                })
            
            explanation = self._generate_concept_explanation()
            
            return jsonify({
                "success": True,
                "message": explanation,
                "explanation": explanation
            })
        except Exception as e:
            logger.error(f"Error explaining concept: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _handle_get_related_cards(self) -> Dict[str, Any]:
        """Handle related cards request from conversation"""
        try:
            if not self.current_card:
                return jsonify({
                    "success": False,
                    "message": "No card loaded to find related cards."
                })
            
            related = self._find_related_cards()
            
            return jsonify({
                "success": True,
                "message": f"Found {related['count']} related cards. {related['summary']}",
                "related_cards": related
            })
        except Exception as e:
            logger.error(f"Error finding related cards: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _detect_intent_from_message(self, user_message: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback intent detection from user message"""
        try:
            message = user_message.lower().strip()
            
            # Intent detection patterns
            intent_patterns = {
                'next_card': ['next', 'continue', 'another', 'more'],
                'show_answer': ['answer', 'solution', 'reveal', 'show', 'tell me'],
                'get_hint': ['hint', 'help', 'clue', 'tip'],
                'rate_card': ['again', 'hard', 'good', 'easy', 'difficult', 'correct', 'wrong'],
                'pause': ['pause', 'stop', 'break', 'wait'],
                'resume': ['resume', 'continue', 'back', 'unpause'],
                'statistics': ['stats', 'statistics', 'progress', 'how am i doing'],
                'end_session': ['end', 'finish', 'done', 'quit', 'stop session']
            }
            
            # Check for intent patterns
            for intent, patterns in intent_patterns.items():
                if any(pattern in message for pattern in patterns):
                    if intent == 'next_card':
                        return self._handle_next_card()
                    elif intent == 'show_answer':
                        return self._handle_show_answer()
                    elif intent == 'get_hint':
                        return self._handle_get_hint()
                    elif intent == 'rate_card':
                        # Extract rating from message
                        entities['rating'] = message
                        return self._handle_answer_card(entities)
                    elif intent == 'pause':
                        return self._handle_pause_session()
                    elif intent == 'resume':
                        return self._handle_resume_session()
                    elif intent == 'statistics':
                        return self._handle_get_statistics({})
                    elif intent == 'end_session':
                        return self._handle_end_session()
            
            # No intent detected
            return jsonify({
                "success": False,
                "message": "I didn't understand that. Try saying: 'next card', 'show answer', 'get hint', or 'statistics'",
                "available_commands": ["next card", "show answer", "hint", "again/hard/good/easy", "pause", "statistics", "end session"]
            })
            
        except Exception as e:
            logger.error(f"Error detecting intent: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _process_speech_command(self, transcript: str) -> Dict[str, Any]:
        """Process direct speech recognition results"""
        try:
            # Use the same intent detection logic
            return self._detect_intent_from_message(transcript, {})
        except Exception as e:
            logger.error(f"Error processing speech: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def clean_html(self, text: str) -> str:
        """Convert HTML to clean text for speech"""
        # Handle cloze deletions
        text = re.sub(r'\{\{c\d+::(.*?)\}\}', r'\1', text)
        
        # Convert to plain text
        plain_text = self.h2t.handle(text).strip()
        
        # Clean up common artifacts
        plain_text = re.sub(r'\s+', ' ', plain_text)  # Multiple spaces
        plain_text = re.sub(r'&nbsp;', ' ', plain_text)  # Non-breaking spaces
        
        return plain_text
    
    def _get_card_stats(self) -> str:
        """Get speaking-friendly card statistics"""
        if self.current_card.type == 0:
            return "Here's a new card"
        elif self.current_card.type == 1:
            return "This is a learning card"
        else:
            interval = self.current_card.ivl
            if interval == 1:
                return "Review card from yesterday"
            elif interval < 7:
                return f"Review card from {interval} days ago"
            elif interval < 21:
                weeks = interval // 7
                return f"Review card from about {weeks} week{'s' if weeks > 1 else ''} ago"
            elif interval < 365:
                months = interval // 30
                return f"Mature card from about {months} month{'s' if months > 1 else ''} ago"
            else:
                years = interval // 365
                return f"Very mature card from about {years} year{'s' if years > 1 else ''} ago"
    
    def _get_remaining_cards(self) -> int:
        """Get count of remaining cards"""
        counts = mw.col.sched.counts()
        return sum(counts)
    
    def _is_difficult_card(self) -> bool:
        """Check if current card has been difficult recently"""
        if not self.current_card:
            return False
        
        # Check recent reviews
        reviews = mw.col.db.all(
            "SELECT ease FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT 5",
            self.current_card.id
        )
        
        if not reviews:
            return False
        
        # If more than threshold of recent reviews were "again"
        again_count = sum(1 for r in reviews if r[0] == 1)
        return again_count / len(reviews) > self.config.difficulty_threshold
    
    def _generate_progressive_hint(self, hint_number: int) -> str:
        """Generate hints that get progressively more helpful"""
        note = self.current_card.note()
        fields = {name: self.clean_html(value) for name, value in note.items()}
        answer = fields.get('Back', fields.get('Answer', ''))
        
        if hint_number == 1:
            # First hint: general category or first letter
            if answer:
                first_letter = answer.strip()[0] if answer.strip() else ""
                word_count = len(answer.split())
                return f"The answer starts with '{first_letter}' and has {word_count} word{'s' if word_count != 1 else ''}"
            return "Think about the key concept this card is testing"
        
        elif hint_number == 2:
            # Second hint: more structural information
            if len(answer) > 20:
                words = answer.split()
                if len(words) > 3:
                    return f"The answer begins with '{' '.join(words[:2])}...'"
            return f"The answer is {len(answer)} characters long"
        
        elif hint_number >= 3:
            # Third+ hint: significant portion of answer
            if len(answer) > 10:
                reveal_length = len(answer) // 2
                return f"Here's the first half: '{answer[:reveal_length]}...'"
            return "One more try before I show you the answer!"
        
        return "No more hints available. Try your best!"
    
    def _generate_concept_explanation(self) -> str:
        """Generate an explanation for the current card's concept"""
        note = self.current_card.note()
        fields = {name: self.clean_html(value) for name, value in note.items()}
        
        # Check for explanation field
        explanation = fields.get('Explanation', fields.get('Extra', ''))
        if explanation:
            return f"Here's more information: {explanation}"
        
        # Generate basic explanation based on card content
        question = fields.get('Front', fields.get('Question', ''))
        answer = fields.get('Back', fields.get('Answer', ''))
        
        # Get related tags for context
        tags = note.tags
        tag_context = f" This card is tagged with: {', '.join(tags)}" if tags else ""
        
        return f"This card asks about '{question}' and the answer is '{answer}'.{tag_context} Try to understand the connection between the question and answer."
    
    def _find_related_cards(self) -> Dict[str, Any]:
        """Find cards related to the current one"""
        if not self.current_card:
            return {"count": 0, "summary": "No card loaded"}
        
        note = self.current_card.note()
        tags = note.tags
        
        related_cards = []
        
        # Find by tags
        if tags:
            tag_query = " or ".join([f"tag:{tag}" for tag in tags])
            tag_cards = mw.col.find_cards(tag_query)
            related_cards.extend(tag_cards)
        
        # Find by deck
        deck_cards = mw.col.find_cards(f"deck:{mw.col.decks.name(self.current_card.did)}")
        related_cards.extend(deck_cards)
        
        # Remove current card and duplicates
        related_cards = list(set(related_cards))
        if self.current_card.id in related_cards:
            related_cards.remove(self.current_card.id)
        
        # Get some sample content
        samples = []
        for cid in related_cards[:3]:
            card = mw.col.get_card(cid)
            if card:
                samples.append(self.clean_html(card.question())[:50] + "...")
        
        summary = "You might want to review: " + ", ".join(samples) if samples else "in the same deck"
        
        return {
            "count": len(related_cards),
            "summary": summary,
            "tag_matches": len([c for c in related_cards if any(tag in mw.col.get_card(c).note().tags for tag in tags)]) if tags else 0,
            "deck_matches": len(deck_cards)
        }
    
    def _get_rating_guidance(self) -> str:
        """Provide mode-appropriate rating guidance"""
        if self.current_session.mode == ReviewMode.FOCUS:
            return "Rate honestly: 'again' if any part was forgotten, 'hard' if you struggled, 'good' only if you recalled it completely, 'easy' if it was trivial."
        elif self.current_session.mode == ReviewMode.SPEED:
            return "Quick rating: again, hard, good, or easy!"
        else:
            return "How well did you remember? Say 'again' if you forgot, 'hard' if difficult, 'good' if you got it, or 'easy' if it was simple."
    
    def _generate_feedback_message(self, ease: int, rating: str) -> str:
        """Generate encouraging feedback based on rating"""
        messages = {
            1: [
                f"No worries! Marked as '{rating}'. Everyone forgets sometimes.",
                f"That's okay! We'll see this one again soon.",
                f"Don't worry about it. Repetition is how we learn!"
            ],
            2: [
                f"Good effort! Marked as '{rating}'.",
                f"Nice try! You're getting there.",
                f"Keep working on it. You're making progress!"
            ],
            3: [
                f"Well done! Marked as '{rating}'.",
                f"Great job! You got it!",
                f"Excellent! Your memory is working well."
            ],
            4: [
                f"Perfect! Marked as '{rating}'.",
                f"Outstanding! That was easy for you.",
                f"Brilliant! You've mastered this one."
            ]
        }
        
        import random
        return random.choice(messages[ease])
    
    def _get_session_start_stats(self) -> Dict[str, Any]:
        """Get statistics when starting a session"""
        counts = mw.col.sched.counts()
        total = sum(counts)
        
        message_parts = []
        if counts[0] > 0:
            message_parts.append(f"{counts[0]} new")
        if counts[1] > 0:
            message_parts.append(f"{counts[1]} learning")
        if counts[2] > 0:
            message_parts.append(f"{counts[2]} review")
        
        cards_text = " and ".join(message_parts) + f" card{'s' if total != 1 else ''}"
        
        return {
            "message": f"You have {cards_text} waiting",
            "new": counts[0],
            "learning": counts[1],
            "review": counts[2],
            "total": total
        }
    
    def _get_session_summary(self) -> str:
        """Generate session summary"""
        if not self.current_session:
            return "No session data available."
        
        duration = datetime.now() - self.current_session.start_time - self.current_session.paused_duration
        minutes = int(duration.total_seconds() / 60)
        
        accuracy = 0
        if self.current_session.cards_reviewed > 0:
            accuracy = round(self.current_session.correct_count / self.current_session.cards_reviewed * 100)
        
        summary_parts = [
            f"You reviewed {self.current_session.cards_reviewed} cards in {minutes} minutes",
            f"with {accuracy}% accuracy",
            f"Your best streak was {self.current_session.best_streak} cards"
        ]
        
        # Add mode-specific feedback
        if self.current_session.mode == ReviewMode.FOCUS:
            summary_parts.append("Great focus session!")
        elif self.current_session.mode == ReviewMode.SPEED:
            cards_per_minute = self.current_session.cards_reviewed / max(minutes, 1)
            summary_parts.append(f"Speed: {cards_per_minute:.1f} cards per minute")
        
        return ". ".join(summary_parts) + "."
    
    def _get_detailed_statistics(self, period: str) -> Dict[str, Any]:
        """Get detailed statistics for a time period"""
        # Calculate time boundaries
        now = datetime.now()
        if period == 'today':
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_time = now - timedelta(days=7)
        elif period == 'month':
            start_time = now - timedelta(days=30)
        else:  # all time
            start_time = datetime(2000, 1, 1)
        
        # Query review log
        reviews = self.db.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN user_rating NOT IN ('again', 'repeat', 'forgot') THEN 1 ELSE 0 END),
                   AVG(time_to_answer_seconds),
                   SUM(hints_used)
            FROM review_log
            WHERE review_time >= ?
        ''', (start_time,)).fetchone()
        
        total_reviews = reviews[0] or 0
        correct_reviews = reviews[1] or 0
        avg_time = reviews[2] or 0
        total_hints = reviews[3] or 0
        
        # Query sessions
        sessions = self.db.execute('''
            SELECT COUNT(*), 
                   SUM(cards_reviewed),
                   AVG(cards_reviewed),
                   MAX(best_streak)
            FROM sessions
            WHERE start_time >= ?
        ''', (start_time,)).fetchone()
        
        total_sessions = sessions[0] or 0
        
        # Build summary
        if total_reviews == 0:
            summary = f"No reviews found for {period}."
        else:
            accuracy = round(correct_reviews / total_reviews * 100)
            summary = f"In the past {period}, you reviewed {total_reviews} cards with {accuracy}% accuracy"
            
            if avg_time > 0:
                summary += f", averaging {avg_time:.1f} seconds per card"
            
            if total_hints > 0:
                summary += f", using {total_hints} hints"
        
        return {
            "summary": summary,
            "period": period,
            "total_reviews": total_reviews,
            "correct_reviews": correct_reviews,
            "accuracy": round(correct_reviews / total_reviews * 100) if total_reviews > 0 else 0,
            "average_time": avg_time,
            "total_hints": total_hints,
            "total_sessions": total_sessions,
            "max_streak": sessions[3] or 0
        }
    
    def _log_card_review(self, rating: str = None):
        """Log card review to database"""
        if not self.current_card or not self.current_session:
            return
        
        try:
            question = self.clean_html(self.current_card.question())
            answer = self.clean_html(self.current_card.answer())
            time_taken = (datetime.now() - self._current_card_start_time).total_seconds()
            
            self.db.execute('''
                INSERT INTO review_log 
                (session_id, card_id, question, answer, user_rating, review_time, time_to_answer_seconds, hints_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.current_session.id,
                self.current_card.id,
                question[:200],  # Truncate for storage
                answer[:200],
                rating,
                datetime.now(),
                time_taken,
                self._hints_used
            ))
            self.db.commit()
        except Exception as e:
            logger.error(f"Error logging card review: {str(e)}")
    
    def _end_session(self):
        """End and save session to database"""
        if not self.current_session:
            return
        
        try:
            total_duration = (datetime.now() - self.current_session.start_time - self.current_session.paused_duration).total_seconds()
            
            self.db.execute('''
                INSERT INTO sessions 
                (id, start_time, end_time, mode, cards_reviewed, correct_count, best_streak, total_duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.current_session.id,
                self.current_session.start_time,
                datetime.now(),
                self.current_session.mode.value,
                self.current_session.cards_reviewed,
                self.current_session.correct_count,
                self.current_session.best_streak,
                int(total_duration)
            ))
            self.db.commit()
            
            self.current_session = None
            self.current_card = None
            self.is_showing_answer = False
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
    
    def start(self):
        """Start the Flask server in a background thread"""
        def run_server():
            try:
                logger.info(f"Starting voice review server on {self.config.host}:{self.config.port}")
                self.app.run(host=self.config.host, port=self.config.port, debug=False, use_reloader=False)
            except Exception as e:
                logger.error(f"Server error: {str(e)}")
                showWarning(f"Failed to start voice review server: {str(e)}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Wait a moment and check if server started
        import time
        time.sleep(1)
        
        # Test server health
        try:
            import requests
            response = requests.get(f"http://{self.config.host}:{self.config.port}/health", timeout=2)
            if response.status_code == 200:
                showInfo(f"Voice Review Server started successfully on http://{self.config.host}:{self.config.port}")
            else:
                showWarning("Voice Review Server started but health check failed")
        except:
            showWarning("Voice Review Server may not have started correctly")
    
    def stop(self):
        """Stop the server and cleanup resources"""
        # Stop WebSocket streaming session
        if self.voice_stream_handler:
            try:
                self.voice_stream_handler.stop_streaming_session()
                # Shutdown executor
                self.voice_stream_handler.executor.shutdown(wait=True)
                logger.info("Voice streaming handler stopped")
            except Exception as e:
                logger.error(f"Error stopping voice stream handler: {e}")
        
        if hasattr(self, 'server_thread'):
            # Flask doesn't have a clean shutdown in development mode
            # In production, you'd use a proper WSGI server
            logger.info("Voice review server stopping...")

# Global instances
voice_server: Optional[AnkiVoiceReviewServer] = None
voice_assistant_widget: Optional[VoiceAssistantWidget] = None
voice_assistant_dialog: Optional[VoiceAssistantDialog] = None

def start_voice_server():
    """Initialize and start the voice review server"""
    global voice_server
    if not voice_server:
        voice_server = AnkiVoiceReviewServer()
        voice_server.start()
        # Store reference in main window for VoiceStreamHandler access
        mw.voice_server = voice_server
    else:
        showInfo("Voice Review Server is already running")

def stop_voice_server():
    """Stop the voice review server"""
    global voice_server
    if voice_server:
        voice_server.stop()
        voice_server = None
        # Clear reference from main window
        if hasattr(mw, 'voice_server'):
            delattr(mw, 'voice_server')
        showInfo("Voice Review Server stopped")
    else:
        showInfo("Voice Review Server is not running")

# Global widget manager instance
widget_manager = WidgetManager()

def add_voice_assistant_dock():
    """Add the voice assistant to Anki's interface using enhanced widget manager"""
    global voice_assistant_widget, widget_manager
    if not voice_assistant_widget:
        # Use widget manager to create preferred widget type
        preferred_type = widget_manager.get_preference('widget_type', 'sidebar')
        voice_assistant_widget = widget_manager.create_widget(preferred_type, parent=mw)

def toggle_voice_assistant(show):
    """Toggle voice assistant dock visibility using widget manager"""
    global widget_manager
    if show:
        widget_manager.toggle_widget()
    else:
        # Close all active widgets
        widget_manager.close_all_widgets()

def show_voice_assistant_dialog():
    """Show voice assistant in a floating dialog using enhanced integration"""
    global widget_manager
    # Create or toggle popup widget
    if widget_manager.is_widget_active('popup'):
        widget_manager.close_widget('popup')
    else:
        widget_manager.create_widget('popup', parent=mw)

def switch_widget_type(widget_type: str):
    """Switch widget type globally"""
    global widget_manager
    widget_manager.switch_widget_type(widget_type)

def show_widget_preferences_dialog():
    """Show widget preferences configuration dialog"""
    global widget_manager
    
    dialog = QDialog(mw)
    dialog.setWindowTitle("Widget Preferences")
    dialog.setMinimumSize(400, 300)
    layout = QVBoxLayout(dialog)
    
    # Widget type selection
    type_group = QGroupBox("Widget Type")
    type_layout = QVBoxLayout(type_group)
    
    sidebar_radio = QRadioButton("Sidebar (Docked)")
    floating_radio = QRadioButton("Floating Window")
    popup_radio = QRadioButton("Popup Dialog")
    
    current_type = widget_manager.get_preference('widget_type', 'sidebar')
    if current_type == 'sidebar':
        sidebar_radio.setChecked(True)
    elif current_type == 'floating':
        floating_radio.setChecked(True)
    elif current_type == 'popup':
        popup_radio.setChecked(True)
    
    type_layout.addWidget(sidebar_radio)
    type_layout.addWidget(floating_radio)
    type_layout.addWidget(popup_radio)
    layout.addWidget(type_group)
    
    # Dock area selection (for sidebar)
    dock_group = QGroupBox("Dock Area (Sidebar Only)")
    dock_layout = QVBoxLayout(dock_group)
    
    dock_combo = QComboBox()
    dock_combo.addItems(["left", "right", "bottom"])
    dock_combo.setCurrentText(widget_manager.get_preference('dock_area', 'right'))
    
    dock_layout.addWidget(dock_combo)
    layout.addWidget(dock_group)
    
    # Auto-start option
    auto_start_check = QCheckBox("Auto-start widget")
    auto_start_check.setChecked(widget_manager.get_preference('auto_start', True))
    layout.addWidget(auto_start_check)
    
    # Size preferences
    size_group = QGroupBox("Default Size")
    size_layout = QHBoxLayout(size_group)
    
    width_spin = QSpinBox()
    width_spin.setRange(300, 1000)
    width_spin.setValue(widget_manager.get_preference('size', {}).get('width', 350))
    
    height_spin = QSpinBox()
    height_spin.setRange(400, 1000)
    height_spin.setValue(widget_manager.get_preference('size', {}).get('height', 500))
    
    size_layout.addWidget(QLabel("Width:"))
    size_layout.addWidget(width_spin)
    size_layout.addWidget(QLabel("Height:"))
    size_layout.addWidget(height_spin)
    layout.addWidget(size_group)
    
    # Buttons
    button_layout = QHBoxLayout()
    apply_btn = QPushButton("Apply")
    ok_btn = QPushButton("OK")
    cancel_btn = QPushButton("Cancel")
    
    def apply_preferences():
        # Determine widget type
        if sidebar_radio.isChecked():
            widget_type = 'sidebar'
        elif floating_radio.isChecked():
            widget_type = 'floating'
        else:
            widget_type = 'popup'
        
        # Save preferences
        widget_manager.set_preference('widget_type', widget_type)
        widget_manager.set_preference('dock_area', dock_combo.currentText())
        widget_manager.set_preference('auto_start', auto_start_check.isChecked())
        widget_manager.set_preference('size', {
            'width': width_spin.value(),
            'height': height_spin.value()
        })
        
        # Switch widget type if needed
        if widget_type != current_type:
            widget_manager.switch_widget_type(widget_type)
    
    apply_btn.clicked.connect(apply_preferences)
    ok_btn.clicked.connect(lambda: (apply_preferences(), dialog.accept()))
    cancel_btn.clicked.connect(dialog.reject)
    
    button_layout.addWidget(apply_btn)
    button_layout.addWidget(ok_btn)
    button_layout.addWidget(cancel_btn)
    layout.addLayout(button_layout)
    
    dialog.exec()

def open_config_dialog():
    """Open configuration dialog"""
    dialog = QDialog(mw)
    dialog.setWindowTitle("Voice Review Configuration")
    layout = QVBoxLayout()
    
    # Port configuration
    port_layout = QHBoxLayout()
    port_layout.addWidget(QLabel("Server Port:"))
    port_input = QSpinBox()
    port_input.setMinimum(1024)
    port_input.setMaximum(65535)
    port_input.setValue(voice_server.config.port if voice_server else 5000)
    port_layout.addWidget(port_input)
    layout.addLayout(port_layout)
    
    # AI hints toggle
    ai_hints = QCheckBox("Enable AI-powered hints")
    ai_hints.setChecked(voice_server.config.enable_ai_hints if voice_server else True)
    layout.addWidget(ai_hints)
    
    # Auto-start server
    auto_start = QCheckBox("Auto-start server when Anki opens")
    auto_start.setChecked(voice_server.config.auto_start if voice_server else False)
    layout.addWidget(auto_start)
    
    # Show assistant on startup
    show_assistant = QCheckBox("Show AI assistant on startup")
    show_assistant.setChecked(voice_server.config.show_voice_assistant if voice_server else True)
    layout.addWidget(show_assistant)
    
    # Session timeout
    timeout_layout = QHBoxLayout()
    timeout_layout.addWidget(QLabel("Session timeout (minutes):"))
    timeout_input = QSpinBox()
    timeout_input.setMinimum(5)
    timeout_input.setMaximum(120)
    timeout_input.setValue(voice_server.config.session_timeout_minutes if voice_server else 30)
    timeout_layout.addWidget(timeout_input)
    layout.addLayout(timeout_layout)
    
    # Security section
    security_group = QGroupBox("Security Settings")
    security_layout = QVBoxLayout()
    
    # Rate limiting
    rate_limit_layout = QHBoxLayout()
    rate_limit_layout.addWidget(QLabel("Max requests per minute:"))
    rate_limit_input = QSpinBox()
    rate_limit_input.setMinimum(10)
    rate_limit_input.setMaximum(1000)
    rate_limit_input.setValue(voice_server.config.max_requests_per_minute if voice_server else 100)
    rate_limit_layout.addWidget(rate_limit_input)
    security_layout.addLayout(rate_limit_layout)
    
    # Webhook authentication
    webhook_auth = QCheckBox("Enable webhook signature verification")
    webhook_auth.setChecked(voice_server.config.enable_webhook_auth if voice_server else False)
    security_layout.addWidget(webhook_auth)
    
    # Webhook secret
    webhook_secret_layout = QHBoxLayout()
    webhook_secret_layout.addWidget(QLabel("Webhook secret (optional):"))
    webhook_secret_input = QLineEdit()
    webhook_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
    webhook_secret_input.setPlaceholderText("Enter ElevenLabs webhook secret")
    if voice_server and voice_server.config.webhook_secret:
        webhook_secret_input.setText(voice_server.config.webhook_secret)
    webhook_secret_layout.addWidget(webhook_secret_input)
    security_layout.addLayout(webhook_secret_layout)
    
    security_group.setLayout(security_layout)
    layout.addWidget(security_group)
    
    # Instructions
    instructions = QTextBrowser()
    instructions.setMaximumHeight(150)
    instructions.setHtml("""
    <html>
    <body style="font-family: Arial; font-size: 12px;">
    <b>Voice Review Setup:</b><br>
    1. Click "Start Voice Server" to enable webhook endpoints<br>
    2. Use the AI Study Buddy window to review cards with voice<br>
    3. Say natural phrases like "I forgot" or "too easy"<br>
    <br>
    <b>For iPhone/iPad:</b> Open ElevenLabs app → Conversational AI → Select "Anki Study Buddy"
    </body>
    </html>
    """)
    layout.addWidget(instructions)
    
    # Buttons
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    dialog.setLayout(layout)
    
    if dialog.exec():
        # Save configuration
        config = {
            'port': port_input.value(),
            'enable_ai_hints': ai_hints.isChecked(),
            'session_timeout_minutes': timeout_input.value(),
            'auto_start': auto_start.isChecked(),
            'show_voice_assistant': show_assistant.isChecked(),
            'max_requests_per_minute': rate_limit_input.value(),
            'enable_webhook_auth': webhook_auth.isChecked()
        }
        mw.addonManager.writeConfig(__name__, config)
        
        # Update webhook secret in running server (not saved to config for security)
        if voice_server and webhook_secret_input.text().strip():
            voice_server.config.webhook_secret = webhook_secret_input.text().strip()
            
        showInfo("Configuration saved. Restart the server for changes to take effect.")

def add_voice_button_to_reviewer(web_content, context):
    """Add voice button to reviewer"""
    if isinstance(context, Reviewer):
        web_content.body += """
        <style>
        .voice-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 24px;
            transition: all 0.3s ease;
        }
        .voice-button:hover {
            background: #0056b3;
            transform: scale(1.1);
        }
        .voice-active {
            background: #28a745;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
            100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
        }
        </style>
        
        <button class="voice-button" onclick="pycmd('voice_assistant:toggle')">
            🎤
        </button>
        """

def handle_pycmd(handled, cmd, context):
    """Handle JavaScript commands"""
    if cmd == "voice_assistant:toggle":
        show_voice_assistant_dialog()
        return True, None
    return handled

def setup_menu():
    """Add menu items"""
    voice_menu = mw.form.menuTools.addMenu("🎤 Voice Review")
    
    # Start server action
    start_action = QAction("▶️ Start Voice Server", mw)
    start_action.triggered.connect(start_voice_server)
    voice_menu.addAction(start_action)
    
    # Stop server action
    stop_action = QAction("⏹️ Stop Voice Server", mw)
    stop_action.triggered.connect(stop_voice_server)
    voice_menu.addAction(stop_action)
    
    voice_menu.addSeparator()
    
    # Widget management submenu
    widget_menu = voice_menu.addMenu("🎯 AI Assistant")
    
    # Show AI assistant (auto-detects preferred type)
    show_action = QAction("📌 Toggle AI Assistant", mw)
    show_action.triggered.connect(lambda: widget_manager.toggle_widget())
    widget_menu.addAction(show_action)
    
    widget_menu.addSeparator()
    
    # Widget type selection
    sidebar_action = QAction("📋 Sidebar Widget", mw)
    sidebar_action.triggered.connect(lambda: switch_widget_type('sidebar'))
    widget_menu.addAction(sidebar_action)
    
    floating_action = QAction("🪟 Floating Widget", mw)
    floating_action.triggered.connect(lambda: switch_widget_type('floating'))
    widget_menu.addAction(floating_action)
    
    popup_action = QAction("💬 Popup Widget", mw)
    popup_action.triggered.connect(lambda: switch_widget_type('popup'))
    widget_menu.addAction(popup_action)
    
    widget_menu.addSeparator()
    
    # Widget preferences
    prefs_action = QAction("⚙️ Widget Preferences", mw)
    prefs_action.triggered.connect(show_widget_preferences_dialog)
    widget_menu.addAction(prefs_action)
    
    voice_menu.addSeparator()
    
    # Configuration action
    config_action = QAction("⚙️ Configure...", mw)
    config_action.triggered.connect(open_config_dialog)
    voice_menu.addAction(config_action)
    
    voice_menu.addSeparator()
    
    # View logs action
    logs_action = QAction("📋 View Logs", mw)
    logs_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(log_file)))
    voice_menu.addAction(logs_action)
    
    # Instructions action
    instructions_action = QAction("❓ How to Use", mw)
    instructions_action.triggered.connect(show_instructions)
    voice_menu.addAction(instructions_action)

def show_instructions():
    """Show usage instructions"""
    dialog = QDialog(mw)
    dialog.setWindowTitle("Voice Review Instructions")
    dialog.setMinimumSize(600, 500)
    
    layout = QVBoxLayout()
    
    browser = QTextBrowser()
    browser.setHtml("""
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; }
            h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            h3 { color: #34495e; }
            code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            .command { background: #e8f4f8; padding: 5px 10px; border-radius: 5px; margin: 5px 0; }
            .tip { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h2>🎓 Anki Voice Review with AI Assistant</h2>
        
        <h3>🚀 Quick Start</h3>
        <ol>
            <li>Click <b>Tools → Voice Review → Start Voice Server</b></li>
            <li>Open the AI Assistant (Dock or Window)</li>
            <li>Say "Start session" to begin reviewing</li>
        </ol>
        
        <h3>🗣️ Voice Commands</h3>
        <div class="command"><b>Starting:</b> "Let's start studying" / "Begin session"</div>
        <div class="command"><b>Next Card:</b> "Next card" / "Continue" / "Give me another"</div>
        <div class="command"><b>Show Answer:</b> "Show answer" / "I give up" / "What's the answer"</div>
        <div class="command"><b>Get Hint:</b> "Give me a hint" / "Help me" / "I need a clue"</div>
        <div class="command"><b>Rate Card:</b> Natural phrases work!</div>
        <ul>
            <li>❌ <b>Again:</b> "I forgot" / "I don't know" / "No idea"</li>
            <li>😅 <b>Hard:</b> "That was tough" / "Difficult" / "I struggled"</li>
            <li>✅ <b>Good:</b> "Got it" / "I know this" / "Correct"</li>
            <li>🎯 <b>Easy:</b> "Too easy" / "Simple" / "Perfect"</li>
        </ul>
        
        <h3>📱 Using on iPhone/iPad</h3>
        <ol>
            <li>Download the <b>ElevenLabs</b> app from App Store</li>
            <li>Open the app and go to <b>Conversational AI</b></li>
            <li>Find and select <b>"Anki Study Buddy"</b></li>
            <li>Make sure your Anki desktop is running with the server started</li>
            <li>Start reviewing hands-free!</li>
        </ol>
        
        <div class="tip">
            <b>💡 Pro Tip:</b> You can also get a phone number for your Study Buddy in the ElevenLabs dashboard, 
            allowing you to call and review cards completely hands-free!
        </div>
        
        <h3>🎯 Review Modes</h3>
        <ul>
            <li><b>Normal:</b> Standard review with all features</li>
            <li><b>Speed:</b> Quick reviews for rapid practice</li>
            <li><b>Focus:</b> No hints, stricter ratings for serious study</li>
            <li><b>Practice:</b> Review without affecting card scheduling</li>
        </ul>
        
        <h3>🔧 Troubleshooting</h3>
        <ul>
            <li>Make sure the voice server is running (green status)</li>
            <li>Allow microphone access when prompted</li>
            <li>Check that port 5000 is not in use by other apps</li>
            <li>View logs for detailed error messages</li>
        </ul>
    </body>
    </html>
    """)
    
    layout.addWidget(browser)
    
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.close)
    layout.addWidget(close_btn)
    
    dialog.setLayout(layout)
    dialog.exec()

# Auto-start functionality
def auto_start():
    """Auto-start server and show assistant if configured"""
    config = mw.addonManager.getConfig(__name__) or {}
    
    if config.get('auto_start', False):
        start_voice_server()
    
    if config.get('show_voice_assistant', True):
        # Show assistant dock after a short delay
        QTimer.singleShot(1000, lambda: toggle_voice_assistant(True))

# Initialize hooks
gui_hooks.main_window_did_init.append(setup_menu)
gui_hooks.webview_will_set_content.append(add_voice_button_to_reviewer)
gui_hooks.webview_did_receive_js_message.append(handle_pycmd)
gui_hooks.profile_did_open.append(auto_start)
#!/usr/bin/env python3
"""
Voice Controls Manager for Anki Voice Review Add-on
Manages voice control widgets and interfaces
"""

import logging
from typing import TYPE_CHECKING, Optional

try:
    from aqt import mw
    from aqt.qt import *
    from aqt.utils import showInfo
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

if TYPE_CHECKING:
    from .. import VoiceReviewAddon

logger = logging.getLogger('voice-review-controls')

class VoiceControlManager:
    """Manages voice control interface and widgets"""
    
    def __init__(self, addon: 'VoiceReviewAddon'):
        self.addon = addon
        self.widget: Optional[QWidget] = None
        self.widget_type = addon.config_manager.get('widget_type', 'sidebar')
        
        if ANKI_AVAILABLE:
            self._setup_widgets()
    
    def _setup_widgets(self):
        """Set up voice control widgets"""
        try:
            widget_type = self.addon.config_manager.get('widget_type', 'sidebar')
            
            if widget_type == 'sidebar':
                self._create_sidebar_widget()
            elif widget_type == 'floating':
                self._create_floating_widget()
            elif widget_type == 'popup':
                self._create_popup_widget()
            
            logger.info(f"Voice control widget created: {widget_type}")
            
        except Exception as e:
            logger.error(f"Failed to setup voice widgets: {e}")
    
    def _create_sidebar_widget(self):
        """Create sidebar voice control widget"""
        if not mw:
            return
            
        # Create a simple status widget for now
        self.widget = QLabel("🎤 Voice Ready")
        self.widget.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        
        # Add to status bar for now (proper sidebar integration would need more work)
        if hasattr(mw, 'statusbar'):
            mw.statusbar.addPermanentWidget(self.widget)
    
    def _create_floating_widget(self):
        """Create floating voice control widget"""
        self.widget = QDialog(mw, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.widget.setWindowTitle("Voice Controls")
        self.widget.setFixedSize(200, 100)
        
        layout = QVBoxLayout(self.widget)
        
        status_label = QLabel("🎤 Voice Ready")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)
        
        start_btn = QPushButton("Start Voice Session")
        start_btn.clicked.connect(self._start_voice_session)
        layout.addWidget(start_btn)
        
        self.widget.show()
    
    def _create_popup_widget(self):
        """Create popup voice control widget"""
        # For now, just show an info message
        showInfo("Voice controls are ready!\n\nAdd voice control buttons to your card templates to get started.")
    
    def _start_voice_session(self):
        """Start a voice session"""
        try:
            # Start MCP server if not running
            if not self.addon.mcp_server:
                success = self.addon.start_mcp_server()
                if not success:
                    showInfo("Failed to start MCP server")
                    return
            
            showInfo("Voice session ready!\n\nUse voice controls on your flashcards.")
            
        except Exception as e:
            logger.error(f"Error starting voice session: {e}")
            showInfo(f"Error starting voice session: {e}")
    
    def update_status(self, status: str):
        """Update voice control status"""
        if self.widget and isinstance(self.widget, QLabel):
            self.widget.setText(f"🎤 {status}")
    
    def cleanup(self):
        """Clean up voice control widgets"""
        if self.widget:
            if hasattr(self.widget, 'close'):
                self.widget.close()
            elif hasattr(mw, 'statusbar') and isinstance(self.widget, QLabel):
                mw.statusbar.removeWidget(self.widget)
            
            self.widget = None 
#!/usr/bin/env python3
"""
Voice Review with AI Assistant - Anki Add-on
Enables hands-free flashcard review using voice commands and ElevenLabs conversational AI.

Main entry point for the add-on that follows proper Anki add-on structure.
"""

import os
import sys
import logging
from typing import Optional

# Add the add-on directory to Python path for imports
addon_dir = os.path.dirname(__file__)
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('voice-review-addon')

try:
    # Import Anki modules
    from aqt import mw, gui_hooks
    from aqt.qt import *
    from aqt.utils import showInfo, showWarning, qconnect
    from anki.hooks import addHook
    
    # Import our modules
    from .core.mcp_server import AnkiMCPServer
    from .ui.voice_controls import VoiceControlManager
    from .ui.menu_integration import setup_menu
    from .utils.config_manager import ConfigManager
    
    ANKI_AVAILABLE = True
    logger.info("Voice Review Add-on: Anki environment detected")
    
except ImportError as e:
    ANKI_AVAILABLE = False
    logger.warning(f"Voice Review Add-on: Anki not available - {e}")

class VoiceReviewAddon:
    """Main add-on class following Anki best practices"""
    
    def __init__(self):
        self.mcp_server: Optional[AnkiMCPServer] = None
        self.voice_manager: Optional[VoiceControlManager] = None
        self.config_manager = ConfigManager()
        self.initialized = False
        
        if ANKI_AVAILABLE:
            self.initialize()
    
    def initialize(self):
        """Initialize the add-on"""
        if self.initialized:
            return
            
        try:
            logger.info("Initializing Voice Review Add-on")
            
            # Set up configuration
            self.config_manager.load_config()
            
            # Set up menu integration
            setup_menu(self)
            
            # Set up hooks
            self._setup_hooks()
            
            # Auto-start MCP server if configured
            if self.config_manager.get('auto_start_mcp', True):
                QTimer.singleShot(1000, self.start_mcp_server)
            
            # Initialize voice controls if configured
            if self.config_manager.get('show_voice_assistant', True):
                QTimer.singleShot(2000, self._initialize_voice_controls)
                
            self.initialized = True
            logger.info("Voice Review Add-on initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Voice Review Add-on: {e}")
            if ANKI_AVAILABLE:
                showWarning(f"Voice Review Add-on initialization failed: {e}")
    
    def _setup_hooks(self):
        """Set up Anki hooks"""
        # Hook for JavaScript commands from cards
        gui_hooks.webview_did_receive_js_message.append(self._handle_js_message)
        
        # Hook for profile loading
        gui_hooks.profile_did_open.append(self._on_profile_opened)
        
        # Hook for main window setup
        gui_hooks.main_window_did_init.append(self._on_main_window_init)
    
    def _handle_js_message(self, handled, message, context):
        """Handle JavaScript messages from voice control cards"""
        if message.startswith("voice_addon:"):
            command = message.replace("voice_addon:", "")
            logger.info(f"Received voice command from card: {command}")
            
            if command == "start_mcp_server":
                success = self.start_mcp_server()
                return (True, None)
            elif command == "stop_mcp_server":
                self.stop_mcp_server()
                return (True, None)
            elif command == "check_status":
                status = self.get_status()
                return (True, status)
        
        return handled
    
    def _on_profile_opened(self):
        """Called when a profile is opened"""
        # Reinitialize if needed when profile changes
        pass
    
    def _on_main_window_init(self):
        """Called when main window is initialized"""
        # Additional initialization if needed
        pass
    
    def start_mcp_server(self) -> bool:
        """Start the MCP server"""
        try:
            if self.mcp_server:
                return True
                
            logger.info("Starting MCP server...")
            self.mcp_server = AnkiMCPServer()
            
            logger.info("MCP server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def stop_mcp_server(self):
        """Stop the MCP server"""
        if self.mcp_server:
            logger.info("Stopping MCP server...")
            self.mcp_server = None
    
    def _initialize_voice_controls(self):
        """Initialize voice control manager"""
        try:
            if not self.voice_manager:
                self.voice_manager = VoiceControlManager(self)
                logger.info("Voice controls initialized")
        except Exception as e:
            logger.error(f"Failed to initialize voice controls: {e}")
    
    def get_status(self) -> dict:
        """Get current add-on status"""
        return {
            'mcp_server_running': self.mcp_server is not None,
            'voice_controls_active': self.voice_manager is not None,
            'config_loaded': self.config_manager.config is not None
        }
    
    def show_config(self):
        """Show configuration dialog"""
        from .ui.config_dialog import ConfigDialog
        dialog = ConfigDialog(self.config_manager, mw)
        dialog.exec()
    
    def show_help(self):
        """Show help dialog"""
        from .ui.help_dialog import HelpDialog
        dialog = HelpDialog(mw)
        dialog.exec()

# Global addon instance
addon_instance: Optional[VoiceReviewAddon] = None

def get_addon() -> VoiceReviewAddon:
    """Get the global addon instance"""
    global addon_instance
    if addon_instance is None:
        addon_instance = VoiceReviewAddon()
    return addon_instance

# Initialize when module is imported
if ANKI_AVAILABLE:
    addon_instance = get_addon()

# Export for other modules
__all__ = ['VoiceReviewAddon', 'get_addon', 'ANKI_AVAILABLE'] 
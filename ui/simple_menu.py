"""
Simple menu integration for Voice Review Add-on
Focuses on ElevenLabs API session management instead of MCP server
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..SimpleVoiceReviewAddon import SimpleVoiceReviewAddon

try:
    from aqt import mw
    from aqt.qt import QAction, QMenu
    from aqt.utils import showInfo, qconnect
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

logger = logging.getLogger("voice-review-menu")

def setup_menu(addon: 'SimpleVoiceReviewAddon'):
    """Set up the Voice Review menu in Anki's Tools menu"""
    if not ANKI_AVAILABLE:
        return
        
    try:
        # Create Voice Review submenu
        voice_menu = QMenu("Voice Review", mw)
        
        # Start API Session action
        start_action = QAction("Start API Session", mw)
        start_action.setStatusTip("Connect to ElevenLabs API and start voice controls")
        qconnect(start_action.triggered, lambda: _start_api_session(addon))
        voice_menu.addAction(start_action)
        
        # Stop API Session action
        stop_action = QAction("Stop API Session", mw)
        stop_action.setStatusTip("Disconnect from ElevenLabs API and stop voice controls")
        qconnect(stop_action.triggered, lambda: _stop_api_session(addon))
        voice_menu.addAction(stop_action)
        
        voice_menu.addSeparator()
        
        # Show Voice Assistant action (placeholder)
        show_assistant_action = QAction("Show Voice Assistant", mw)
        show_assistant_action.setStatusTip("Show voice controls information")
        qconnect(show_assistant_action.triggered, lambda: _show_voice_assistant(addon))
        voice_menu.addAction(show_assistant_action)
        
        voice_menu.addSeparator()
        
        # Configuration action
        config_action = QAction("Configuration", mw)
        config_action.setStatusTip("Configure ElevenLabs API settings")
        qconnect(config_action.triggered, lambda: _show_config(addon))
        voice_menu.addAction(config_action)
        
        # Help action
        help_action = QAction("Help", mw)
        help_action.setStatusTip("Show Voice Review help and documentation")
        qconnect(help_action.triggered, lambda: _show_help(addon))
        voice_menu.addAction(help_action)
        
        # Add to Tools menu
        mw.form.menuTools.addSeparator()
        mw.form.menuTools.addMenu(voice_menu)
        
        logger.info("Voice Review menu added to Tools menu")
        
    except Exception as e:
        logger.error(f"Failed to setup menu: {e}")

def _start_api_session(addon: 'SimpleVoiceReviewAddon'):
    """Start ElevenLabs API session menu action"""
    try:
        success = addon.start_api_session()
        if success:
            showInfo("ElevenLabs API session started successfully!\n\nVoice controls are now active on your flashcards.\n\nClick 'Start Voice' on any card with voice controls to begin.")
        else:
            showInfo("Failed to start API session.\n\nPlease check your ElevenLabs API configuration.")
    except Exception as e:
        logger.error(f"Error starting API session from menu: {e}")
        showInfo(f"Error starting API session: {e}")

def _stop_api_session(addon: 'SimpleVoiceReviewAddon'):
    """Stop ElevenLabs API session menu action"""
    try:
        addon.stop_api_session()
        showInfo("ElevenLabs API session stopped.\n\nVoice controls are now inactive.")
    except Exception as e:
        logger.error(f"Error stopping API session from menu: {e}")
        showInfo(f"Error stopping API session: {e}")

def _show_voice_assistant(addon: 'SimpleVoiceReviewAddon'):
    """Show voice assistant information"""
    try:
        status = addon.get_status()
        
        if status['api_session_active']:
            info_text = "✅ Voice Assistant Active!\n\n"
        else:
            info_text = "⏸️ Voice Assistant Inactive\n\n"
            
        info_text += """📱 How to Use Voice Controls:

1. Add voice control buttons to your card templates
   • Get code: python templates/anki_card_voice_buttons.py
   • Copy HTML, CSS, and JavaScript to your cards

2. Start an API session (Tools → Voice Review → Start API Session)

3. On cards with voice controls:
   • Click "Start Voice" button
   • Use voice commands: "next card", "I forgot", "got it"
   • Say "read card" to hear the content
   • Say "help" for more commands

4. Keyboard shortcuts:
   • Ctrl+V: Start/stop voice session
   • Ctrl+M: Toggle microphone
   • Ctrl+R: Read current card

💡 Voice commands work entirely in your browser - no complex server setup needed!"""

        showInfo(info_text, title="Voice Assistant Status")
        
    except Exception as e:
        logger.error(f"Error showing voice assistant info: {e}")
        showInfo(f"Error showing voice assistant: {e}")

def _show_config(addon: 'SimpleVoiceReviewAddon'):
    """Show configuration dialog"""
    try:
        addon.show_config()
    except Exception as e:
        logger.error(f"Error showing config: {e}")
        showInfo(f"Error showing configuration: {e}")

def _show_help(addon: 'SimpleVoiceReviewAddon'):
    """Show help dialog"""
    try:
        addon.show_help()
    except Exception as e:
        logger.error(f"Error showing help: {e}")
        showInfo(f"Error showing help: {e}") 
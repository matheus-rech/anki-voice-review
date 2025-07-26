#!/usr/bin/env python3
"""
Menu Integration for Voice Review Add-on
Sets up menu items in Anki's Tools menu
"""

import logging
from typing import TYPE_CHECKING

try:
    from aqt import mw
    from aqt.qt import *
    from aqt.utils import showInfo, qconnect
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

if TYPE_CHECKING:
    from .. import VoiceReviewAddon

logger = logging.getLogger('voice-review-menu')

def setup_menu(addon: 'VoiceReviewAddon'):
    """Set up the Voice Review menu in Anki's Tools menu"""
    if not ANKI_AVAILABLE or not mw:
        return
    
    try:
        # Create main menu
        voice_menu = QMenu("Voice Review", mw)
        
        # Start MCP Server action
        start_server_action = QAction("Start MCP Server", mw)
        start_server_action.setStatusTip("Start the MCP server for AI assistant integration")
        qconnect(start_server_action.triggered, lambda: _start_mcp_server(addon))
        voice_menu.addAction(start_server_action)
        
        # Stop MCP Server action
        stop_server_action = QAction("Stop MCP Server", mw)
        stop_server_action.setStatusTip("Stop the MCP server")
        qconnect(stop_server_action.triggered, lambda: _stop_mcp_server(addon))
        voice_menu.addAction(stop_server_action)
        
        voice_menu.addSeparator()
        
        # Show Voice Assistant action
        show_assistant_action = QAction("Show Voice Assistant", mw)
        show_assistant_action.setStatusTip("Show voice control interface")
        qconnect(show_assistant_action.triggered, lambda: _show_voice_assistant(addon))
        voice_menu.addAction(show_assistant_action)
        
        voice_menu.addSeparator()
        
        # Configuration action
        config_action = QAction("Configuration", mw)
        config_action.setStatusTip("Configure Voice Review settings")
        qconnect(config_action.triggered, lambda: _show_config(addon))
        voice_menu.addAction(config_action)
        
        # Help action
        help_action = QAction("Help", mw)
        help_action.setStatusTip("Show Voice Review help")
        qconnect(help_action.triggered, lambda: _show_help(addon))
        voice_menu.addAction(help_action)
        
        # Add to Tools menu
        mw.form.menuTools.addSeparator()
        mw.form.menuTools.addMenu(voice_menu)
        
        logger.info("Voice Review menu added to Tools menu")
        
    except Exception as e:
        logger.error(f"Failed to setup menu: {e}")

def _start_mcp_server(addon: 'VoiceReviewAddon'):
    """Start MCP server menu action"""
    try:
        success = addon.start_mcp_server()
        if success:
            showInfo("MCP Server started successfully!\n\nYou can now use voice commands with AI assistants.")
        else:
            showInfo("Failed to start MCP Server.\n\nCheck the log for details.")
    except Exception as e:
        logger.error(f"Error starting MCP server from menu: {e}")
        showInfo(f"Error starting MCP server: {e}")

def _stop_mcp_server(addon: 'VoiceReviewAddon'):
    """Stop MCP server menu action"""
    try:
        addon.stop_mcp_server()
        showInfo("MCP Server stopped.")
    except Exception as e:
        logger.error(f"Error stopping MCP server from menu: {e}")
        showInfo(f"Error stopping MCP server: {e}")

def _show_voice_assistant(addon: 'VoiceReviewAddon'):
    """Show voice assistant menu action"""
    try:
        addon._initialize_voice_controls()
        showInfo("Voice Assistant activated!\n\nLook for voice control buttons on your flashcards.")
    except Exception as e:
        logger.error(f"Error showing voice assistant: {e}")
        showInfo(f"Error showing voice assistant: {e}")

def _show_config(addon: 'VoiceReviewAddon'):
    """Show configuration dialog menu action"""
    try:
        addon.show_config()
    except Exception as e:
        logger.error(f"Error showing config: {e}")
        showInfo(f"Error showing configuration: {e}")

def _show_help(addon: 'VoiceReviewAddon'):
    """Show help dialog menu action"""
    try:
        addon.show_help()
    except Exception as e:
        logger.error(f"Error showing help: {e}")
        showInfo(f"Error showing help: {e}") 
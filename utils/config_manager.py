#!/usr/bin/env python3
"""
Configuration Manager for Voice Review Add-on
Handles loading and saving of user configuration
"""

import json
import logging
from typing import Any, Dict, Optional

try:
    from aqt import mw
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

logger = logging.getLogger('voice-review-config')

class ConfigManager:
    """Manages add-on configuration using Anki's built-in config system"""
    
    def __init__(self):
        self.config: Optional[Dict[str, Any]] = None
        self.default_config = {
            "auto_start_mcp": True,
            "show_voice_assistant": True,
            "elevenlabs_agent_id": "agent_5301k0wccfefeaxtkqr0kce7v66a",
            "mcp_server_port": 8000,
            "auto_start_from_cards": True,
            "widget_type": "sidebar",
            "voice_recognition_language": "en-US",
            "natural_language_mappings": {
                "again": ["again", "repeat", "forgot", "missed", "no", "totally forgot", "completely forgot", "no idea", "blank", "drawing a blank", "clueless"],
                "hard": ["hard", "difficult", "struggled", "almost", "pretty hard", "took a while", "challenging", "eventually got it", "figured it out"],
                "good": ["good", "correct", "yes", "got it", "remembered", "knew that", "right answer", "of course", "recognized it", "came to me"],
                "easy": ["easy", "perfect", "instant", "obvious", "simple", "immediately", "too simple", "way too easy", "piece of cake", "no problem", "super obvious"]
            },
            "ui_settings": {
                "show_status_indicator": True,
                "show_session_stats": True,
                "minimizable_panel": True,
                "panel_position": "bottom-right"
            }
        }
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from Anki"""
        if ANKI_AVAILABLE and mw and hasattr(mw, 'addonManager'):
            try:
                # Get config from Anki's addon manager
                user_config = mw.addonManager.getConfig(__name__.split('.')[0])
                
                if user_config:
                    # Merge with defaults
                    self.config = self._merge_config(self.default_config.copy(), user_config)
                else:
                    self.config = self.default_config.copy()
                
                logger.info("Configuration loaded from Anki")
                
            except Exception as e:
                logger.warning(f"Failed to load config from Anki: {e}")
                self.config = self.default_config.copy()
        else:
            # Fallback to defaults if Anki not available
            self.config = self.default_config.copy()
            logger.info("Using default configuration")
        
        return self.config
    
    def save_config(self):
        """Save configuration to Anki"""
        if not self.config:
            return
        
        if ANKI_AVAILABLE and mw and hasattr(mw, 'addonManager'):
            try:
                mw.addonManager.writeConfig(__name__.split('.')[0], self.config)
                logger.info("Configuration saved to Anki")
            except Exception as e:
                logger.error(f"Failed to save config to Anki: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if not self.config:
            self.load_config()
        
        return self._get_nested(self.config, key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value"""
        if not self.config:
            self.load_config()
        
        self._set_nested(self.config, key, value)
    
    def _get_nested(self, config: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Get nested configuration value using dot notation"""
        keys = key.split('.')
        current = config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def _set_nested(self, config: Dict[str, Any], key: str, value: Any):
        """Set nested configuration value using dot notation"""
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def _merge_config(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge user config with defaults"""
        for key, value in user.items():
            if key in default:
                if isinstance(default[key], dict) and isinstance(value, dict):
                    default[key] = self._merge_config(default[key], value)
                else:
                    default[key] = value
            else:
                default[key] = value
        
        return default
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self.default_config.copy()
        self.save_config()
        logger.info("Configuration reset to defaults")
    
    def get_natural_language_mappings(self) -> Dict[str, list]:
        """Get natural language mappings for voice commands"""
        return self.get('natural_language_mappings', {})
    
    def get_ui_settings(self) -> Dict[str, Any]:
        """Get UI settings"""
        return self.get('ui_settings', {}) 
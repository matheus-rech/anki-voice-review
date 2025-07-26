"""
Secure Configuration Helper for Voice Review Add-on
Handles API key loading from secure sources with fallbacks
"""

import os
import logging
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger("voice-review-secure-config")

class SecureConfigManager:
    """
    Secure API key management with multiple fallback sources:
    1. Environment variable (most secure)
    2. User config file (if environment not available)
    3. Anki profile config (last resort)
    
    Never stores keys in source code!
    """
    
    def __init__(self):
        self.api_key = None
        self._load_api_key()
    
    def _load_api_key(self) -> None:
        """Load API key from secure sources in order of preference"""
        
        # Method 1: Environment variable (RECOMMENDED)
        env_key = os.getenv('ELEVENLABS_API_KEY')
        if env_key and env_key.strip():
            self.api_key = env_key.strip()
            logger.info(f"✅ API key loaded from environment variable (ends with: ...{env_key[-4:]})")
            return
        
        # Method 2: User config file (fallback)
        config_key = self._load_from_user_config()
        if config_key:
            self.api_key = config_key
            logger.info(f"✅ API key loaded from user config (ends with: ...{config_key[-4:]})")
            return
        
        # Method 3: Anki profile config (last resort)
        try:
            from aqt import mw
            if mw and mw.addonManager:
                addon_config = mw.addonManager.getConfig(__name__.split('.')[0])
                if addon_config and 'elevenlabs_api_key' in addon_config:
                    profile_key = addon_config['elevenlabs_api_key']
                    if profile_key and profile_key.strip():
                        self.api_key = profile_key.strip()
                        logger.info(f"✅ API key loaded from Anki profile config (ends with: ...{profile_key[-4:]})")
                        return
        except Exception as e:
            logger.debug(f"Could not load from Anki profile config: {e}")
        
        # No API key found
        logger.warning("❌ No ElevenLabs API key found in any secure location")
        self.api_key = None
    
    def _load_from_user_config(self) -> Optional[str]:
        """Load API key from user's home directory config file"""
        try:
            # Check for config in user's home directory
            home_config = Path.home() / '.anki_voice_review' / 'config.json'
            
            if home_config.exists():
                with open(home_config, 'r') as f:
                    config = json.load(f)
                    return config.get('elevenlabs_api_key')
            
        except Exception as e:
            logger.debug(f"Could not load from user config: {e}")
        
        return None
    
    def get_api_key(self) -> Optional[str]:
        """Get the API key if available"""
        return self.api_key
    
    def is_configured(self) -> bool:
        """Check if API key is properly configured"""
        return self.api_key is not None and len(self.api_key.strip()) > 0
    
    def save_to_user_config(self, api_key: str) -> bool:
        """
        Save API key to user config file as fallback
        (Environment variable is still recommended)
        """
        try:
            config_dir = Path.home() / '.anki_voice_review'
            config_dir.mkdir(exist_ok=True)
            
            config_file = config_dir / 'config.json'
            
            # Load existing config or create new
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Save API key
            config['elevenlabs_api_key'] = api_key.strip()
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set restrictive permissions (Unix-like systems)
            if hasattr(os, 'chmod'):
                os.chmod(config_file, 0o600)  # Read/write for owner only
            
            logger.info(f"✅ API key saved to user config: {config_file}")
            
            # Reload the key
            self._load_api_key()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save API key to user config: {e}")
            return False
    
    def get_config_instructions(self) -> str:
        """Get setup instructions for the user"""
        return """
🔧 ElevenLabs API Key Setup Instructions:

RECOMMENDED (Most Secure):
Set environment variable before starting Anki:

macOS/Linux:
export ELEVENLABS_API_KEY='your_api_key_here'

Windows:
set ELEVENLABS_API_KEY=your_api_key_here

ALTERNATIVE (Fallback):
Use the add-on's configuration dialog:
Tools → Voice Review → Configuration → Set API Key

VERIFICATION:
Tools → Voice Review → Voice Controls Status
Should show "✅ ElevenLabs API Key: Configured"
        """.strip()
    
    def get_status_info(self) -> dict:
        """Get current configuration status"""
        if not self.is_configured():
            return {
                'configured': False,
                'source': 'none',
                'message': 'API key not configured',
                'instructions': self.get_config_instructions()
            }
        
        # Determine source
        env_key = os.getenv('ELEVENLABS_API_KEY')
        if env_key and env_key.strip() == self.api_key:
            source = 'environment'
        elif self._load_from_user_config() == self.api_key:
            source = 'user_config'
        else:
            source = 'anki_profile'
        
        return {
            'configured': True,
            'source': source,
            'key_suffix': f"...{self.api_key[-4:]}",
            'message': f'API key loaded from {source.replace("_", " ")}'
        }

# Global instance
_secure_config = None

def get_secure_config() -> SecureConfigManager:
    """Get the global secure config instance"""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfigManager()
    return _secure_config

def get_elevenlabs_api_key() -> Optional[str]:
    """Convenience function to get the API key"""
    return get_secure_config().get_api_key()

def is_api_key_configured() -> bool:
    """Convenience function to check if API key is configured"""
    return get_secure_config().is_configured() 
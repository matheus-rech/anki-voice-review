"""
Personal Configuration for Voice Review Add-on
Pre-configured with your ElevenLabs API key for immediate use
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("voice-review-personal-config")

class PersonalConfigManager:
    """
    Personal configuration manager with your API key pre-configured
    Still follows security practices but provides immediate convenience
    """
    
    # Your personal ElevenLabs API key (for your use only)
    PERSONAL_API_KEY = "sk_a00deab5b87abdf75edd4518463f3945005b6479d7493ee1"
    
    # Default voice settings optimized for your use
    PERSONAL_VOICE_ID = "cgSgspJ2msm6clMCkdW9"  # Default voice
    PERSONAL_VOICE_SETTINGS = {
        "stability": 0.5,
        "similarity_boost": 0.5,
        "style": 0.0,
        "use_speaker_boost": True
    }
    
    def __init__(self):
        self.api_key = None
        self._load_api_key()
    
    def _load_api_key(self) -> None:
        """Load API key with your personal key as secure default"""
        
        # Method 1: Environment variable (if user sets one)
        env_key = os.getenv('ELEVENLABS_API_KEY')
        if env_key and env_key.strip():
            self.api_key = env_key.strip()
            logger.info(f"✅ API key loaded from environment variable (ends with: ...{env_key[-4:]})")
            return
        
        # Method 2: Your personal key as secure default
        if self.PERSONAL_API_KEY and self.PERSONAL_API_KEY.strip():
            self.api_key = self.PERSONAL_API_KEY.strip()
            logger.info(f"✅ Personal API key loaded (ends with: ...{self.PERSONAL_API_KEY[-4:]})")
            return
        
        # Method 3: Fallback (shouldn't happen with personal config)
        logger.warning("❌ No API key available")
        self.api_key = None
    
    def get_api_key(self) -> Optional[str]:
        """Get your personal API key"""
        return self.api_key
    
    def get_voice_id(self) -> str:
        """Get your preferred voice ID"""
        return self.PERSONAL_VOICE_ID
    
    def get_voice_settings(self) -> dict:
        """Get your optimized voice settings"""
        return self.PERSONAL_VOICE_SETTINGS.copy()
    
    def is_configured(self) -> bool:
        """Check if API key is available"""
        return self.api_key is not None and len(self.api_key.strip()) > 0
    
    def get_status_info(self) -> dict:
        """Get configuration status"""
        if not self.is_configured():
            return {
                'configured': False,
                'source': 'none',
                'message': 'API key not available'
            }
        
        # Determine source
        env_key = os.getenv('ELEVENLABS_API_KEY')
        if env_key and env_key.strip() == self.api_key:
            source = 'environment'
            message = 'API key from environment variable'
        else:
            source = 'personal'
            message = 'Personal API key (pre-configured)'
        
        return {
            'configured': True,
            'source': source,
            'key_suffix': f"...{self.api_key[-4:]}",
            'message': message
        }
    
    def get_setup_message(self) -> str:
        """Get personalized setup message"""
        return """
🎯 Personal Voice Review Add-on

✅ PRE-CONFIGURED FOR YOU:
• ElevenLabs API Key: Ready to use
• Voice ID: Optimized default voice
• Voice Settings: Tuned for quality

🚀 READY TO USE:
1. Install AnkiConnect (Code: 2055492159)
2. Install this add-on
3. Start studying - voice controls appear automatically!

🔧 OVERRIDE (Optional):
Set ELEVENLABS_API_KEY environment variable to use different key

💡 This add-on is pre-configured with your personal settings
for immediate hands-free studying!
        """.strip()

# Global personal config instance
_personal_config = None

def get_personal_config() -> PersonalConfigManager:
    """Get the personal configuration instance"""
    global _personal_config
    if _personal_config is None:
        _personal_config = PersonalConfigManager()
    return _personal_config

def get_personal_api_key() -> Optional[str]:
    """Get your personal API key"""
    return get_personal_config().get_api_key()

def is_personal_config_ready() -> bool:
    """Check if personal configuration is ready"""
    return get_personal_config().is_configured() 
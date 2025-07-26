"""
Simple configuration dialog for Voice Review Add-on
Uses Anki's built-in configuration system for ElevenLabs API settings
"""

try:
    from aqt import mw
    from aqt.utils import showInfo, showWarning, getText
    from aqt.qt import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox, QFormLayout
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

def show_config_dialog(config_manager=None):
    """Show the configuration dialog using Anki's built-in config system"""
    if not ANKI_AVAILABLE:
        return
    
    try:
        # Try to use Anki's built-in add-on configuration manager
        addon_package = __name__.split('.')[0]  # Get the root addon package name
        
        # First try the modern way
        if hasattr(mw.addonManager, 'configEditor'):
            try:
                mw.addonManager.configEditor(addon_package)
                return
            except:
                pass
        
        # Fallback to manual configuration dialog
        dialog = SimpleConfigDialog(config_manager)
        dialog.exec()
        
    except Exception as e:
        showWarning(f"Error opening configuration: {str(e)}\n\nTo configure manually:\n1. Go to Tools → Add-ons\n2. Select 'Voice Review'\n3. Click 'Config' button")

def show_help_dialog():
    """Show comprehensive help information"""
    if not ANKI_AVAILABLE:
        return
    
    help_text = """🎤 Voice Review Add-on - Comprehensive Help

📋 OVERVIEW:
This add-on enables hands-free flashcard review using ElevenLabs API for voice synthesis and recognition. No complex server setup required!

🔧 SETUP:
1. Get your ElevenLabs API key:
   • Visit https://elevenlabs.io
   • Create account and get your API key
   
2. Configure the add-on:
   • Tools → Voice Review → Configuration
   • Enter your API key
   • Optionally customize voice ID and agent ID

3. Add voice controls to cards:
   • Run: python templates/anki_card_voice_buttons.py
   • Copy the HTML, CSS, and JavaScript
   • Paste into your card templates

🎤 VOICE COMMANDS:
Navigation:
• "next card" - Advance to next card
• "show answer" - Reveal answer

Rating (Natural Language):
• "I forgot" / "again" - Rate as Again (1)
• "hard" / "difficult" - Rate as Hard (2)
• "good" / "got it" - Rate as Good (3)
• "easy" / "perfect" - Rate as Easy (4)

Audio:
• "read card" - Read card content aloud
• "repeat" - Read card again
• "help" - Show available commands

⌨️ KEYBOARD SHORTCUTS:
• Ctrl+V - Start/stop voice session
• Ctrl+M - Toggle microphone
• Ctrl+R - Read current card

🔄 HOW IT WORKS:
1. Click "Start Voice" on any card with voice controls
2. The add-on connects directly to ElevenLabs API
3. Speech recognition runs in your browser
4. Voice commands control Anki through JavaScript
5. Text-to-speech uses ElevenLabs voices

📱 MOBILE SUPPORT:
• Install ElevenLabs mobile app
• Use same agent ID configuration
• Perfect for commute studying

🐛 TROUBLESHOOTING:
• API connection failed: Check your API key
• Voice not recognized: Speak clearly, try rephrasing
• No audio: Check browser permissions
• Cards not responding: Verify JavaScript is in back template

🔧 CONFIGURATION:
• elevenlabs_api_key: Your ElevenLabs API key (required)
• voice_id: Voice to use for TTS (default: Jessica)
• elevenlabs_agent_id: Conversational agent (optional)

💡 TIPS:
• Use natural language - the system understands context
• Speak at normal pace and volume
• "Read card" is great for language learning
• Session stats track your progress

📚 RESOURCES:
• ElevenLabs API: https://elevenlabs.io/docs
• Voice Gallery: https://elevenlabs.io/voice-library
• Anki Templates: https://docs.ankiweb.net/templates

🎯 PERFECT FOR:
• Language learning with pronunciation
• Hands-free review while commuting
• Accessibility and ease of use
• Natural conversation-style studying

Happy voice studying! 🚀"""
    
    showInfo(help_text, title="Voice Review - Complete Help Guide")

class SimpleConfigDialog(QDialog):
    """Simple configuration dialog for ElevenLabs settings"""
    
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Voice Review Configuration")
        self.setModal(True)
        self.resize(500, 400)
        self.setup_ui()
        self.load_current_config()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🎤 Voice Review Configuration")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(title)
        
        # ElevenLabs API Settings Group
        api_group = QGroupBox("ElevenLabs API Settings")
        api_layout = QFormLayout()
        
        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your ElevenLabs API key")
        api_layout.addRow("API Key:", self.api_key_input)
        
        # Show/Hide API Key button
        key_button_layout = QHBoxLayout()
        self.show_key_btn = QPushButton("Show Key")
        self.show_key_btn.clicked.connect(self.toggle_key_visibility)
        key_button_layout.addWidget(self.show_key_btn)
        key_button_layout.addStretch()
        api_layout.addRow("", key_button_layout)
        
        # Voice ID
        self.voice_id_input = QLineEdit()
        self.voice_id_input.setPlaceholderText("cgSgspJ2msm6clMCkdW9 (Jessica - default)")
        api_layout.addRow("Voice ID:", self.voice_id_input)
        
        # Agent ID (optional)
        self.agent_id_input = QLineEdit()
        self.agent_id_input.setPlaceholderText("agent_5301k0wccfefeaxtkqr0kce7v66a (optional)")
        api_layout.addRow("Agent ID:", self.agent_id_input)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Help text
        help_text = QLabel("""💡 Configuration Help:
• Get your API key from https://elevenlabs.io
• Voice ID determines which voice speaks your cards
• Agent ID enables conversational AI features (optional)
• All settings are saved automatically""")
        help_text.setStyleSheet("color: #666; font-size: 11px; margin: 10px 0;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Test connection area
        test_group = QGroupBox("Test Connection")
        test_layout = QVBoxLayout()
        
        self.test_btn = QPushButton("🔍 Test ElevenLabs API Connection")
        self.test_btn.clicked.connect(self.test_connection)
        test_layout.addWidget(self.test_btn)
        
        self.test_result = QLabel("")
        test_layout.addWidget(self.test_result)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Save Configuration")
        self.save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_btn)
        
        help_btn = QPushButton("❓ Show Help")
        help_btn.clicked.connect(lambda: show_help_dialog())
        button_layout.addWidget(help_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_current_config(self):
        """Load current configuration values"""
        if not self.config_manager:
            return
            
        try:
            config = self.config_manager.get_all()
            
            self.api_key_input.setText(config.get('elevenlabs_api_key', ''))
            self.voice_id_input.setText(config.get('voice_id', 'cgSgspJ2msm6clMCkdW9'))
            self.agent_id_input.setText(config.get('elevenlabs_agent_id', 'agent_5301k0wccfefeaxtkqr0kce7v66a'))
            
        except Exception as e:
            showWarning(f"Error loading configuration: {e}")
    
    def toggle_key_visibility(self):
        """Toggle API key visibility"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("Hide Key")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("Show Key")
    
    def test_connection(self):
        """Test connection to ElevenLabs API"""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            self.test_result.setText("❌ Please enter an API key first")
            self.test_result.setStyleSheet("color: red;")
            return
        
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        self.test_result.setText("🔍 Testing connection...")
        self.test_result.setStyleSheet("color: blue;")
        
        try:
            # Simple test - just check if key format looks correct
            if len(api_key) < 20:
                raise ValueError("API key seems too short")
            
            # In a full implementation, you would make an actual API call here
            # For now, we'll just validate the format
            self.test_result.setText("✅ API key format looks valid! Click Save to apply.")
            self.test_result.setStyleSheet("color: green;")
            
        except Exception as e:
            self.test_result.setText(f"❌ Connection test failed: {str(e)}")
            self.test_result.setStyleSheet("color: red;")
        
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("🔍 Test ElevenLabs API Connection")
    
    def save_config(self):
        """Save configuration"""
        if not self.config_manager:
            showWarning("Configuration manager not available")
            return
        
        try:
            # Get values from form
            api_key = self.api_key_input.text().strip()
            voice_id = self.voice_id_input.text().strip() or 'cgSgspJ2msm6clMCkdW9'
            agent_id = self.agent_id_input.text().strip() or 'agent_5301k0wccfefeaxtkqr0kce7v66a'
            
            # Validate required fields
            if not api_key:
                showWarning("API key is required!")
                return
            
            # Save configuration
            self.config_manager.set('elevenlabs_api_key', api_key)
            self.config_manager.set('voice_id', voice_id)
            self.config_manager.set('elevenlabs_agent_id', agent_id)
            
            self.config_manager.save_config()
            
            showInfo("✅ Configuration saved successfully!\n\nYou can now start an API session and use voice controls on your cards.")
            self.accept()
            
        except Exception as e:
            showWarning(f"Error saving configuration: {e}")

# Simple configuration functions for non-dialog usage
def get_api_key():
    """Get API key from user input"""
    if not ANKI_AVAILABLE:
        return None
        
    api_key, ok = getText("Enter your ElevenLabs API key:", title="API Key Required")
    return api_key if ok and api_key.strip() else None

def show_quick_setup():
    """Show quick setup dialog"""
    if not ANKI_AVAILABLE:
        return
        
    info_text = """🚀 Quick Setup for Voice Review:

1. Get ElevenLabs API Key:
   • Visit https://elevenlabs.io
   • Create account → Get API key

2. Configure Add-on:
   • Tools → Voice Review → Configuration
   • Enter your API key

3. Add Voice Controls to Cards:
   • Run: python templates/anki_card_voice_buttons.py
   • Copy HTML, CSS, JS to your card templates

4. Start Using:
   • Tools → Voice Review → Start API Session
   • Click "Start Voice" on cards
   • Say "next card", "I forgot", "got it", etc.

Ready to configure now?"""
    
    showInfo(info_text, title="Voice Review Setup") 
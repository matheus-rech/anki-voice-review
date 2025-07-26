"""
Configuration dialog for Voice Review Add-on
Uses Anki's built-in configuration system
"""

try:
    from aqt import mw
    from aqt.utils import showInfo, showWarning
    from aqt.qt import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QSpinBox, QTextEdit
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

def show_config_dialog():
    """Show the configuration dialog using Anki's built-in config system"""
    if not ANKI_AVAILABLE:
        return
    
    try:
        # Use Anki's built-in add-on configuration manager
        addon_package = mw.addonManager.addonFromModule(__name__)
        if addon_package:
            mw.addonManager.configEditor(addon_package)
        else:
            # Fallback: show info with current config
            config = mw.addonManager.getConfig(__name__) or {}
            config_text = "Current Voice Review Configuration:\n\n"
            for key, value in config.items():
                config_text += f"{key}: {value}\n"
            config_text += "\nTo modify settings, go to:\nTools → Add-ons → Voice Review → Config"
            showInfo(config_text, title="Voice Review Configuration")
    except Exception as e:
        showWarning(f"Error opening configuration: {str(e)}\n\nTry: Tools → Add-ons → Voice Review with AI Assistant → Config")

def show_help_dialog():
    """Show help information"""
    if not ANKI_AVAILABLE:
        return
    
    help_text = """
🎤 Voice Review Add-on - Help

BASIC USAGE:
1. Add voice controls to your card templates
2. Use the template generator: python templates/anki_card_voice_buttons.py
3. Copy the HTML, CSS, and JavaScript to your card templates

VOICE COMMANDS:
• "next card" - Advance to next card
• "show answer" - Reveal answer
• "I forgot" / "again" - Rate as Again (1)
• "hard" / "difficult" - Rate as Hard (2) 
• "good" / "got it" - Rate as Good (3)
• "easy" / "perfect" - Rate as Easy (4)

MENU OPTIONS:
• Start MCP Server - Enable AI assistant features
• Stop MCP Server - Disable AI features
• Show Voice Assistant - Display voice controls
• Configuration - Modify settings
• Help - Show this dialog

TROUBLESHOOTING:
• If MCP server fails: Voice controls still work without it
• For card integration: See templates/anki_card_voice_buttons.py
• For mobile: Install ElevenLabs app and configure agent ID

CONFIGURATION:
• ElevenLabs Agent ID: agent_5301k0wccfefeaxtkqr0kce7v66a
• MCP Server Port: 8000
• Auto-start options available in config

For more help, check the README.md file.
"""
    
    showInfo(help_text, title="Voice Review - Help")

class SimpleConfigDialog(QDialog):
    """Simple configuration dialog as fallback"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Review Configuration")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Voice Review Add-on Configuration")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Info text
        info = QLabel("Use Anki's built-in configuration system:\nTools → Add-ons → Voice Review → Config")
        layout.addWidget(info)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        help_button = QPushButton("Show Help")
        help_button.clicked.connect(lambda: show_help_dialog())
        button_layout.addWidget(help_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout) 
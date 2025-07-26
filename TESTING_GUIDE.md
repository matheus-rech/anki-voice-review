# 🧪 Testing & Installation Guide

## 🔧 **IMPORTANT: Latest Fix Applied**

**✅ Fixed Import Error**: The `TextContent` import issue has been resolved in the latest package.

**📦 Updated Package**: `voice_review_addon.ankiaddon` (25.8KB) - July 26, 2024

If you previously got this error:
```
NameError: name 'TextContent' is not defined
```

**Solution**: Use the newly generated `voice_review_addon.ankiaddon` package. The issue has been fixed with proper fallback imports.

---

## 📦 Current Status: READY FOR TESTING

Your Anki Voice Review Add-on is now properly structured and packaged! Here's how to test and install it.

## 🎯 Step-by-Step Installation

### **Step 1: Verify Package**
```bash
# Check that the package exists and is the right size
ls -la voice_review_addon.ankiaddon
# Should show: ~32KB file
```

### **Step 2: Open Anki**
1. Launch Anki on your computer
2. Make sure you're on a profile you can test with
3. Close any open study sessions

### **Step 3: Install the Add-on**
1. Go to **Tools → Add-ons**
2. Click **"Install from file..."** button
3. Navigate to your project directory
4. Select `voice_review_addon.ankiaddon`
5. Click **Open**
6. You should see: "Add-on installed successfully"

### **Step 4: Restart Anki**
1. Close Anki completely
2. Reopen Anki
3. Load your profile

### **Step 5: Verify Installation**
1. Go to **Tools** menu
2. Look for **"Voice Review"** submenu
3. You should see:
   - Start MCP Server
   - Stop MCP Server  
   - Show Voice Assistant
   - Configuration
   - Help

## 🧪 Testing the Add-on

### **Test 1: Menu Integration**
```
✅ Tools → Voice Review menu appears
✅ All menu items are clickable
✅ Configuration dialog opens
✅ Help dialog shows information
```

### **Test 2: MCP Server**
```
1. Click Tools → Voice Review → Start MCP Server
2. Should show: "MCP Server started successfully!"
3. Click Tools → Voice Review → Stop MCP Server  
4. Should show: "MCP Server stopped."
```

### **Test 3: Voice Assistant**
```
1. Click Tools → Voice Review → Show Voice Assistant
2. Should show voice control interface
3. Check status bar for voice indicator
```

### **Test 4: Configuration**
```
1. Click Tools → Voice Review → Configuration
2. Should open Anki's built-in config dialog
3. Verify all settings are present:
   - auto_start_mcp: true
   - elevenlabs_agent_id: agent_5301k0wccfefeaxtkqr0kce7v66a
   - mcp_server_port: 8000
   - etc.
```

## 🎨 Add Voice Controls to Cards

### **Step 1: Get the Template Code**
```bash
python templates/anki_card_voice_buttons.py
```

This will output three sections:
1. **HTML** - for card templates
2. **CSS** - for styling
3. **JavaScript** - for functionality

### **Step 2: Edit a Card Type**
1. Go to **Tools → Manage Note Types**
2. Select a note type to test with
3. Click **Cards...**

### **Step 3: Add HTML**
1. In the **Front Template** or **Back Template**
2. Add the HTML code at the bottom:
```html
<!-- Voice Control Buttons -->
<div id="voice-controls" class="voice-control-panel">
    <!-- Full HTML from the template generator -->
</div>
```

### **Step 4: Add CSS**
1. In the **Styling** section
2. Add the complete CSS code

### **Step 5: Add JavaScript**
1. In the **Back Template** (important!)
2. Add the complete JavaScript code wrapped in `<script>` tags

### **Step 6: Save & Test**
1. Click **Save**
2. Go to study mode
3. Look for voice control panel in bottom-right corner

## 🎤 Test Voice Controls

### **Test 1: Basic Functionality**
```
1. Open a flashcard with voice controls
2. Click "Start Voice" button
3. Should show: "Starting MCP Server..." → "MCP Connected" → "Voice Active"
4. Voice control buttons should appear
5. Status indicator should be green
```

### **Test 2: Voice Commands**
```
1. Start voice session
2. Say "next card" → should advance card
3. Say "show answer" → should reveal answer  
4. Say "I forgot" → should rate as Again (1)
5. Say "got it" → should rate as Good (3)
```

### **Test 3: Session Stats**
```
1. Complete several cards with voice
2. Stop voice session
3. Should show session summary:
   "Session complete! X cards in Ys (Z% accuracy)"
```

## 🐛 Troubleshooting

### **Issue: Add-on won't install**
```
Solutions:
- Check file isn't corrupted (should be ~32KB)
- Try restarting Anki
- Check Anki version (needs 2.1.50+)
- Look for error messages in Tools → Add-ons
```

### **Issue: Menu doesn't appear**
```
Solutions:
- Restart Anki completely
- Check Tools → Add-ons → [addon] → Config
- Look for error messages in debug console
- Try disabling other add-ons temporarily
```

### **Issue: MCP Server won't start**
```
Solutions:
- Check port 8000 isn't in use
- Try different port in configuration
- Check Python dependencies installed
- Look in Anki debug console for errors
```

### **Issue: Voice controls don't appear on cards**
```
Solutions:
- Make sure HTML, CSS, and JavaScript are all added
- JavaScript must be in Back Template
- Check browser console for errors (F12)
- Verify card template saved correctly
```

### **Issue: Voice recognition not working**
```
Solutions:
- Use Chrome or Edge browser (best support)
- Grant microphone permissions
- Check microphone is working in other apps
- Try different voice commands
```

## 📊 Success Criteria

### **✅ Installation Success**
- [ ] Add-on installs without errors
- [ ] Voice Review menu appears in Tools
- [ ] Configuration dialog opens
- [ ] MCP server starts and stops successfully

### **✅ Voice Control Success**  
- [ ] Voice control panel appears on cards
- [ ] "Start Voice" button works
- [ ] MCP server starts automatically
- [ ] Voice commands are recognized
- [ ] Card navigation works
- [ ] Session statistics display

### **✅ ElevenLabs Integration Success**
- [ ] Agent ID configured correctly
- [ ] Natural language processing works
- [ ] Voice feedback is clear
- [ ] Mobile app compatibility

## 🎯 Next Steps After Successful Testing

### **1. Customize Settings**
- Update ElevenLabs agent ID if needed
- Adjust natural language mappings
- Configure UI preferences

### **2. Add to Multiple Card Types**
- Apply voice controls to all your note types
- Customize styling for different subjects
- Test with various card formats

### **3. Train Your Voice**
- Practice natural language commands
- Learn keyboard shortcuts (Ctrl+V, Ctrl+N, Ctrl+S)
- Experiment with session management

### **4. Mobile Setup** 
- Install ElevenLabs mobile app
- Connect to same agent
- Test commute studying workflow

## 📞 Getting Help

### **If you encounter issues:**
1. Check the debug console: Tools → Debug Console
2. Look for error messages in add-on manager
3. Try with a fresh Anki profile
4. Check the backup_old_files/ for reference
5. Review configuration settings

### **Debug Console Commands:**
```python
# Check if add-on loaded
print([addon for addon in mw.addonManager.allAddons() if 'voice' in addon.lower()])

# Check configuration
print(mw.addonManager.getConfig('voice_review_addon'))

# Test MCP server
from voice_review_addon import get_addon
addon = get_addon()
print(addon.get_status())
```

**Happy voice studying! 🎉** 
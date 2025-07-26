# 📦 Packaging Instructions for Voice Review Add-on

This document explains how to properly package the Voice Review add-on for distribution following [Anki's add-on guidelines](https://addon-docs.ankiweb.net/sharing.html).

## 🏗️ Project Structure

The add-on follows the proper Anki add-on structure:

```
voice_review_addon_proper/
├── __init__.py              # ✅ Main entry point (required)
├── manifest.json            # ✅ Add-on metadata (required for external distribution)
├── config.json             # ✅ User configuration (Anki standard)
├── config.md               # ✅ Configuration documentation (Anki standard)
├── README.md               # 📝 Documentation
├── requirements.txt        # 📋 Python dependencies
├── core/                   # 🔧 Core functionality
│   └── mcp_server.py
├── ui/                     # 🎨 User interface
│   ├── menu_integration.py
│   └── voice_controls.py
├── utils/                  # 🛠️ Utilities
│   └── config_manager.py
├── web/                    # 🌐 Web assets
│   └── voice_card_controls.js
└── templates/              # 📄 Templates
    └── anki_card_voice_buttons.py
```

## 📋 Pre-packaging Checklist

### ✅ Required Files
- [x] `__init__.py` - Main entry point
- [x] `manifest.json` - Add-on metadata
- [x] `config.json` - User configuration
- [x] `config.md` - Configuration documentation

### ✅ Code Quality
- [x] All imports work correctly
- [x] No syntax errors
- [x] Proper error handling
- [x] Logging configured
- [x] Type hints where appropriate

### ✅ Dependencies
- [x] All dependencies listed in `requirements.txt`
- [x] Only necessary dependencies included
- [x] Version constraints specified

### ✅ Testing
- [x] Add-on loads without errors
- [x] Menu integration works
- [x] Configuration dialog works
- [x] MCP server starts correctly
- [x] Voice controls integrate properly

## 📦 Packaging Steps

### 1. **Clean the Directory**
Remove any development files:

```bash
# Remove Python cache files
find voice_review_addon_proper -name "__pycache__" -type d -exec rm -rf {} +
find voice_review_addon_proper -name "*.pyc" -delete

# Remove development files
rm -f voice_review_addon_proper/.DS_Store
rm -f voice_review_addon_proper/*/.DS_Store
```

### 2. **Validate Structure**
Ensure proper structure:

```bash
cd voice_review_addon_proper
ls -la
# Should show: __init__.py, manifest.json, config.json, config.md, etc.
```

### 3. **Create .ankiaddon File**

**Method A: Command Line (Unix/macOS/Linux)**
```bash
cd voice_review_addon_proper
zip -r ../voice_review_addon.ankiaddon * -x "*.pyc" "*__pycache__*" "*.DS_Store"
```

**Method B: Manual Zip**
1. Select ALL files inside `voice_review_addon_proper/`
2. Create zip archive
3. Rename to `voice_review_addon.ankiaddon`

**⚠️ CRITICAL: Do NOT include the parent folder in the zip!**

**✅ Correct zip contents:**
```
voice_review_addon.ankiaddon/
├── __init__.py
├── manifest.json
├── config.json
├── config.md
└── core/...
```

**❌ Incorrect zip contents:**
```
voice_review_addon.ankiaddon/
└── voice_review_addon_proper/
    ├── __init__.py
    ├── manifest.json
    └── ...
```

### 4. **Verify Package**
Test the package:

```bash
# Extract to test directory
unzip voice_review_addon.ankiaddon -d test_extract/
# Should see __init__.py directly in test_extract/
```

## 🌐 Distribution Options

### **Option 1: AnkiWeb (Recommended)**
1. Go to [AnkiWeb Add-ons](https://ankiweb.net/shared/addons/)
2. Click "Upload" button
3. Upload `voice_review_addon.ankiaddon` file
4. Fill in description and details
5. Submit for review

### **Option 2: GitHub Releases**
1. Create GitHub release
2. Upload `voice_review_addon.ankiaddon` as asset
3. Write release notes
4. Tag with version number

### **Option 3: Direct Distribution**
- Share `voice_review_addon.ankiaddon` file directly
- Users install via "Install from file" in Anki

## 📋 Manifest.json Explained

```json
{
    "name": "Voice Review with AI Assistant",
    "package": "voice_review_addon",        // Folder name in Anki
    "author": "Matheus Rech",
    "version": "1.0.0",                     // Semantic versioning
    "description": "Hands-free flashcard review...",
    "homepage": "https://github.com/...",   // Optional
    "conflicts": [],                        // Conflicting add-on IDs
    "mod": 1738239600,                     // Unix timestamp
    "min_point_version": 50,               // Minimum Anki 2.1.50
    "max_point_version": 0,                // 0 = no maximum
    "human_version": "1.0.0"               // User-friendly version
}
```

## 📊 Version Management

### **Semantic Versioning**
- `MAJOR.MINOR.PATCH` (e.g., 1.0.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

### **Update Process**
1. Update version in `manifest.json`
2. Update `mod` timestamp: `date +%s`
3. Create new package
4. Test installation
5. Release/upload

## 🧪 Testing Checklist

### **Pre-Release Testing**
- [ ] Install in fresh Anki profile
- [ ] Verify menu appears in Tools
- [ ] Test MCP server startup
- [ ] Test voice controls on cards
- [ ] Test configuration dialog
- [ ] Check error handling
- [ ] Verify uninstallation

### **Cross-Platform Testing**
- [ ] Windows 10/11
- [ ] macOS (Intel/Apple Silicon)
- [ ] Linux (Ubuntu/Fedora)
- [ ] Different Anki versions (2.1.50+)

## 🚨 Common Packaging Errors

### **❌ Wrong Zip Structure**
```
voice_review_addon.ankiaddon/
└── voice_review_addon_proper/  # ❌ Don't include parent folder
    └── __init__.py
```

### **❌ Python Cache Files**
```
__pycache__/        # ❌ Remove these
*.pyc              # ❌ Remove these
```

### **❌ Missing manifest.json**
```
# ❌ Without manifest.json, external distribution won't work
```

### **❌ Import Errors**
```python
# ❌ Absolute imports that don't work in Anki
from voice_review_addon.core import something

# ✅ Relative imports
from .core import something
```

## 📈 Post-Release

### **User Support**
- Monitor GitHub issues
- Respond to AnkiWeb reviews
- Update documentation
- Fix critical bugs quickly

### **Analytics**
- Track download numbers
- Monitor user feedback
- Plan future features
- Version adoption rates

## 🔄 Update Releases

### **For Bug Fixes**
1. Increment PATCH version (1.0.0 → 1.0.1)
2. Update manifest.json
3. Create new package
4. Upload to AnkiWeb/GitHub

### **For New Features**
1. Increment MINOR version (1.0.1 → 1.1.0)
2. Update documentation
3. Test thoroughly
4. Release announcement

## 📞 Support Channels

### **For Users**
- GitHub Issues for bugs
- GitHub Discussions for questions
- Email support for critical issues
- AnkiWeb reviews and ratings

### **For Developers**
- Code review via Pull Requests
- Technical discussions in Issues
- Documentation improvements
- Feature collaboration

---

## 🎯 Final Packaging Command

```bash
# Complete packaging in one command
cd voice_review_addon_proper && \
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
find . -name "*.pyc" -delete && \
rm -f .DS_Store */.DS_Store && \
zip -r ../voice_review_addon.ankiaddon * -x "*.pyc" "*__pycache__*" "*.DS_Store" && \
echo "✅ Package created: voice_review_addon.ankiaddon" && \
cd .. && ls -la voice_review_addon.ankiaddon
```

**The add-on is now ready for distribution!** 🚀 
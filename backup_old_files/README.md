# Anki MCP Server

A comprehensive Model Context Protocol (MCP) server that provides Anki operations optimized for voice-controlled studying and commuting scenarios. This server integrates seamlessly with the Voice Review Add-on to provide AI assistants with deep Anki knowledge and capabilities.

## Features

### 🎯 Core Tools
- **Study Session Management**: Get due cards, create commute sessions, analyze progress
- **Card Operations**: Search, retrieve details, generate hints, format for speech
- **Analytics**: Deck statistics, review history, learning progress insights
- **Voice Optimization**: Speech-friendly formatting, pronunciation hints, timing

### 📚 Knowledge Resources
- **Architecture Documentation**: Complete Anki internals guide
- **Scheduling Algorithm**: Spaced repetition implementation details
- **Add-on Development**: Comprehensive development guide
- **Database Schema**: SQLite structure and relationships
- **Voice Study Guides**: Best practices for hands-free learning
- **Card Templates**: Voice-optimized formats and examples

## Installation

### Prerequisites
- Python 3.9+ (matching your Anki version)
- Anki installed with an existing collection
- MCP-compatible client (Claude Desktop, etc.)

### Quick Setup

1. **Clone or download** this repository to your desired location:
```bash
git clone <repository-url> anki-mcp-server
cd anki-mcp-server
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Test the server**:
```bash
python anki_mcp_server.py
```

4. **Configure your MCP client** (see [Client Configuration](#client-configuration) below)

### Client Configuration

#### Claude Desktop
Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "anki-mcp-server": {
      "command": "python",
      "args": ["/path/to/anki-mcp-server/anki_mcp_server.py"],
      "env": {
        "ANKI_COLLECTION_PATH": "/path/to/your/collection.anki2"
      }
    }
  }
}
```

#### Other MCP Clients
Use the configuration format appropriate for your client, referencing:
- **Command**: `python`
- **Arguments**: `["/path/to/anki_mcp_server.py"]`
- **Working Directory**: Path to this server directory

## Usage

### Basic Operations

Once connected, you can ask your AI assistant to:

```
"Show me my due cards for today"
"Get statistics for my Spanish deck"
"Create a 15-minute commute study session"
"Format card 12345 for text-to-speech"
"Analyze my learning progress this month"
"Generate hints for difficult cards"
```

### Voice Study Commands

The server understands natural language for voice-optimized studying:

```
"I need a hands-free study session"
"What cards should I review while driving?"
"Make this card easier to understand by voice"
"How am I doing with my German vocabulary?"
"Give me pronunciation hints for this card"
```

### Accessing Documentation

Request comprehensive Anki knowledge:

```
"Show me the Anki scheduling algorithm documentation"
"How do I develop Anki add-ons?"
"What are best practices for voice studying?"
"Explain the Anki database schema"
```

## Integration with Voice Review Add-on

This MCP server is designed to complement the Voice Review Add-on:

### Workflow Integration
1. **Session Planning**: Use MCP tools to analyze due cards and create optimized sessions
2. **Voice Optimization**: Format cards for optimal TTS presentation
3. **Progress Tracking**: Analyze performance and adjust study strategies
4. **Content Curation**: Identify and modify cards that work well with voice

### Example Integration
```python
# In your voice review add-on
async def get_commute_session(duration_minutes=15):
    # Use MCP server to get optimized card set
    session_data = await mcp_client.call_tool(
        "get_commute_session",
        {"duration_minutes": duration_minutes, "difficulty_level": "mixed"}
    )
    return session_data
```

## Configuration

### Environment Variables
- `ANKI_COLLECTION_PATH`: Path to your Anki collection file
- `MCP_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `MCP_MAX_CARDS`: Maximum cards returned per query (default: 100)

### Collection Auto-Discovery
The server automatically searches for Anki collections in standard locations:
- **macOS**: `~/Library/Application Support/Anki2/User 1/collection.anki2`
- **Windows**: `~/AppData/Roaming/Anki2/User 1/collection.anki2`
- **Linux**: `~/.local/share/Anki2/User 1/collection.anki2`

## Available Tools

### Study Session Tools
- `get_due_cards`: Retrieve cards due for review
- `get_commute_session`: Create optimized hands-free study sessions
- `search_cards`: Find cards using Anki search syntax

### Card Information Tools
- `get_card_details`: Get comprehensive card information
- `format_card_for_speech`: Optimize content for TTS
- `generate_study_hints`: Create contextual learning hints

### Analytics Tools
- `get_deck_statistics`: Deck performance metrics
- `get_review_history`: Historical review data
- `analyze_learning_progress`: Performance insights and recommendations

### System Tools
- `check_connection`: Verify Anki collection connectivity

## Available Resources

### Documentation
- `anki://docs/architecture`: Anki's internal architecture
- `anki://docs/scheduling`: Spaced repetition algorithm
- `anki://docs/addon-development`: Add-on development guide
- `anki://docs/database-schema`: Database structure

### Guides
- `anki://docs/voice-study-best-practices`: Voice study optimization
- `anki://docs/commute-study-guide`: Hands-free studying guide

### Templates & Examples
- `anki://templates/card-formats`: Voice-optimized card templates
- `anki://examples/voice-commands`: Natural language examples

## Safety Features

### Read-Only Mode
- Server operates in read-only mode by default
- Automatic collection backup before any operations
- No modification of existing cards or notes
- Safe for use while Anki is running

### Error Handling
- Graceful degradation when collection is unavailable
- Comprehensive logging for troubleshooting
- Safe disconnection on errors

## Development

### Running Tests
```bash
pytest tests/
```

### Adding New Tools
1. Define tool schema in `_setup_tools()`
2. Implement handler in `handle_call_tool()`
3. Add helper methods as needed
4. Update documentation

### Adding New Resources
1. Define resource in `_setup_resources()`
2. Implement content method
3. Update configuration

## Troubleshooting

### Common Issues

**Collection Not Found**
- Verify Anki is installed and has been opened at least once
- Check collection path in configuration
- Ensure proper file permissions

**Connection Errors**
- Close Anki if using collection file directly
- Check if collection file is corrupted
- Verify Python version compatibility

**Performance Issues**
- Reduce `max_cards_per_query` setting
- Use more specific search queries
- Check available system memory

### Debug Mode
Enable detailed logging:
```bash
MCP_LOG_LEVEL=DEBUG python anki_mcp_server.py
```

## Contributing

### Guidelines
- Follow existing code style and patterns
- Add comprehensive documentation for new features
- Include tests for new functionality
- Ensure voice-study optimization for new tools

### Pull Requests
1. Fork the repository
2. Create feature branch
3. Add tests and documentation
4. Submit pull request with detailed description

## License

This project is licensed under the same terms as the Anki project. See LICENSE file for details.

## Support

### Documentation
- Check the comprehensive resources available through the MCP server
- Review voice study best practices guides
- Consult add-on development documentation

### Issues
- Report bugs through the repository issue tracker
- Include log output and system information
- Describe steps to reproduce the issue

### Community
- Join Anki add-on development discussions
- Share voice study techniques and optimizations
- Contribute to documentation and examples

## Changelog

### Version 1.0.0
- Initial release with core tools and resources
- Voice-optimized study session support
- Comprehensive Anki documentation
- Read-only safety mode
- Auto-discovery of collection files

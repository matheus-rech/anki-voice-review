#!/usr/bin/env python3
"""
MCP Server for Anki Voice Review Add-on
Provides Model Context Protocol interface for AI assistants
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import traceback
import os
import tempfile
import shutil

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Resource, 
        Tool, 
        TextContent, 
        ImageContent, 
        EmbeddedResource,
        LoggingLevel
    )
    MCP_AVAILABLE = True
except ImportError:
    # Fallback definitions when MCP is not available
    class TextContent:
        def __init__(self, type: str = "text", text: str = ""):
            self.type = type
            self.text = text
    
    class Resource:
        pass
    
    class Tool:
        pass
    
    MCP_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("anki-mcp-server")

class AnkiCollection:
    """
    Wrapper for Anki collection operations.
    
    This class provides a safe interface to Anki's database without requiring
    the full Anki application to be running.
    """
    
    def __init__(self, collection_path: Optional[str] = None):
        self.collection_path = collection_path
        self.db = None
        self._connected = False
        
        # Try to find Anki collection automatically
        if not collection_path:
            self.collection_path = self._find_collection_path()
            
    def _find_collection_path(self) -> Optional[str]:
        """Find the Anki collection file automatically."""
        possible_paths = [
            # macOS
            os.path.expanduser("~/Library/Application Support/Anki2/User 1/collection.anki2"),
            # Windows
            os.path.expanduser("~/AppData/Roaming/Anki2/User 1/collection.anki2"),
            # Linux
            os.path.expanduser("~/.local/share/Anki2/User 1/collection.anki2"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found Anki collection at: {path}")
                return path
        
        logger.warning("Could not find Anki collection automatically")
        return None
    
    def connect(self) -> bool:
        """Connect to the Anki collection."""
        if not self.collection_path or not os.path.exists(self.collection_path):
            logger.error(f"Collection file not found: {self.collection_path}")
            return False
            
        try:
            # Create a backup copy for safety
            backup_path = f"{self.collection_path}.mcp_backup"
            if not os.path.exists(backup_path):
                shutil.copy2(self.collection_path, backup_path)
                logger.info(f"Created backup at: {backup_path}")
            
            # Connect to database (read-only for safety)
            self.db = sqlite3.connect(self.collection_path)
            self.db.row_factory = sqlite3.Row
            self._connected = True
            logger.info("Connected to Anki collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to collection: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the Anki collection."""
        if self.db:
            self.db.close()
            self.db = None
        self._connected = False
        logger.info("Disconnected from Anki collection")
    
    def is_connected(self) -> bool:
        """Check if connected to collection."""
        return self._connected and self.db is not None
    
    def get_due_cards(self, deck_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cards that are due for review."""
        if not self.is_connected():
            return []
        
        try:
            query = """
            SELECT c.id, c.nid, c.did, c.ord, c.mod, c.usn, c.type, c.queue, 
                   c.due, c.ivl, c.factor, c.reps, c.lapses, c.left, c.odue, 
                   c.odid, c.flags, c.data,
                   n.flds, n.tags, n.mid,
                   d.name as deck_name
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN decks d ON c.did = d.id
            WHERE c.queue IN (1, 2, 3) AND c.due <= ?
            """
            
            params = [int(datetime.now().timestamp() / 86400)]  # Today's day number
            
            if deck_name:
                query += " AND d.name LIKE ?"
                params.append(f"%{deck_name}%")
            
            query += f" ORDER BY c.due LIMIT {limit}"
            
            cursor = self.db.execute(query, params)
            cards = []
            
            for row in cursor.fetchall():
                card_data = dict(row)
                # Parse fields
                fields = card_data['flds'].split('\x1f')
                card_data['fields'] = fields
                card_data['tags_list'] = card_data['tags'].split() if card_data['tags'] else []
                cards.append(card_data)
            
            return cards
            
        except Exception as e:
            logger.error(f"Error getting due cards: {e}")
            return []
    
    def get_card_details(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific card."""
        if not self.is_connected():
            return None
        
        try:
            query = """
            SELECT c.*, n.flds, n.tags, n.mid, d.name as deck_name,
                   m.name as model_name, m.flds as model_fields
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN decks d ON c.did = d.id
            JOIN models m ON n.mid = m.id
            WHERE c.id = ?
            """
            
            cursor = self.db.execute(query, [card_id])
            row = cursor.fetchone()
            
            if row:
                card_data = dict(row)
                # Parse fields
                fields = card_data['flds'].split('\x1f')
                card_data['fields'] = fields
                card_data['tags_list'] = card_data['tags'].split() if card_data['tags'] else []
                
                # Parse model fields
                model_fields = json.loads(card_data['model_fields'])
                field_names = [f['name'] for f in model_fields]
                card_data['field_names'] = field_names
                
                # Create field dictionary
                card_data['fields_dict'] = dict(zip(field_names, fields))
                
                return card_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting card details: {e}")
            return None

class AnkiMCPServer:
    """
    Main MCP server for Anki operations.
    
    Provides tools and resources for interacting with Anki collections,
    optimized for voice-controlled studying and commuting scenarios.
    """
    
    def __init__(self):
        if not MCP_AVAILABLE:
            logger.error("MCP library not available")
            raise ImportError("MCP library required but not found")
            
        self.server = Server("anki-mcp-server")
        self.anki = AnkiCollection()
        self._setup_tools()
        self._setup_resources()
        
        # Connect to Anki collection
        if not self.anki.connect():
            logger.warning("Could not connect to Anki collection")
        
    def _setup_tools(self):
        """Set up MCP tools for Anki operations."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name="get_due_cards",
                    description="Get cards that are due for review, optionally filtered by deck",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "deck_name": {
                                "type": "string",
                                "description": "Optional deck name to filter cards (supports partial matching)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of cards to return (default: 50)",
                                "default": 50
                            }
                        }
                    }
                ),
                Tool(
                    name="get_card_details",
                    description="Get detailed information about a specific card",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "card_id": {
                                "type": "integer",
                                "description": "The ID of the card to retrieve"
                            }
                        },
                        "required": ["card_id"]
                    }
                ),
                Tool(
                    name="check_connection",
                    description="Check connection to Anki collection and return status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[TextContent]:
            """Handle tool calls."""
            try:
                if name == "get_due_cards":
                    return await self._get_due_cards(arguments)
                elif name == "get_card_details":
                    return await self._get_card_details(arguments)
                elif name == "check_connection":
                    return await self._check_connection(arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            except Exception as e:
                logger.error(f"Error handling tool call {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _get_due_cards(self, arguments: dict) -> List[TextContent]:
        """Get due cards tool implementation."""
        deck_name = arguments.get("deck_name")
        limit = arguments.get("limit", 50)
        
        cards = self.anki.get_due_cards(deck_name, limit)
        
        if not cards:
            return [TextContent(type="text", text="No due cards found")]
        
        result = f"Found {len(cards)} due cards:\n\n"
        for card in cards[:10]:  # Show first 10
            fields = card.get('fields', [])
            front = fields[0] if fields else "No content"
            result += f"Card ID: {card['id']}\n"
            result += f"Deck: {card['deck_name']}\n"
            result += f"Front: {front[:100]}...\n"
            result += f"Due: {card['due']}\n\n"
        
        if len(cards) > 10:
            result += f"... and {len(cards) - 10} more cards"
        
        return [TextContent(type="text", text=result)]
    
    async def _get_card_details(self, arguments: dict) -> List[TextContent]:
        """Get card details tool implementation."""
        card_id = arguments.get("card_id")
        
        if not card_id:
            return [TextContent(type="text", text="Card ID required")]
        
        card = self.anki.get_card_details(card_id)
        
        if not card:
            return [TextContent(type="text", text=f"Card {card_id} not found")]
        
        result = f"Card Details (ID: {card_id}):\n\n"
        result += f"Deck: {card['deck_name']}\n"
        result += f"Model: {card['model_name']}\n"
        result += f"Due: {card['due']}\n"
        result += f"Interval: {card['ivl']} days\n"
        result += f"Ease: {card['factor']}\n"
        result += f"Reviews: {card['reps']}\n"
        result += f"Lapses: {card['lapses']}\n\n"
        
        result += "Fields:\n"
        fields_dict = card.get('fields_dict', {})
        for name, value in fields_dict.items():
            result += f"  {name}: {value[:100]}...\n"
        
        if card.get('tags_list'):
            result += f"\nTags: {', '.join(card['tags_list'])}\n"
        
        return [TextContent(type="text", text=result)]
    
    async def _check_connection(self, arguments: dict) -> List[TextContent]:
        """Check connection tool implementation."""
        if self.anki.is_connected():
            return [TextContent(type="text", text="✅ Connected to Anki collection")]
        else:
            return [TextContent(type="text", text="❌ Not connected to Anki collection")]
    
    def _setup_resources(self):
        """Set up MCP resources."""
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="anki://status",
                    name="Anki Connection Status",
                    description="Current connection status to Anki collection",
                    mimeType="text/plain"
                )
            ]
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "anki://status":
                if self.anki.is_connected():
                    return "Connected to Anki collection"
                else:
                    return "Not connected to Anki collection"
            else:
                raise ValueError(f"Unknown resource: {uri}")

    async def run(self):
        """Run the MCP server."""
        if not MCP_AVAILABLE:
            logger.error("Cannot run MCP server - MCP library not available")
            return
            
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="anki-mcp-server",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=None,
                            experimental_capabilities={}
                        )
                    )
                )
        except Exception as e:
            logger.error(f"MCP server error: {e}")
        finally:
            self.anki.disconnect()

def main():
    """Main entry point for standalone server."""
    try:
        server = AnkiMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 
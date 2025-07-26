#!/usr/bin/env python3
"""
Anki MCP Server

A Model Context Protocol server that provides comprehensive Anki operations
for voice-controlled studying and commuting scenarios.

This server exposes Anki's core functionality through MCP tools and resources,
enabling AI assistants to interact with Anki collections, manage cards,
and provide intelligent study assistance.
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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('anki_mcp_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("anki-mcp-server")

class AnkiCollection:
    """
    Wrapper for Anki collection operations.
    
    This class provides a safe interface to Anki's database without requiring
    the full Anki application to be running. It can work with collection files
    directly or connect to a running Anki instance via AnkiConnect.
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
            self.db = sqlite3.connect(f"file:{self.collection_path}?mode=ro", uri=True)
            self.db.row_factory = sqlite3.Row
            self._connected = True
            logger.info("Successfully connected to Anki collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to collection: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the collection."""
        if self.db:
            self.db.close()
            self.db = None
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to collection."""
        return self._connected and self.db is not None
    
    def get_due_cards(self, deck_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cards due for review."""
        if not self.is_connected():
            return []
        
        try:
            # Base query for due cards
            query = """
            SELECT c.id, c.nid, c.did, c.ord, c.type, c.queue, c.due, c.ivl, c.factor, c.reps, c.lapses,
                   n.flds, n.tags, n.mid,
                   d.name as deck_name
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN decks d ON c.did = d.id
            WHERE c.queue IN (1, 2, 3)  -- Learning, review, day learning
            """
            
            params = []
            
            # Filter by deck if specified
            if deck_name:
                query += " AND d.name LIKE ?"
                params.append(f"%{deck_name}%")
            
            # Order by due date and limit
            query += " ORDER BY c.due ASC LIMIT ?"
            params.append(limit)
            
            cursor = self.db.execute(query, params)
            cards = []
            
            for row in cursor.fetchall():
                # Parse note fields
                fields = row['flds'].split('\x1f')  # Anki's field separator
                
                card_data = {
                    'id': row['id'],
                    'note_id': row['nid'],
                    'deck_id': row['did'],
                    'deck_name': row['deck_name'],
                    'ord': row['ord'],
                    'type': row['type'],
                    'queue': row['queue'],
                    'due': row['due'],
                    'interval': row['ivl'],
                    'ease_factor': row['factor'],
                    'reps': row['reps'],
                    'lapses': row['lapses'],
                    'fields': fields,
                    'tags': row['tags'].split(),
                    'model_id': row['mid']
                }
                
                # Get note type information
                card_data.update(self._get_note_type_info(row['mid']))
                cards.append(card_data)
            
            return cards
            
        except Exception as e:
            logger.error(f"Error getting due cards: {e}")
            return []
    
    def _get_note_type_info(self, model_id: int) -> Dict[str, Any]:
        """Get note type (model) information."""
        try:
            cursor = self.db.execute("SELECT name, flds, tmpls FROM notetypes WHERE id = ?", (model_id,))
            row = cursor.fetchone()
            
            if not row:
                return {'note_type': 'Unknown', 'field_names': [], 'templates': []}
            
            # Parse field and template information
            fields_data = json.loads(row['flds'])
            templates_data = json.loads(row['tmpls'])
            
            return {
                'note_type': row['name'],
                'field_names': [f['name'] for f in fields_data],
                'templates': [{'name': t['name'], 'qfmt': t['qfmt'], 'afmt': t['afmt']} for t in templates_data]
            }
            
        except Exception as e:
            logger.error(f"Error getting note type info: {e}")
            return {'note_type': 'Unknown', 'field_names': [], 'templates': []}
    
    def get_card_by_id(self, card_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific card by ID."""
        if not self.is_connected():
            return None
        
        try:
            query = """
            SELECT c.*, n.flds, n.tags, n.mid, d.name as deck_name
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN decks d ON c.did = d.id
            WHERE c.id = ?
            """
            
            cursor = self.db.execute(query, (card_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            fields = row['flds'].split('\x1f')
            card_data = dict(row)
            card_data['fields'] = fields
            card_data['tags'] = row['tags'].split()
            card_data.update(self._get_note_type_info(row['mid']))
            
            return card_data
            
        except Exception as e:
            logger.error(f"Error getting card {card_id}: {e}")
            return None
    
    def search_cards(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for cards using Anki-style queries."""
        if not self.is_connected():
            return []
        
        try:
            # Convert simple search queries to SQL
            # This is a simplified version - full Anki search is very complex
            
            sql_conditions = []
            params = []
            
            # Parse basic search terms
            terms = query.split()
            for term in terms:
                if ':' in term:
                    # Handle special searches like deck:name, tag:tag
                    key, value = term.split(':', 1)
                    if key == 'deck':
                        sql_conditions.append("d.name LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'tag':
                        sql_conditions.append("n.tags LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'is':
                        if value == 'due':
                            sql_conditions.append("c.queue IN (1, 2, 3)")
                        elif value == 'new':
                            sql_conditions.append("c.queue = 0")
                else:
                    # Search in note fields
                    sql_conditions.append("n.flds LIKE ?")
                    params.append(f"%{term}%")
            
            base_query = """
            SELECT c.id, c.nid, c.did, c.ord, c.type, c.queue, c.due, c.ivl, c.factor, c.reps, c.lapses,
                   n.flds, n.tags, n.mid, d.name as deck_name
            FROM cards c
            JOIN notes n ON c.nid = n.id
            JOIN decks d ON c.did = d.id
            """
            
            if sql_conditions:
                base_query += " WHERE " + " AND ".join(sql_conditions)
            
            base_query += " LIMIT ?"
            params.append(limit)
            
            cursor = self.db.execute(base_query, params)
            cards = []
            
            for row in cursor.fetchall():
                fields = row['flds'].split('\x1f')
                card_data = dict(row)
                card_data['fields'] = fields
                card_data['tags'] = row['tags'].split()
                card_data.update(self._get_note_type_info(row['mid']))
                cards.append(card_data)
            
            return cards
            
        except Exception as e:
            logger.error(f"Error searching cards: {e}")
            return []
    
    def get_deck_stats(self, deck_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for decks."""
        if not self.is_connected():
            return {}
        
        try:
            # Base query for deck statistics
            query = """
            SELECT d.name, d.id,
                   COUNT(CASE WHEN c.queue = 0 THEN 1 END) as new_cards,
                   COUNT(CASE WHEN c.queue IN (1, 3) THEN 1 END) as learning_cards,
                   COUNT(CASE WHEN c.queue = 2 THEN 1 END) as review_cards,
                   COUNT(c.id) as total_cards,
                   AVG(CASE WHEN c.queue = 2 THEN c.ivl END) as avg_interval,
                   AVG(CASE WHEN c.queue = 2 THEN c.factor END) as avg_ease
            FROM decks d
            LEFT JOIN cards c ON d.id = c.did
            """
            
            params = []
            if deck_name:
                query += " WHERE d.name LIKE ?"
                params.append(f"%{deck_name}%")
            
            query += " GROUP BY d.id, d.name ORDER BY d.name"
            
            cursor = self.db.execute(query, params)
            
            stats = {}
            for row in cursor.fetchall():
                stats[row['name']] = {
                    'deck_id': row['id'],
                    'new_cards': row['new_cards'] or 0,
                    'learning_cards': row['learning_cards'] or 0,
                    'review_cards': row['review_cards'] or 0,
                    'total_cards': row['total_cards'] or 0,
                    'average_interval': round(row['avg_interval'] or 0, 1),
                    'average_ease': round((row['avg_ease'] or 2500) / 10, 1)  # Convert to percentage
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting deck stats: {e}")
            return {}
    
    def get_review_history(self, days: int = 30, card_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get review history."""
        if not self.is_connected():
            return []
        
        try:
            # Calculate timestamp for N days ago
            cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            query = """
            SELECT r.id, r.cid, r.usn, r.ease, r.ivl, r.lastIvl, r.factor, r.time, r.type,
                   c.did, d.name as deck_name, n.flds
            FROM revlog r
            JOIN cards c ON r.cid = c.id
            JOIN decks d ON c.did = d.id
            JOIN notes n ON c.nid = n.id
            WHERE r.id > ?
            """
            
            params = [cutoff_timestamp]
            
            if card_id:
                query += " AND r.cid = ?"
                params.append(card_id)
            
            query += " ORDER BY r.id DESC"
            
            cursor = self.db.execute(query, params)
            reviews = []
            
            for row in cursor.fetchall():
                fields = row['flds'].split('\x1f')
                reviews.append({
                    'review_id': row['id'],
                    'card_id': row['cid'],
                    'deck_name': row['deck_name'],
                    'ease': row['ease'],
                    'interval': row['ivl'],
                    'last_interval': row['lastIvl'],
                    'ease_factor': row['factor'],
                    'time_ms': row['time'],
                    'review_type': row['type'],
                    'timestamp': row['id'],
                    'datetime': datetime.fromtimestamp(row['id'] / 1000).isoformat(),
                    'question_preview': fields[0][:100] if fields else "No content"
                })
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting review history: {e}")
            return []


class AnkiMCPServer:
    """
    Main MCP server for Anki operations.
    
    Provides tools and resources for interacting with Anki collections,
    optimized for voice-controlled studying and commuting scenarios.
    """
    
    def __init__(self):
        self.server = Server("anki-mcp-server")
        self.anki = AnkiCollection()
        self._setup_tools()
        self._setup_resources()
        
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
                    name="search_cards",
                    description="Search for cards using Anki-style queries",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g., 'deck:Spanish', 'tag:grammar', 'is:due')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 50)",
                                "default": 50
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_deck_statistics",
                    description="Get statistics for decks (new, learning, review cards)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "deck_name": {
                                "type": "string",
                                "description": "Optional specific deck name to get stats for"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_review_history",
                    description="Get recent review history with performance data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back (default: 30)",
                                "default": 30
                            },
                            "card_id": {
                                "type": "integer",
                                "description": "Optional specific card ID to get history for"
                            }
                        }
                    }
                ),
                Tool(
                    name="generate_study_hints",
                    description="Generate contextual hints for a card based on its content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "card_id": {
                                "type": "integer",
                                "description": "Card ID to generate hints for"
                            },
                            "hint_level": {
                                "type": "integer",
                                "description": "Hint level: 1=subtle, 2=moderate, 3=obvious",
                                "default": 1,
                                "minimum": 1,
                                "maximum": 3
                            }
                        },
                        "required": ["card_id"]
                    }
                ),
                Tool(
                    name="analyze_learning_progress",
                    description="Analyze learning progress and provide insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "deck_name": {
                                "type": "string",
                                "description": "Optional deck name to analyze"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to analyze (default: 30)",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_commute_session",
                    description="Get an optimized set of cards for commute/hands-free study",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "duration_minutes": {
                                "type": "integer",
                                "description": "Expected study duration in minutes",
                                "default": 15
                            },
                            "difficulty_level": {
                                "type": "string",
                                "description": "Preferred difficulty: easy, medium, hard, mixed",
                                "default": "mixed",
                                "enum": ["easy", "medium", "hard", "mixed"]
                            },
                            "deck_preference": {
                                "type": "string",
                                "description": "Optional preferred deck name"
                            }
                        }
                    }
                ),
                Tool(
                    name="format_card_for_speech",
                    description="Format card content for optimal text-to-speech presentation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "card_id": {
                                "type": "integer",
                                "description": "Card ID to format"
                            },
                            "include_hints": {
                                "type": "boolean",
                                "description": "Whether to include pronunciation hints",
                                "default": True
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
        
        # Tool handlers
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
            """Handle tool calls."""
            try:
                # Ensure we're connected
                if not self.anki.is_connected():
                    if not self.anki.connect():
                        return [TextContent(
                            type="text",
                            text="Error: Could not connect to Anki collection. Please ensure Anki is installed and the collection file is accessible."
                        )]
                
                if name == "get_due_cards":
                    cards = self.anki.get_due_cards(
                        deck_name=arguments.get("deck_name"),
                        limit=arguments.get("limit", 50)
                    )
                    
                    if not cards:
                        return [TextContent(
                            type="text",
                            text="No due cards found. Either all cards are up to date or no cards match the criteria."
                        )]
                    
                    result = f"Found {len(cards)} due cards:\n\n"
                    for i, card in enumerate(cards[:10], 1):  # Show first 10
                        question = card['fields'][0][:100] if card['fields'] else "No content"
                        result += f"{i}. Card {card['id']} ({card['deck_name']})\n"
                        result += f"   Question: {question}...\n"
                        result += f"   Type: {card['note_type']}, Due: {card['due']}\n\n"
                    
                    if len(cards) > 10:
                        result += f"... and {len(cards) - 10} more cards.\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "get_card_details":
                    card_id = arguments["card_id"]
                    card = self.anki.get_card_by_id(card_id)
                    
                    if not card:
                        return [TextContent(
                            type="text",
                            text=f"Card {card_id} not found."
                        )]
                    
                    # Format card details
                    result = f"Card {card['id']} Details:\n"
                    result += f"Deck: {card['deck_name']}\n"
                    result += f"Note Type: {card['note_type']}\n"
                    result += f"Due: {card['due']}, Interval: {card['ivl']} days\n"
                    result += f"Ease: {card['factor']/10:.1f}%, Reviews: {card['reps']}, Lapses: {card['lapses']}\n"
                    result += f"Tags: {', '.join(card['tags']) if card['tags'] else 'None'}\n\n"
                    
                    # Show fields
                    for i, (field_name, field_value) in enumerate(zip(card['field_names'], card['fields'])):
                        result += f"{field_name}: {field_value}\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "search_cards":
                    query = arguments["query"]
                    limit = arguments.get("limit", 50)
                    cards = self.anki.search_cards(query, limit)
                    
                    if not cards:
                        return [TextContent(
                            type="text",
                            text=f"No cards found matching query: {query}"
                        )]
                    
                    result = f"Found {len(cards)} cards matching '{query}':\n\n"
                    for i, card in enumerate(cards[:10], 1):
                        question = card['fields'][0][:80] if card['fields'] else "No content"
                        result += f"{i}. Card {card['id']} - {question}...\n"
                        result += f"   Deck: {card['deck_name']}, Type: {card['note_type']}\n\n"
                    
                    if len(cards) > 10:
                        result += f"... and {len(cards) - 10} more cards.\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "get_deck_statistics":
                    deck_name = arguments.get("deck_name")
                    stats = self.anki.get_deck_stats(deck_name)
                    
                    if not stats:
                        return [TextContent(
                            type="text",
                            text="No deck statistics available."
                        )]
                    
                    result = "Deck Statistics:\n\n"
                    for deck, data in stats.items():
                        result += f"📚 {deck}:\n"
                        result += f"  • New: {data['new_cards']}\n"
                        result += f"  • Learning: {data['learning_cards']}\n"
                        result += f"  • Review: {data['review_cards']}\n"
                        result += f"  • Total: {data['total_cards']}\n"
                        result += f"  • Avg Interval: {data['average_interval']} days\n"
                        result += f"  • Avg Ease: {data['average_ease']}%\n\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "get_review_history":
                    days = arguments.get("days", 30)
                    card_id = arguments.get("card_id")
                    history = self.anki.get_review_history(days, card_id)
                    
                    if not history:
                        return [TextContent(
                            type="text",
                            text=f"No review history found for the last {days} days."
                        )]
                    
                    result = f"Review History (Last {days} days):\n\n"
                    
                    # Summary statistics
                    total_reviews = len(history)
                    avg_time = sum(r['time_ms'] for r in history) / total_reviews / 1000
                    correct_reviews = sum(1 for r in history if r['ease'] > 1)
                    
                    result += f"📊 Summary:\n"
                    result += f"  • Total Reviews: {total_reviews}\n"
                    result += f"  • Average Time: {avg_time:.1f}s per card\n"
                    result += f"  • Success Rate: {correct_reviews/total_reviews*100:.1f}%\n\n"
                    
                    # Recent reviews
                    result += "🕒 Recent Reviews:\n"
                    for review in history[:10]:
                        ease_text = ["Again", "Hard", "Good", "Easy"][review['ease'] - 1] if review['ease'] <= 4 else "Unknown"
                        result += f"  • {review['datetime'][:16]} - {ease_text} ({review['time_ms']/1000:.1f}s)\n"
                        result += f"    {review['question_preview']}...\n"
                    
                    if len(history) > 10:
                        result += f"  ... and {len(history) - 10} more reviews.\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "generate_study_hints":
                    card_id = arguments["card_id"]
                    hint_level = arguments.get("hint_level", 1)
                    
                    card = self.anki.get_card_by_id(card_id)
                    if not card:
                        return [TextContent(type="text", text=f"Card {card_id} not found.")]
                    
                    # Generate hints based on card content
                    hints = self._generate_hints(card, hint_level)
                    
                    result = f"Study Hints for Card {card_id} (Level {hint_level}):\n\n"
                    for i, hint in enumerate(hints, 1):
                        result += f"{i}. {hint}\n"
                    
                    return [TextContent(type="text", text=result)]
                
                elif name == "analyze_learning_progress":
                    deck_name = arguments.get("deck_name")
                    days = arguments.get("days", 30)
                    
                    # Get review history and deck stats
                    history = self.anki.get_review_history(days)
                    stats = self.anki.get_deck_stats(deck_name)
                    
                    analysis = self._analyze_progress(history, stats, days)
                    
                    return [TextContent(type="text", text=analysis)]
                
                elif name == "get_commute_session":
                    duration = arguments.get("duration_minutes", 15)
                    difficulty = arguments.get("difficulty_level", "mixed")
                    deck_preference = arguments.get("deck_preference")
                    
                    session = self._create_commute_session(duration, difficulty, deck_preference)
                    
                    return [TextContent(type="text", text=session)]
                
                elif name == "format_card_for_speech":
                    card_id = arguments["card_id"]
                    include_hints = arguments.get("include_hints", True)
                    
                    card = self.anki.get_card_by_id(card_id)
                    if not card:
                        return [TextContent(type="text", text=f"Card {card_id} not found.")]
                    
                    formatted = self._format_for_speech(card, include_hints)
                    
                    return [TextContent(type="text", text=formatted)]
                
                elif name == "check_connection":
                    if self.anki.is_connected():
                        return [TextContent(type="text", text="✅ Connected to Anki collection successfully.")]
                    else:
                        if self.anki.connect():
                            return [TextContent(type="text", text="✅ Connected to Anki collection successfully.")]
                        else:
                            return [TextContent(type="text", text="❌ Could not connect to Anki collection. Please check if Anki is installed and collection file exists.")]
                
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                logger.error(traceback.format_exc())
                return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]
    
    def _setup_resources(self):
        """Set up MCP resources for Anki documentation and guides."""
        
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List all available resources."""
            return [
                Resource(
                    uri="anki://docs/architecture",
                    name="Anki Architecture Overview",
                    description="Comprehensive guide to Anki's internal architecture and components",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://docs/scheduling",
                    name="Anki Scheduling Algorithm",
                    description="Details about Anki's spaced repetition scheduling algorithm",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://docs/addon-development",
                    name="Add-on Development Guide",
                    description="Complete guide for developing Anki add-ons",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://docs/database-schema",
                    name="Database Schema Documentation",
                    description="Anki's SQLite database structure and relationships",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://docs/voice-study-best-practices",
                    name="Voice Study Best Practices",
                    description="Guidelines for effective voice-controlled studying",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://docs/commute-study-guide",
                    name="Commute Study Guide",
                    description="Optimizing Anki for hands-free commute studying",
                    mimeType="text/markdown"
                ),
                Resource(
                    uri="anki://templates/card-formats",
                    name="Card Format Templates",
                    description="Templates for formatting cards for different study modes",
                    mimeType="application/json"
                ),
                Resource(
                    uri="anki://examples/voice-commands",
                    name="Voice Command Examples",
                    description="Examples of natural language commands for Anki interaction",
                    mimeType="application/json"
                )
            ]
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Handle resource requests."""
            try:
                if uri == "anki://docs/architecture":
                    return self._get_architecture_docs()
                elif uri == "anki://docs/scheduling":
                    return self._get_scheduling_docs()
                elif uri == "anki://docs/addon-development":
                    return self._get_addon_development_docs()
                elif uri == "anki://docs/database-schema":
                    return self._get_database_schema_docs()
                elif uri == "anki://docs/voice-study-best-practices":
                    return self._get_voice_study_guide()
                elif uri == "anki://docs/commute-study-guide":
                    return self._get_commute_study_guide()
                elif uri == "anki://templates/card-formats":
                    return self._get_card_format_templates()
                elif uri == "anki://examples/voice-commands":
                    return self._get_voice_command_examples()
                else:
                    raise ValueError(f"Unknown resource: {uri}")
                    
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                return f"Error reading resource: {str(e)}"
    
    # Helper methods for tools
    def _generate_hints(self, card: Dict[str, Any], hint_level: int) -> List[str]:
        """Generate study hints for a card."""
        hints = []
        
        # Get question and answer
        fields = card.get('fields', [])
        if not fields:
            return ["No content available for hints."]
        
        question = fields[0] if len(fields) > 0 else ""
        answer = fields[1] if len(fields) > 1 else ""
        
        if hint_level == 1:  # Subtle hints
            # Give category or type hints
            if card.get('tags'):
                hints.append(f"This relates to: {', '.join(card['tags'][:2])}")
            
            # Give length hint
            if answer:
                word_count = len(answer.split())
                hints.append(f"The answer has {word_count} word{'s' if word_count != 1 else ''}")
            
            # Give first letter
            if answer and answer.strip():
                hints.append(f"It starts with '{answer.strip()[0].upper()}'")
        
        elif hint_level == 2:  # Moderate hints
            # Include subtle hints
            hints.extend(self._generate_hints(card, 1))
            
            # Give partial answer
            if answer and len(answer) > 10:
                partial = answer[:len(answer)//3]
                hints.append(f"It begins with: '{partial}...'")
            
            # Give context clues
            if len(fields) > 2:
                hints.append(f"Additional context: {fields[2][:50]}...")
        
        elif hint_level == 3:  # Obvious hints
            # Include moderate hints
            hints.extend(self._generate_hints(card, 2))
            
            # Give most of the answer
            if answer and len(answer) > 5:
                partial = answer[:len(answer)*2//3]
                hints.append(f"The answer is: '{partial}...'")
        
        return hints if hints else ["No hints available for this card."]
    
    def _analyze_progress(self, history: List[Dict], stats: Dict, days: int) -> str:
        """Analyze learning progress and provide insights."""
        if not history:
            return f"No review data available for the last {days} days."
        
        analysis = f"📈 Learning Progress Analysis (Last {days} days):\n\n"
        
        # Basic statistics
        total_reviews = len(history)
        correct_reviews = sum(1 for r in history if r['ease'] > 1)
        accuracy = correct_reviews / total_reviews * 100
        
        avg_time = sum(r['time_ms'] for r in history) / total_reviews / 1000
        
        analysis += f"📊 **Overview:**\n"
        analysis += f"• Total Reviews: {total_reviews}\n"
        analysis += f"• Overall Accuracy: {accuracy:.1f}%\n"
        analysis += f"• Average Time: {avg_time:.1f}s per card\n\n"
        
        # Performance trends
        if total_reviews >= 7:
            # Split into recent vs older reviews
            midpoint = len(history) // 2
            recent = history[:midpoint]
            older = history[midpoint:]
            
            recent_accuracy = sum(1 for r in recent if r['ease'] > 1) / len(recent) * 100
            older_accuracy = sum(1 for r in older if r['ease'] > 1) / len(older) * 100
            
            trend = "improving" if recent_accuracy > older_accuracy else "declining" if recent_accuracy < older_accuracy else "stable"
            
            analysis += f"📈 **Trend Analysis:**\n"
            analysis += f"• Recent accuracy: {recent_accuracy:.1f}%\n"
            analysis += f"• Earlier accuracy: {older_accuracy:.1f}%\n"
            analysis += f"• Trend: {trend.capitalize()}\n\n"
        
        # Difficulty analysis
        again_count = sum(1 for r in history if r['ease'] == 1)
        hard_count = sum(1 for r in history if r['ease'] == 2)
        good_count = sum(1 for r in history if r['ease'] == 3)
        easy_count = sum(1 for r in history if r['ease'] == 4)
        
        analysis += f"🎯 **Difficulty Breakdown:**\n"
        analysis += f"• Again: {again_count} ({again_count/total_reviews*100:.1f}%)\n"
        analysis += f"• Hard: {hard_count} ({hard_count/total_reviews*100:.1f}%)\n"
        analysis += f"• Good: {good_count} ({good_count/total_reviews*100:.1f}%)\n"
        analysis += f"• Easy: {easy_count} ({easy_count/total_reviews*100:.1f}%)\n\n"
        
        # Recommendations
        analysis += f"💡 **Recommendations:**\n"
        
        if accuracy < 70:
            analysis += "• Consider reviewing cards more frequently\n"
            analysis += "• Take time to understand concepts, not just memorize\n"
        elif accuracy > 90:
            analysis += "• You might be ready for more challenging material\n"
            analysis += "• Consider adjusting card intervals\n"
        
        if avg_time > 10:
            analysis += "• Try to answer more quickly to improve recall\n"
        elif avg_time < 3:
            analysis += "• Take a bit more time to ensure you really know the material\n"
        
        if again_count / total_reviews > 0.3:
            analysis += "• Focus on your most difficult cards\n"
            analysis += "• Consider breaking complex cards into smaller parts\n"
        
        return analysis
    
    def _create_commute_session(self, duration: int, difficulty: str, deck_preference: Optional[str]) -> str:
        """Create an optimized study session for commuting."""
        # Estimate cards per minute (conservative for voice interaction)
        cards_per_minute = 2.5
        target_cards = int(duration * cards_per_minute)
        
        # Get due cards
        due_cards = self.anki.get_due_cards(deck_preference, target_cards * 2)  # Get extra for filtering
        
        if not due_cards:
            return "No cards available for commute session. All cards may be up to date."
        
        # Filter by difficulty if specified
        filtered_cards = []
        
        for card in due_cards:
            card_difficulty = self._assess_card_difficulty(card)
            
            if difficulty == "easy" and card_difficulty == "easy":
                filtered_cards.append(card)
            elif difficulty == "medium" and card_difficulty == "medium":
                filtered_cards.append(card)
            elif difficulty == "hard" and card_difficulty == "hard":
                filtered_cards.append(card)
            elif difficulty == "mixed":
                filtered_cards.append(card)
        
        # Limit to target number
        session_cards = filtered_cards[:target_cards]
        
        result = f"🚗 Commute Study Session ({duration} minutes):\n\n"
        result += f"📊 **Session Plan:**\n"
        result += f"• Duration: {duration} minutes\n"
        result += f"• Target cards: {len(session_cards)}\n"
        result += f"• Difficulty: {difficulty}\n"
        if deck_preference:
            result += f"• Deck focus: {deck_preference}\n"
        result += "\n"
        
        # Safety reminders
        result += f"⚠️ **Safety Reminders:**\n"
        result += f"• Keep your eyes on the road\n"
        result += f"• Use voice commands only\n"
        result += f"• Pull over if you need to interact manually\n"
        result += f"• Pause session in heavy traffic\n\n"
        
        # Card preview
        result += f"📚 **Cards in this session:**\n"
        for i, card in enumerate(session_cards[:10], 1):
            question_preview = card['fields'][0][:60] if card['fields'] else "No content"
            result += f"{i}. {question_preview}... ({card['deck_name']})\n"
        
        if len(session_cards) > 10:
            result += f"... and {len(session_cards) - 10} more cards.\n"
        
        result += f"\n🎯 **Voice Commands to use:**\n"
        result += f"• 'Next card' - Get the next question\n"
        result += f"• 'Show answer' - Reveal the answer\n"
        result += f"• 'I got it' / 'Too easy' - Mark as easy\n"
        result += f"• 'Good' / 'Correct' - Mark as good\n"
        result += f"• 'Hard' / 'Difficult' - Mark as hard\n"
        result += f"• 'Again' / 'I forgot' - Mark for repeat\n"
        result += f"• 'Pause session' - Take a break\n"
        
        return result
    
    def _assess_card_difficulty(self, card: Dict[str, Any]) -> str:
        """Assess the difficulty of a card based on its statistics."""
        ease_factor = card.get('ease_factor', 2500)
        lapses = card.get('lapses', 0)
        interval = card.get('interval', 0)
        
        # Calculate difficulty score
        if ease_factor < 2000 or lapses > 2:
            return "hard"
        elif ease_factor > 2800 and interval > 30 and lapses == 0:
            return "easy"
        else:
            return "medium"
    
    def _format_for_speech(self, card: Dict[str, Any], include_hints: bool) -> str:
        """Format card content for optimal speech synthesis."""
        fields = card.get('fields', [])
        if not fields:
            return "No content available for this card."
        
        # Clean HTML and format for speech
        question = self._clean_html_for_speech(fields[0])
        answer = self._clean_html_for_speech(fields[1]) if len(fields) > 1 else ""
        
        result = f"🎤 **Speech-Optimized Card {card['id']}:**\n\n"
        
        # Question formatting
        result += f"**Question:**\n{question}\n\n"
        
        # Answer formatting
        if answer:
            result += f"**Answer:**\n{answer}\n\n"
        
        # Pronunciation hints if requested
        if include_hints:
            hints = self._generate_pronunciation_hints(question, answer)
            if hints:
                result += f"**Pronunciation Hints:**\n"
                for hint in hints:
                    result += f"• {hint}\n"
                result += "\n"
        
        # Speech timing suggestions
        question_words = len(question.split())
        result += f"**Speech Timing:**\n"
        result += f"• Question read time: ~{question_words * 0.6:.1f} seconds\n"
        if answer:
            answer_words = len(answer.split())
            result += f"• Answer read time: ~{answer_words * 0.6:.1f} seconds\n"
        
        return result
    
    def _clean_html_for_speech(self, text: str) -> str:
        """Clean HTML content for better speech synthesis."""
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Handle common symbols and abbreviations
        replacements = {
            '&': 'and',
            '@': 'at',
            '#': 'number',
            '%': 'percent',
            '$': 'dollars',
            '€': 'euros',
            '£': 'pounds',
            '×': 'times',
            '÷': 'divided by',
            '≤': 'less than or equal to',
            '≥': 'greater than or equal to',
            '≠': 'not equal to',
            '→': 'leads to',
            '←': 'comes from',
            '↑': 'up',
            '↓': 'down'
        }
        
        for symbol, replacement in replacements.items():
            text = text.replace(symbol, f' {replacement} ')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _generate_pronunciation_hints(self, question: str, answer: str) -> List[str]:
        """Generate pronunciation hints for difficult words."""
        hints = []
        
        # Simple heuristics for pronunciation hints
        # This could be expanded with a pronunciation dictionary
        
        difficult_patterns = [
            (r'\b\w*ough\w*\b', 'Words with "ough" can be tricky'),
            (r'\b\w*ph\w*\b', 'Remember "ph" sounds like "f"'),
            (r'\b\w*ch\w*\b', '"ch" can sound like "k" in some words'),
            (r'\b[A-Z][a-z]*[A-Z]\w*\b', 'Mixed case words may be abbreviations'),
        ]
        
        text = f"{question} {answer}"
        
        for pattern, hint in difficult_patterns:
            if re.search(pattern, text):
                hints.append(hint)
        
        # Check for numbers that should be read specially
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            hints.append("Numbers should be read digit by digit or as years/quantities as appropriate")
        
        return hints[:3]  # Limit to 3 hints
    
    # Resource content methods
    def _get_architecture_docs(self) -> str:
        """Get Anki architecture documentation."""
        return """# Anki Architecture Overview

## Core Components

### 1. Collection (`anki.collection.Collection`)
- Central object managing all data operations
- SQLite database interface
- Scheduling algorithm implementation
- Media file management

### 2. Scheduler (`anki.scheduler.Scheduler`)
- Implements spaced repetition algorithm (modified SM2)
- Manages card states: New → Learning → Review → Relearning
- Calculates intervals and due dates
- Handles daily limits and deck configurations

### 3. Cards and Notes
- **Notes**: Content containers with fields
- **Cards**: Generated from note templates
- One note can generate multiple cards
- Cards contain scheduling information

### 4. Decks
- Hierarchical organization of cards
- Individual configuration options
- Can be filtered dynamically

### 5. Note Types (Models)
- Templates defining card layout
- Field definitions
- CSS styling
- JavaScript for dynamic behavior

## Database Schema

```sql
-- Core tables
notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
notetypes (id, name, usn, mod, flds, tmpls, tags, did, css, data)
decks (id, name, conf, usn, mod, desc, dyn, collapsed, data)
```

## Add-on Integration Points

### Hooks
- Event-driven architecture
- GUI hooks for UI modifications
- Collection hooks for data operations
- WebView hooks for content injection

### API Access
- Collection operations via `mw.col`
- Scheduler access via `mw.col.sched`
- UI modification via PyQt
- Web content via JavaScript injection

## Threading Model
- Main thread for UI operations
- Background threads for heavy operations
- TaskManager for async operations
- Thread-safe collection access
"""
    
    def _get_scheduling_docs(self) -> str:
        """Get scheduling algorithm documentation."""
        return """# Anki Scheduling Algorithm

## Overview
Anki uses a modified version of the SuperMemo 2 (SM2) algorithm with additional optimizations for real-world usage.

## Card States

### 1. New Cards
- Initial state for newly created cards
- Shown according to new cards/day limit
- Move to Learning state after first review

### 2. Learning Cards
- Cards being initially learned
- Multiple steps with increasing intervals
- Default steps: 1m, 10m
- Graduate to Review after successful completion

### 3. Review Cards
- Cards with intervals ≥ 1 day
- Use ease factor for interval calculation
- Can lapse back to Learning/Relearning

### 4. Relearning Cards
- Previously learned cards that were forgotten
- Similar to Learning but with different steps
- Lower graduation requirements

## Interval Calculation

### Basic Formula
```
new_interval = previous_interval × ease_factor × interval_modifier
```

### Ease Factor
- Starts at 250% (2.5x multiplier)
- Adjusted based on answer quality:
  - Again: -20%
  - Hard: -15%
  - Good: no change
  - Easy: +15%
- Minimum: 130%

### Answer Buttons
1. **Again**: Reset to Learning
2. **Hard**: Reduce ease, multiply interval by 1.2
3. **Good**: Standard interval calculation
4. **Easy**: Increase ease, multiply by Easy bonus

## Optimizations

### Fuzz Factor
- Prevents cards from always appearing together
- Adds ±5% randomness to intervals
- Spreads review load over multiple days

### Daily Limits
- New cards per day
- Maximum reviews per day
- Separate limits per deck

### Deck Options
- Learning steps customization
- Graduating interval
- Easy interval
- Maximum interval (default: 36500 days)

## Advanced Features

### Filtered Decks
- Dynamic queries for card selection
- Custom scheduling rules
- Cramming mode with special handling

### Buried Cards
- Temporarily hidden related cards
- Prevents interference between similar cards
- Automatically unburied next day

### Suspended Cards
- Manually disabled cards
- Don't appear in any queue
- Can be unsuspended manually

## Best Practices

### Card Creation
- One concept per card
- Clear, unambiguous questions
- Appropriate difficulty level

### Review Strategy
- Consistent daily reviews
- Honest self-assessment
- Don't change settings too frequently

### Difficulty Management
- Use "Hard" for challenging but known cards
- Use "Again" only for truly forgotten cards
- Use "Easy" sparingly for trivial cards
"""
    
    def _get_addon_development_docs(self) -> str:
        """Get add-on development documentation."""
        return """# Anki Add-on Development Guide

## Getting Started

### Environment Setup
1. Install Anki from source or use development version
2. Set up Python environment matching Anki's version
3. Configure IDE with Anki's Python path
4. Enable debug console in Anki

### Basic Add-on Structure
```
addon_folder/
├── __init__.py          # Entry point
├── manifest.json        # Metadata
├── config.json          # Default config
├── meta.json           # Internal metadata
└── resources/          # Additional files
```

### Manifest.json
```json
{
    "name": "My Add-on",
    "package": "my_addon",
    "author": "Your Name",
    "version": "1.0",
    "homepage": "https://github.com/user/addon",
    "conflicts": [],
    "mod": 0
}
```

## Core Concepts

### Hook System
```python
from aqt import gui_hooks

# Register hook
def on_main_window_init():
    print("Main window initialized")

gui_hooks.main_window_did_init.append(on_main_window_init)
```

### Collection Access
```python
from aqt import mw

# Get cards
card_ids = mw.col.find_cards("deck:current")
cards = [mw.col.get_card(cid) for cid in card_ids]

# Modify notes
note = card.note()
note["Field"] = "new value"
mw.col.update_note(note)
```

### UI Modifications
```python
from aqt.qt import QAction

def add_menu_item():
    action = QAction("My Action", mw)
    action.triggered.connect(my_function)
    mw.form.menuTools.addAction(action)

gui_hooks.main_window_did_init.append(add_menu_item)
```

### Web Content Injection
```python
def on_webview_will_set_content(web_content, context):
    if isinstance(context, Reviewer):
        web_content.js += "console.log('Hello from add-on');"
        web_content.css += ".card { border: 1px solid red; }"

gui_hooks.webview_will_set_content.append(on_webview_will_set_content)
```

## Advanced Features

### Background Operations
```python
from aqt.taskman import run_on_main

def background_task():
    # Heavy computation
    result = process_data()
    
    # Update UI on main thread
    def update_ui():
        show_result(result)
    
    run_on_main(update_ui)

# Run in background
mw.taskman.run_in_background(background_task)
```

### Configuration
```python
# Get config
config = mw.addonManager.getConfig(__name__)
setting = config.get('my_setting', 'default_value')

# Save config
config['my_setting'] = 'new_value'
mw.addonManager.writeConfig(__name__, config)
```

### Error Handling
```python
import logging

logger = logging.getLogger(__name__)

try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    showWarning(f"Error: {e}")
```

## Best Practices

### Code Organization
- Separate UI from business logic
- Use type hints for better IDE support
- Follow Python naming conventions
- Document public functions

### Performance
- Use background threads for heavy operations
- Cache frequently accessed data
- Minimize database queries
- Profile performance-critical code

### Compatibility
- Check Anki version compatibility
- Use feature detection, not version checks
- Handle missing hooks gracefully
- Test on multiple Anki versions

### Security
- Validate user inputs
- Use secure communication for external services
- Don't store sensitive data in config files
- Follow principle of least privilege

## Testing

### Manual Testing
- Test with different note types
- Test with large collections
- Test edge cases and error conditions
- Test on different platforms

### Automated Testing
```python
import unittest
from unittest.mock import Mock, patch

class TestMyAddon(unittest.TestCase):
    def setUp(self):
        self.mock_col = Mock()
        
    def test_feature(self):
        result = my_function(self.mock_col)
        self.assertEqual(result, expected_value)
```

## Distribution

### Packaging
```bash
# Create .ankiaddon file
zip -r my_addon.ankiaddon . -x "*.git*" "*__pycache__*"
```

### Publishing
1. Test thoroughly on multiple systems
2. Create clear documentation
3. Submit to AnkiWeb
4. Provide support channel
5. Maintain compatibility with updates
"""
    
    def _get_database_schema_docs(self) -> str:
        """Get database schema documentation."""
        return """# Anki Database Schema

## Overview
Anki uses SQLite database with normalized schema for efficient storage and querying.

## Core Tables

### notes
Stores note content and metadata.
```sql
CREATE TABLE notes (
    id INTEGER PRIMARY KEY,     -- Unique note ID
    guid TEXT NOT NULL,         -- Global unique identifier
    mid INTEGER NOT NULL,       -- Note type (model) ID
    mod INTEGER NOT NULL,       -- Last modified timestamp
    usn INTEGER NOT NULL,       -- Update sequence number (sync)
    tags TEXT NOT NULL,         -- Space-separated tags
    flds TEXT NOT NULL,         -- Field content (separated by \x1f)
    sfld TEXT NOT NULL,         -- Sort field for searching
    csum INTEGER NOT NULL,      -- Checksum for duplicate detection
    flags INTEGER NOT NULL,     -- Bit flags for note state
    data TEXT NOT NULL          -- Additional JSON data
);
```

### cards
Stores individual cards and scheduling information.
```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,     -- Unique card ID
    nid INTEGER NOT NULL,       -- Note ID (foreign key)
    did INTEGER NOT NULL,       -- Deck ID
    ord INTEGER NOT NULL,       -- Card template ordinal
    mod INTEGER NOT NULL,       -- Last modified timestamp
    usn INTEGER NOT NULL,       -- Update sequence number
    type INTEGER NOT NULL,      -- Card type (0=new, 1=learn, 2=review, 3=relearn)
    queue INTEGER NOT NULL,     -- Queue type (-3=user buried, -2=sched buried, -1=suspended, 0=new, 1=learn, 2=review, 3=day learn, 4=preview)
    due INTEGER NOT NULL,       -- Due date/position
    ivl INTEGER NOT NULL,       -- Current interval in days
    factor INTEGER NOT NULL,    -- Ease factor (2500 = 250%)
    reps INTEGER NOT NULL,      -- Number of reviews
    lapses INTEGER NOT NULL,    -- Number of lapses (forgotten)
    left INTEGER NOT NULL,      -- Learning steps remaining
    odue INTEGER NOT NULL,      -- Original due date (for filtered decks)
    odid INTEGER NOT NULL,      -- Original deck ID (for filtered decks)
    flags INTEGER NOT NULL,     -- Bit flags
    data TEXT NOT NULL          -- Additional JSON data
);
```

### revlog
Review history log.
```sql
CREATE TABLE revlog (
    id INTEGER PRIMARY KEY,     -- Review timestamp in milliseconds
    cid INTEGER NOT NULL,       -- Card ID
    usn INTEGER NOT NULL,       -- Update sequence number
    ease INTEGER NOT NULL,      -- Button pressed (1=again, 2=hard, 3=good, 4=easy)
    ivl INTEGER NOT NULL,       -- New interval
    lastIvl INTEGER NOT NULL,   -- Previous interval
    factor INTEGER NOT NULL,    -- New ease factor
    time INTEGER NOT NULL,      -- Time taken in milliseconds
    type INTEGER NOT NULL       -- Review type (0=learn, 1=review, 2=relearn, 3=early)
);
```

### notetypes
Note type definitions.
```sql
CREATE TABLE notetypes (
    id INTEGER PRIMARY KEY,     -- Note type ID
    name TEXT NOT NULL,         -- Note type name
    usn INTEGER NOT NULL,       -- Update sequence number
    mod INTEGER NOT NULL,       -- Last modified timestamp
    flds TEXT NOT NULL,         -- Field definitions (JSON)
    tmpls TEXT NOT NULL,        -- Card templates (JSON)
    tags TEXT NOT NULL,         -- Default tags
    did INTEGER NOT NULL,       -- Default deck ID
    usn INTEGER NOT NULL,       -- Update sequence number
    mod INTEGER NOT NULL,       -- Last modified timestamp
    css TEXT NOT NULL,          -- CSS styling
    data TEXT NOT NULL          -- Additional JSON data
);
```

### decks
Deck configurations and hierarchy.
```sql
CREATE TABLE decks (
    id INTEGER PRIMARY KEY,     -- Deck ID
    name TEXT NOT NULL,         -- Deck name (can include ::Parent::Child)
    conf TEXT NOT NULL,         -- Configuration JSON
    usn INTEGER NOT NULL,       -- Update sequence number
    mod INTEGER NOT NULL,       -- Last modified timestamp
    desc TEXT NOT NULL,         -- Description
    dyn INTEGER NOT NULL,       -- Is filtered deck (0=no, 1=yes)
    collapsed INTEGER NOT NULL, -- Collapsed in browser
    data TEXT NOT NULL          -- Additional JSON data
);
```

## Key Relationships

- `cards.nid` → `notes.id` (many-to-one)
- `cards.did` → `decks.id` (many-to-one)
- `notes.mid` → `notetypes.id` (many-to-one)
- `revlog.cid` → `cards.id` (many-to-one)

## Card Queue Types

- `-3`: User buried
- `-2`: Scheduler buried  
- `-1`: Suspended
- `0`: New
- `1`: Learning
- `2`: Review
- `3`: Day learning
- `4`: Preview

## Review Types

- `0`: Learning
- `1`: Review
- `2`: Relearning
- `3`: Early review (cramming)

## Ease Values

- `1`: Again
- `2`: Hard
- `3`: Good
- `4`: Easy

## Important Notes

- All timestamps are Unix epochs in seconds or milliseconds
- Field separator in notes.flds is `\x1f` (ASCII 31)
- Ease factors are stored as integers (2500 = 250%)
- Intervals are in days for review cards
"""
    
    def _get_voice_study_guide(self) -> str:
        """Get voice study best practices guide."""
        return """# Voice Study Best Practices

## Overview
Voice-controlled studying offers hands-free learning but requires different strategies than traditional visual study methods.

## Optimal Card Design for Voice

### Text Content
- **Keep it concise**: Aim for questions under 20 words
- **Avoid complex formatting**: No tables, complex layouts
- **Use clear language**: Avoid ambiguous wording
- **Include context**: Add enough information for audio-only comprehension
- **Phonetic spelling**: For foreign words, include pronunciation guides

### Visual Elements
- **Describe images**: Add alt-text descriptions for visual content
- **Convert symbols**: Replace mathematical symbols with words
- **Audio cues**: Use sound files when appropriate
- **Minimal HTML**: Avoid complex markup that doesn't translate to speech

## Study Session Setup

### Environment
- **Quiet space**: Minimize background noise
- **Good microphone**: Ensure clear voice recognition
- **Stable connection**: Reliable internet for AI processing
- **Comfortable posture**: Maintain focus without strain

### Session Planning
- **Shorter sessions**: 15-20 minutes optimal for voice study
- **Break frequency**: Take breaks every 10-15 cards
- **Progressive difficulty**: Start easy, increase complexity
- **Review goals**: Set clear targets for each session

## Voice Commands Best Practices

### Natural Language
- Use conversational phrases instead of rigid commands
- Example: "I don't remember this" instead of just "again"
- Express uncertainty: "I'm not sure" or "That's difficult"
- Be specific: "This is too easy" rather than just "easy"

### Timing and Rhythm
- **Pause before answering**: Take time to think
- **Speak clearly**: Enunciate for better recognition
- **Consistent pace**: Don't rush through cards
- **Confirm understanding**: Ask for repetition if unclear

## Memory Enhancement Techniques

### Audio Mnemonics
- Create sound associations for difficult concepts
- Use rhymes and alliteration for better recall
- Practice pronunciation repeatedly
- Associate with familiar sounds or music

### Verbal Elaboration
- Explain answers in your own words
- Create verbal connections between concepts
- Use analogies and examples
- Engage in self-dialogue about the material

## Troubleshooting Common Issues

### Recognition Problems
- Speak more clearly and slowly
- Use alternative phrasings for commands
- Check microphone settings and positioning
- Ensure stable internet connection

### Attention and Focus
- Use shorter study sessions
- Take regular breaks
- Vary question types and difficulties
- Set specific goals for each session

### Content Comprehension
- Request hints when struggling
- Ask for explanations of difficult concepts
- Break complex cards into smaller parts
- Review related cards together

## Advanced Techniques

### Spaced Repetition Optimization
- Trust the algorithm but provide honest feedback
- Use "hard" rating for challenging but known content
- Reserve "again" for truly forgotten material
- Don't overuse "easy" ratings

### Multi-Modal Learning
- Combine voice study with visual review
- Use different senses when possible
- Create mental images while listening
- Practice active recall techniques

## Safety Considerations

### Commute Study
- **Never compromise safety**: Stop if driving becomes difficult
- **Hands-free only**: Use voice commands exclusively
- **Pause in traffic**: Don't study during complex driving
- **Emergency stops**: Be ready to pause instantly

### Health and Ergonomics
- **Voice care**: Stay hydrated, don't strain
- **Posture**: Maintain good position
- **Eye rest**: Look away from screens periodically
- **Mental fatigue**: Recognize when to stop

## Performance Optimization

### Session Analytics
- Track accuracy trends over time
- Monitor response times
- Identify problematic card types
- Adjust difficulty based on performance

### Content Curation
- Remove or modify cards that don't work well with voice
- Create voice-optimized versions of visual cards
- Use tags to organize voice-friendly content
- Regular review and refinement of card collection

## Integration with Daily Routine

### Scheduling
- **Consistent timing**: Same time each day when possible
- **Micro-sessions**: Use small time blocks effectively
- **Commute optimization**: Make travel time productive
- **Pre-sleep review**: Light review before bed

### Habit Formation
- Start with short, easy sessions
- Gradually increase duration and difficulty
- Use rewards and milestones
- Track progress visibly

## Technology Tips

### Audio Quality
- Use noise-canceling headphones when possible
- Adjust playback speed for comprehension
- Test different voices and accents
- Optimize volume levels for your environment

### Device Management
- Keep devices charged and ready
- Have backup options available
- Use offline modes when possible
- Regular software updates for optimal performance
"""
    
    def _get_commute_study_guide(self) -> str:
        """Get commute study guide."""
        return """# Commute Study Guide

## Safety First Principles

### Driving Safety
⚠️ **CRITICAL**: Never compromise driving safety for studying
- **Full attention to road**: Driving is your primary task
- **Voice only**: Never look at or touch device while driving
- **Pause immediately**: Stop studying if road conditions worsen
- **Pull over**: If you need to interact manually, find safe parking

### Preparation
- Set up audio before starting your commute
- Test voice commands in a safe environment first
- Have emergency stop phrases ready ("pause study", "stop session")
- Plan for interruptions (calls, navigation announcements)

## Optimal Commute Study Setup

### Vehicle Preparation
- **Hands-free mount**: Secure device safely
- **Audio system**: Connect via Bluetooth or aux cable
- **Microphone**: Ensure clear voice pickup
- **Volume levels**: Audible but not overwhelming

### Route Considerations
- **Familiar routes**: Best for study sessions
- **Traffic patterns**: Avoid studying in heavy traffic
- **Drive duration**: 15+ minutes optimal
- **Predictable stops**: Plan around regular traffic lights

### Content Selection
- **Review cards**: Focus on reinforcement, not new learning
- **Easy to medium difficulty**: Avoid complex new material
- **Short format**: Quick question-answer pairs
- **Familiar topics**: Subjects you know reasonably well

## Study Session Structure

### Pre-Drive Setup (5 minutes)
1. **Connect device** to car audio system
2. **Test voice commands** with engine off
3. **Select appropriate deck** and difficulty level
4. **Set session duration** based on commute time
5. **Review safety commands** (pause, stop, help)

### During Drive Session
1. **Start easy**: Begin with familiar cards
2. **Natural responses**: Use conversational language
3. **Don't rush**: Take time to think before answering
4. **Stay flexible**: Pause for complex driving situations
5. **Monitor fatigue**: Stop if concentration wavers

### Post-Drive Review (2 minutes)
1. **Session summary**: Quick review of performance
2. **Mark difficult cards**: Flag cards for later detailed study
3. **Plan follow-up**: Note topics needing visual reinforcement
4. **Log progress**: Track commute study effectiveness

## Voice Command Optimization

### Natural Language Commands
Instead of rigid commands, use natural speech:
- ✅ "I don't remember this one" → Again
- ✅ "That was pretty tough" → Hard  
- ✅ "Got it right" → Good
- ✅ "Way too easy" → Easy
- ✅ "Skip this for now" → Bury card
- ✅ "Pause the session" → Pause

### Emergency Commands
Memorize these critical commands:
- **"Emergency stop"**: Immediately pause everything
- **"Driving focus"**: Pause and stay paused
- **"End session"**: Stop studying completely
- **"Repeat question"**: Replay current card

## Content Adaptation

### Card Types That Work Well
- **Simple Q&A**: Direct question-answer pairs
- **Vocabulary**: Word definitions, translations
- **Facts and figures**: Historical dates, statistics
- **Formulas**: Mathematical or scientific formulas (spoken)
- **Pronunciation**: Language learning with audio

### Card Types to Avoid
- **Complex diagrams**: Visual elements that can't be described
- **Long passages**: Extended reading comprehension
- **Mathematical notation**: Complex equations with symbols
- **Detailed images**: Maps, charts, technical drawings
- **Multi-step problems**: Complex reasoning tasks

### Conversion Strategies
Transform visual cards for audio use:
- **Add descriptions**: Describe images in text fields
- **Simplify language**: Use clear, unambiguous wording
- **Break down complexity**: Split complex cards into smaller parts
- **Add pronunciation**: Include phonetic spellings
- **Use analogies**: Replace visual concepts with verbal ones

## Time Management

### Session Duration Planning
- **Short commute (5-15 min)**: Quick review of 10-20 cards
- **Medium commute (15-30 min)**: Focused session of 25-40 cards
- **Long commute (30+ min)**: Extended session with breaks

### Efficiency Optimization
- **Pre-filtered decks**: Set up commute-specific card collections
- **Difficulty targeting**: Focus on cards due for review
- **Progress tracking**: Monitor cards completed per minute
- **Adaptive timing**: Adjust based on traffic and road conditions

## Performance Monitoring

### Success Metrics
- **Safety**: Zero driving incidents or near-misses
- **Retention**: Improved recall rates over time
- **Efficiency**: Cards reviewed per commute minute
- **Consistency**: Regular daily study completion
- **Engagement**: Sustained attention throughout session

### Troubleshooting Common Issues

#### Recognition Problems
- **Background noise**: Use noise-canceling microphone
- **Engine noise**: Adjust volume and speak clearly
- **Poor connection**: Ensure stable internet/cellular signal
- **Accent issues**: Practice with system, use alternative phrases

#### Attention Issues
- **Traffic distraction**: Pause immediately, resume when safe
- **Mental fatigue**: Reduce session length or difficulty
- **Information overload**: Take breaks, reduce card density
- **Multitasking stress**: Focus on driving first, study second

#### Technical Problems
- **Audio dropouts**: Check connections, have backup audio
- **App crashes**: Keep session data synced, restart quickly
- **Battery drain**: Use car charger, manage power settings
- **Data usage**: Download content for offline use when possible

## Best Practices by Transport Mode

### Car (Driver)
- **Strictest safety rules**: Full hands-free operation
- **Short sessions**: 15-20 minutes maximum
- **Familiar routes only**: Avoid studying on new roads
- **Weather considerations**: Skip during poor conditions

### Car (Passenger)
- **More flexibility**: Can use visual elements if needed
- **Longer sessions**: Up to full commute duration
- **Complex content**: Can handle more challenging material
- **Note-taking**: Can jot down difficult concepts

### Public Transport
- **Visual + audio**: Combine modes for better learning
- **Full sessions**: Use entire travel time
- **Any content type**: No restrictions on complexity
- **Social awareness**: Use headphones, mind volume

### Walking/Cycling
- **Safety awareness**: Stay alert to surroundings
- **Light sessions**: Easy review content only
- **Weather proof**: Ensure device protection
- **Route familiarity**: Stick to known, safe paths

## Advanced Strategies

### Contextual Learning
- **Route associations**: Link difficult concepts to specific locations
- **Time-based cues**: Associate content with parts of commute
- **Environmental triggers**: Use surroundings as memory aids
- **Routine integration**: Make study part of travel ritual

### Progressive Difficulty
- **Start easy**: Begin commute with confidence builders
- **Build momentum**: Gradually increase challenge level
- **Peak performance**: Tackle hardest content mid-commute
- **Cool down**: End with easier review material

### Multi-Modal Integration
- **Audio reinforcement**: Use voice notes for difficult concepts
- **Visual follow-up**: Review challenging cards later with screen
- **Kinesthetic elements**: Use gesture associations when safe
- **Social sharing**: Discuss learned concepts with others

## Technology Setup

### Essential Apps and Tools
- **Anki with voice add-on**: Primary study platform
- **Voice recording app**: Capture questions or insights
- **Offline maps**: Reduce data usage and distractions
- **Do not disturb**: Block non-emergency notifications

### Hardware Optimization
- **Quality headphones**: Clear audio input/output
- **Car mount**: Secure, accessible device placement
- **Charging cables**: Keep devices powered
- **Backup power**: Portable battery for longer commutes

### Connectivity Management
- **Download content**: Prepare offline content in advance
- **Data monitoring**: Track usage to avoid overages
- **Connection backup**: Have mobile hotspot option
- **Sync timing**: Update progress when connected

## Habit Development

### Starting Out
- **Week 1-2**: Focus on setup and safety
- **Week 3-4**: Establish consistent routine
- **Month 2**: Optimize content and timing
- **Month 3+**: Advanced techniques and expansion

### Motivation Maintenance
- **Track progress**: Visible improvement metrics
- **Celebrate milestones**: Acknowledge achievements
- **Vary content**: Keep sessions interesting
- **Social accountability**: Share goals with others

### Long-term Success
- **Gradual expansion**: Slowly increase session length
- **Content rotation**: Regularly update card collections
- **Performance analysis**: Regular review of effectiveness
- **Adaptation**: Adjust based on life changes and feedback
"""
    
    def _get_card_format_templates(self) -> str:
        """Get card format templates as JSON."""
        templates = {
            "voice_optimized_basic": {
                "name": "Voice-Optimized Basic",
                "description": "Simple Q&A format optimized for voice interaction",
                "front_template": "{{Question}}",
                "back_template": "{{Answer}}<br><br><i>{{#Pronunciation}}Pronunciation: {{Pronunciation}}{{/Pronunciation}}</i>",
                "fields": ["Question", "Answer", "Pronunciation", "Notes"],
                "css": """
.card {
    font-family: Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
    line-height: 1.4;
}

.pronunciation {
    font-style: italic;
    color: #666;
    font-size: 16px;
}
""",
                "voice_settings": {
                    "read_question": True,
                    "read_answer": True,
                    "include_pronunciation": True,
                    "pause_after_question": 2.0,
                    "speech_rate": 0.9
                }
            },
            "commute_friendly": {
                "name": "Commute-Friendly",
                "description": "Optimized for hands-free studying during commute",
                "front_template": "<div class='question'>{{Question}}</div>{{#Context}}<div class='context'>Context: {{Context}}</div>{{/Context}}",
                "back_template": "<div class='answer'>{{Answer}}</div>{{#Explanation}}<div class='explanation'>{{Explanation}}</div>{{/Explanation}}",
                "fields": ["Question", "Answer", "Context", "Explanation", "Difficulty"],
                "css": """
.card {
    font-family: Arial, sans-serif;
    font-size: 18px;
    text-align: left;
    color: #333;
    background-color: #f9f9f9;
    padding: 20px;
    line-height: 1.5;
}

.question {
    font-size: 22px;
    font-weight: bold;
    margin-bottom: 15px;
}

.context {
    font-size: 16px;
    color: #666;
    font-style: italic;
    margin-bottom: 10px;
}

.answer {
    font-size: 20px;
    color: #2c3e50;
    margin-bottom: 15px;
}

.explanation {
    font-size: 16px;
    color: #666;
    border-left: 3px solid #3498db;
    padding-left: 15px;
}
""",
                "voice_settings": {
                    "read_context": True,
                    "read_explanation": True,
                    "max_question_length": 150,
                    "pause_after_context": 1.0,
                    "speech_rate": 0.8
                }
            },
            "language_learning": {
                "name": "Language Learning (Voice)",
                "description": "Optimized for language learning with pronunciation focus",
                "front_template": "<div class='word'>{{Word}}</div>{{#PartOfSpeech}}<div class='pos'>({{PartOfSpeech}})</div>{{/PartOfSpeech}}",
                "back_template": "<div class='definition'>{{Definition}}</div>{{#Example}}<div class='example'>Example: {{Example}}</div>{{/Example}}{{#Pronunciation}}<div class='pronunciation'>[{{Pronunciation}}]</div>{{/Pronunciation}}",
                "fields": ["Word", "Definition", "PartOfSpeech", "Example", "Pronunciation", "Audio"],
                "css": """
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 18px;
    text-align: center;
    color: #2c3e50;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 25px;
    border-radius: 10px;
}

.word {
    font-size: 28px;
    font-weight: bold;
    color: #e74c3c;
    margin-bottom: 10px;
}

.pos {
    font-size: 14px;
    color: #7f8c8d;
    font-style: italic;
    margin-bottom: 20px;
}

.definition {
    font-size: 20px;
    margin-bottom: 15px;
    line-height: 1.4;
}

.example {
    font-size: 16px;
    color: #27ae60;
    font-style: italic;
    margin: 15px 0;
    padding: 10px;
    background: rgba(255,255,255,0.3);
    border-radius: 5px;
}

.pronunciation {
    font-size: 16px;
    color: #3498db;
    font-family: 'Courier New', monospace;
    margin-top: 10px;
}
""",
                "voice_settings": {
                    "read_word_twice": True,
                    "read_pronunciation": True,
                    "read_example": True,
                    "use_target_language_tts": True,
                    "speech_rate": 0.7
                }
            }
        }
        return json.dumps(templates, indent=2)
    
    def _get_voice_command_examples(self) -> str:
        """Get voice command examples as JSON."""
        examples = {
            "basic_commands": {
                "session_control": [
                    "Start a new study session",
                    "Let's begin reviewing",
                    "I'm ready to study",
                    "Pause the session",
                    "Take a break",
                    "Resume studying",
                    "End the session",
                    "Stop studying"
                ],
                "card_navigation": [
                    "Next card please",
                    "Give me another one",
                    "Continue",
                    "Show me the answer",
                    "I give up",
                    "What's the answer?",
                    "Reveal the solution"
                ],
                "ratings": [
                    "I forgot this completely",
                    "Again please",
                    "That was really difficult",
                    "Pretty hard",
                    "I got it right",
                    "That was good",
                    "Way too easy",
                    "Super simple"
                ]
            },
            "natural_responses": {
                "difficulty_expressions": [
                    "I don't remember",
                    "No idea",
                    "I'm blanking on this",
                    "Can't recall",
                    "This is tough",
                    "Struggling with this",
                    "Kind of remember",
                    "I think I know",
                    "Got it",
                    "I know this",
                    "Piece of cake",
                    "Too obvious"
                ],
                "confidence_levels": [
                    "I'm not sure about this",
                    "Maybe?",
                    "I think so",
                    "Pretty confident",
                    "Definitely know this",
                    "Absolutely certain"
                ],
                "help_requests": [
                    "Can you give me a hint?",
                    "I need some help",
                    "What's a clue?",
                    "Point me in the right direction",
                    "Give me a nudge"
                ]
            },
            "advanced_commands": {
                "study_preferences": [
                    "Focus on difficult cards",
                    "Show me easy ones first",
                    "Mix up the difficulty",
                    "Only cards from Spanish deck",
                    "Skip this card for now",
                    "Mark this for later review"
                ],
                "session_customization": [
                    "I have 15 minutes to study",
                    "Quick review session",
                    "In-depth study mode",
                    "Commute-friendly session",
                    "Focus mode please"
                ],
                "feedback_and_analysis": [
                    "How am I doing today?",
                    "Show my statistics",
                    "What's my accuracy rate?",
                    "Which cards am I struggling with?",
                    "Any patterns in my mistakes?"
                ]
            },
            "contextual_responses": {
                "by_subject": {
                    "languages": [
                        "I know the meaning but can't pronounce it",
                        "The grammar is confusing",
                        "I remember the word but not the gender",
                        "Close but not quite right"
                    ],
                    "mathematics": [
                        "I know the concept but made a calculation error",
                        "The formula is familiar",
                        "I understand the process",
                        "Need to practice this more"
                    ],
                    "history": [
                        "I know the century but not the exact year",
                        "Familiar with the event",
                        "Close time period",
                        "I know the person but not the context"
                    ]
                },
                "by_card_type": {
                    "definition": [
                        "I know what it means in general",
                        "Close definition",
                        "Right concept, wrong words",
                        "Partial understanding"
                    ],
                    "translation": [
                        "I know it in the other direction",
                        "Familiar word but can't translate",
                        "Similar meaning",
                        "Close but not exact"
                    ]
                }
            },
            "error_recovery": {
                "misunderstanding": [
                    "That's not what I meant",
                    "Let me try again",
                    "I said something different",
                    "Can you repeat the question?"
                ],
                "technical_issues": [
                    "I didn't hear that clearly",
                    "Can you speak louder?",
                    "The connection seems poor",
                    "Please repeat"
                ]
            }
        }
        return json.dumps(examples, indent=2)

    async def run(self):
        """Run the MCP server."""
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

def main():
    """Main entry point."""
    try:
        server = AnkiMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Cleanup
        if hasattr(server, 'anki'):
            server.anki.disconnect()

if __name__ == "__main__":
    main()

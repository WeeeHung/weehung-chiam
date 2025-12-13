"""
Memory Module: Log or store memory for the agent

This module handles:
- Storing conversation history
- Retrieving relevant past interactions
- Managing long-term memory (optional: vector store, cache, or on-disk logs)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os


class Memory:
    """
    Memory class for storing and retrieving agent interactions.
    """
    
    def __init__(self, storage_path: str = "logs/memory.json"):
        """
        Initialize the memory store.
        
        Args:
            storage_path: Path to store memory (JSON file or directory)
        """
        self.storage_path = storage_path
        self.memory: List[Dict[str, Any]] = []
        self._load_memory()
    
    def store(self, interaction: Dict[str, Any]) -> None:
        """
        Store an interaction in memory.
        
        Args:
            interaction: Dictionary containing:
                - input: User input
                - output: Agent output
                - timestamp: When it occurred
                - metadata: Additional context
        """
        interaction["timestamp"] = datetime.now().isoformat()
        self.memory.append(interaction)
        self._save_memory()
    
    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant past interactions based on a query.
        
        Args:
            query: Search query to find relevant memories
            limit: Maximum number of memories to return
            
        Returns:
            List of relevant interaction dictionaries
        """
        # TODO: Implement semantic search or keyword matching
        # For now, return recent interactions
        return self.memory[-limit:] if len(self.memory) > limit else self.memory
    
    def get_recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most recent n interactions.
        
        Args:
            n: Number of recent interactions to return
            
        Returns:
            List of recent interaction dictionaries
        """
        return self.memory[-n:] if len(self.memory) > n else self.memory
    
    def clear(self) -> None:
        """Clear all stored memory."""
        self.memory = []
        self._save_memory()
    
    def _load_memory(self) -> None:
        """Load memory from storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.memory = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.memory = []
        else:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            self.memory = []
    
    def _save_memory(self) -> None:
        """Save memory to storage."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.memory, f, indent=2)


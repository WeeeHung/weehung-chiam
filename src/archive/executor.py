"""
Executor Module: Logic for calling LLMs (Gemini API) or tools

This module handles the execution of tasks, including:
- Calling the Google Gemini API
- Invoking external tools or APIs
- Processing and formatting responses
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()


class Executor:
    """
    Executor class responsible for executing tasks using Gemini API and tools.
    """
    
    def __init__(self):
        """Initialize the executor with Gemini API configuration."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables. "
                "Please create a .env file with your API key."
            )
        
        # Set API key as environment variable for google-genai client
        os.environ["GEMINI_API_KEY"] = api_key
        self.client = genai.Client(api_key=api_key)
    
    def execute(self, task: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a single task.
        
        Args:
            task: Task dictionary containing task description and metadata
            context: Optional context information
            
        Returns:
            Dictionary containing:
            - result: The execution result
            - success: Boolean indicating success/failure
            - error: Error message if failed
        """
        try:
            task_description = task.get("task", "")
            
            # Build prompt with context if available
            prompt = self._build_prompt(task_description, context)
            
            # Call Gemini API
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            
            return {
                "result": response.text,
                "success": True,
                "error": None
            }
        except Exception as e:
            return {
                "result": None,
                "success": False,
                "error": str(e)
            }
    
    def _build_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build the prompt for Gemini API.
        
        Args:
            task: Task description
            context: Optional context information
            
        Returns:
            Formatted prompt string
        """
        prompt = f"Task: {task}\n\n"
        
        if context:
            prompt += f"Context: {context}\n\n"
        
        prompt += "Please provide a helpful response to complete this task."
        
        return prompt
    
    def call_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Any:
        """
        Call an external tool or API.
        
        Args:
            tool_name: Name of the tool to call
            tool_params: Parameters for the tool
            
        Returns:
            Tool execution result
        """
        # TODO: Implement tool calling logic
        # This could include web search, calculator, database queries, etc.
        
        raise NotImplementedError(f"Tool '{tool_name}' not yet implemented")


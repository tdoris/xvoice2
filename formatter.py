"""
Optional LLM-based text formatting module.
Uses LLM APIs to correct grammar and punctuation in transcribed text.
Supports both cloud APIs (OpenAI) and local models via Ollama.
"""

import requests
import json
from typing import Optional, Dict, Any
import config

class TextFormatter:
    """Handles formatting transcribed text using LLM APIs."""
    
    def __init__(self):
        """Initialize the formatter with configuration settings."""
        self.use_llm = config.USE_LLM
        self.api_key = config.LLM_API_KEY
        self.model = config.LLM_MODEL
        self.prompt = config.LLM_PROMPT
        
        # Ollama specific settings
        self.use_local_llm = config.USE_LOCAL_LLM
        self.ollama_model = config.OLLAMA_MODEL
        self.ollama_url = config.OLLAMA_URL
        
    def format_text(self, text: str, mode: str = "general") -> str:
        """
        Format text using an LLM API to correct grammar and punctuation.
        
        Args:
            text: Raw transcribed text to format
            mode: Dictation mode (e.g., "general", "email", "command")
            
        Returns:
            Formatted text, or the original text if formatting is disabled or fails
        """
        # Return the original text if LLM formatting is disabled or text is empty
        if not text.strip():
            return text
            
        # Check which LLM option is enabled (if any)
        use_openai = self.use_llm and self.api_key
        use_ollama = self.use_local_llm
        
        if not use_openai and not use_ollama:
            return text
            
        try:
            # Adjust prompt based on mode
            mode_prompt = self._get_mode_prompt(mode)
            full_prompt = f"{mode_prompt} {text}"
            
            # Choose LLM provider based on configuration
            if use_ollama:
                response = self._call_ollama_api(full_prompt)
            elif use_openai:
                response = self._call_openai_api(full_prompt)
            else:
                return text
            
            if response:
                return response
            return text
        except Exception as e:
            print(f"Error formatting text: {e}")
            return text
    
    def _get_mode_prompt(self, mode: str) -> str:
        """
        Get the appropriate prompt for the current dictation mode.
        
        Args:
            mode: Dictation mode
            
        Returns:
            Prompt string for the specified mode
        """
        if mode == "email":
            return "Format the following text as professional email content with proper grammar and punctuation:"
        elif mode == "command":
            return "Format the following as a clear command, preserving technical terms and structure:"
        else:  # general mode
            return self.prompt
    
    def _call_openai_api(self, prompt: str) -> Optional[str]:
        """
        Call the OpenAI API to format the text.
        
        Args:
            prompt: Full prompt with text to format
            
        Returns:
            Formatted text from the API or None if the request fails
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that fixes grammar and punctuation only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # Low temperature for more consistent results
            "max_tokens": 1024
        }
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(data),
                timeout=5  # Short timeout to ensure low latency
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["choices"][0]["message"]["content"].strip()
        except requests.RequestException as e:
            print(f"API request error: {e}")
            return None
            
    def _call_ollama_api(self, prompt: str) -> Optional[str]:
        """
        Call the local Ollama API to format the text.
        
        Args:
            prompt: Full prompt with text to format
            
        Returns:
            Formatted text from the local LLM or None if the request fails
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.ollama_model,
            "prompt": prompt,
            "system": "You are a helpful assistant that fixes grammar and punctuation only.",
            "stream": False,
            "temperature": 0.3,  # Low temperature for more consistent results
        }
        
        try:
            response = requests.post(
                self.ollama_url,
                headers=headers,
                data=json.dumps(data),
                timeout=5  # Short timeout to ensure low latency
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Ollama response format is different from OpenAI
            return result.get("response", "").strip()
        except requests.RequestException as e:
            print(f"Ollama API request error: {e}")
            return None

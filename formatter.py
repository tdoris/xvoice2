"""
Optional LLM-based text formatting module.
Uses LLM APIs to correct grammar and punctuation in transcribed text.
Supports both cloud APIs (OpenAI) and local models via Ollama.
"""

import requests
import json
import platform
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
            print("[DEBUG] Text is empty, skipping formatting")
            return text
            
        # Check which LLM option is enabled (if any)
        use_openai = self.use_llm and self.api_key
        use_ollama = self.use_local_llm
        
        if not use_openai and not use_ollama:
            print("[DEBUG] No LLM service is enabled for formatting")
            return text
            
        try:
            # Adjust prompt based on mode
            mode_prompt = self._get_mode_prompt(mode)
            full_prompt = f"{mode_prompt} {text}"
            print(f"[DEBUG] Sending prompt to LLM: '{full_prompt}'")
            
            # Choose LLM provider based on configuration
            if use_ollama:
                print(f"[DEBUG] Using Ollama with model: {self.ollama_model}")
                response = self._call_ollama_api(full_prompt)
            elif use_openai:
                print(f"[DEBUG] Using OpenAI with model: {self.model}")
                response = self._call_openai_api(full_prompt)
            else:
                return text
            
            if response:
                print(f"[DEBUG] Received formatted response from LLM")
                return response
            
            print("[DEBUG] LLM returned empty response, using original text")
            return text
        except Exception as e:
            print(f"[DEBUG] Error formatting text: {e}")
            return text
    
    def _get_mode_prompt(self, mode: str) -> str:
        """
        Get the appropriate prompt for the current dictation mode.
        
        Args:
            mode: Dictation mode
            
        Returns:
            Prompt string for the specified mode
        """
        is_macos = platform.system() == "Darwin"
        os_type = "macOS" if is_macos else "Linux"
        
        if mode == "email":
            return "Format the following text as professional email content with proper grammar and punctuation:"
        elif mode == "command":
            return f"""
You are a command-line expert for {os_type}. 
Convert the following spoken instruction into a valid shell command for {os_type}.
Focus on common terminal commands and utilities available on {os_type} systems.
If the instruction appears to be a command already, just fix any syntax errors.
For complex instructions, create a pipeline or script that achieves the goal.
Do not include explanations or markdown formatting, ONLY output the exact command to execute.
For example:
- "list all files in the current directory" → "ls -la"
- "create a new folder called projects" → "mkdir projects"
- "find all python files containing the word error" → "find . -name '*.py' -exec grep -l 'error' {{}} \\;"

Instruction: """
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
        
        # Use different system message based on whether we're in command mode
        if prompt.strip().startswith("You are a command-line expert for"):
            system_message = "You are a shell command expert. Only respond with the exact command to run, no explanations or markdown."
        else:
            system_message = "You are a helpful assistant that fixes grammar and punctuation only."
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # Low temperature for more consistent results
            "max_tokens": 1024
        }
        
        try:
            print(f"[DEBUG] Sending request to OpenAI API")
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(data),
                timeout=5  # Short timeout to ensure low latency
            )
            
            print(f"[DEBUG] OpenAI API status code: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            
            formatted_text = result["choices"][0]["message"]["content"].strip()
            print(f"[DEBUG] OpenAI API response: '{formatted_text}'")
            return formatted_text
        except requests.RequestException as e:
            print(f"[DEBUG] OpenAI API request error: {e}")
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
        
        # Use different system message based on whether we're in command mode
        if prompt.strip().startswith("You are a command-line expert for"):
            system_message = "You are a shell command expert. Only respond with the exact command to run, no explanations or markdown."
        else:
            system_message = "You are a helpful assistant that fixes grammar and punctuation only."
        
        data = {
            "model": self.ollama_model,
            "prompt": prompt,
            "system": system_message,
            "stream": False,
            "temperature": 0.3,  # Low temperature for more consistent results
        }
        
        try:
            print(f"[DEBUG] Sending request to Ollama API")
            response = requests.post(
                self.ollama_url,
                headers=headers,
                data=json.dumps(data),
                timeout=5  # Short timeout to ensure low latency
            )
            
            print(f"[DEBUG] Ollama API status code: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            
            # Ollama response format is different from OpenAI
            formatted_text = result.get("response", "").strip()
            print(f"[DEBUG] Ollama API response: '{formatted_text}'")
            return formatted_text
        except requests.RequestException as e:
            print(f"[DEBUG] Ollama API request error: {e}")
            return None

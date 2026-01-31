import os
import httpx
import hashlib
import json
import redis
from openai import OpenAI
from typing import List, Dict, Any

class LLM:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        # Support for local LLMs (e.g. Ollama) via OpenAI compatibility
        # If arguments are provided, use them. Otherwise, fall back to env vars.
        
        self.api_key = api_key if api_key else os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "ollama"))
        self.base_url = base_url if base_url else os.getenv("LLM_BASE_URL") # e.g. http://localhost:11434/v1 for Ollama
        self.model = model if model else os.getenv("LLM_MODEL", "gpt-4o")
        
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        # Optimized HTTP client for high concurrency
        http_client = httpx.Client(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=httpx.Timeout(300.0, connect=60.0)
        )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=http_client
        )
        
        # Initialize Redis Cache (Redis Stack on 6380)
        try:
            self.redis = redis.Redis(host='localhost', port=6380, decode_responses=True)
            self.redis.ping()
            print("⚡ LLM Cache Active (Redis Stack:6380)")
        except Exception:
            self.redis = None
            print("⚠️ LLM Cache Inactive (Redis unavailable)")

    def generate(self, prompt: str, system_message: str = "You are a helpful research assistant.", temperature: float = 0.7) -> str:
        # 1. Check Cache
        if self.redis and temperature == 0.0: # Only cache deterministic outputs
            cache_key = f"llm_cache:{hashlib.md5((system_message + prompt + self.model).encode()).hexdigest()}"
            cached_resp = self.redis.get(cache_key)
            if cached_resp:
                return cached_resp

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=8192, # Increased to prevent truncation
                extra_body={"options": {"num_ctx": 32768}} # Force larger context for Ollama
            )
            content = response.choices[0].message.content.strip()
            
            # 2. Set Cache (Expire in 24 hours)
            if self.redis and temperature == 0.0 and content:
                self.redis.setex(cache_key, 86400, content)
                
            return content
        except Exception as e:
            print(f"LLM Error: {e}")
            return ""

    def get_embedding(self, text: str) -> List[float]:
        text = text.replace("\n", " ")
        try:
            return self.client.embeddings.create(input = [text], model=self.embedding_model).data[0].embedding
        except Exception as e:
            print(f"Embedding Error: {e}")
            return []

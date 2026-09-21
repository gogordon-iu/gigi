#!/usr/bin/env python3
import requests
import json

# Ollama server URL (default is localhost:11434)
url = "http://localhost:11434/api/chat"

# Test payload
payload = {
    "model": "hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M",  # Change to your model name
    "messages": [
        {
            "role": "system",
            "content": "Extract only name form text"
        },
        {
            "role": "user",
            "content": "Hi, my name is David"
        }
    ],
    "stream": False
}

print("Testing Ollama server...")
print(f"URL: {url}")
print(f"Model: {payload['model']}\n")

try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
    
    result = response.json()
    print("Response:")
    print(result['message']['content'])
    print("\n✓ Ollama server is working!")
    
except Exception as e:
    print(f"✗ Error: {e}")
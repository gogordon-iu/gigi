# from transformers import AutoModelForCausalLM, AutoTokenizer
import ollama
import requests
import subprocess
import time
import threading
import random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

LLM_TIMEOUT = 120

class Conversation:
    def __init__(self, system_prompt=None, use_rag=False, rag_file_path=None):
        self.use_rag = use_rag
        self.rag_file_path = rag_file_path
        self.rag_chunks = []
        self.vectorizer = None
        self.tfidf_matrix = None
        
        if self.use_rag and self.rag_file_path:
            self._initialize_rag()
            
        # print("Initiazling conversation (starting ollame server)...")

        # subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # time.sleep(10)

        #model_name = "EleutherAI/gpt-neo-125M"  # Replace with a smaller model if needed
        #self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        #self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M"
        self.conversation_history = []
        if system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            self.conversation_history.append({
                "role": "system",
                "content": "Your name is Gigi, a social robot teaching assistant. " +
                 "You are going to interact with children in a friendly and engaging manner. You are perky, curious and generally happy." +
                 "Keep your responses concise and appropriate for children." + 
                 "DO NOT include any movements, or facial expressions. Respond only with the speech content."
            })

        self.max_history = 5 
        # Assign eos_token as pad_token
        #self.tokenizer.pad_token = self.tokenizer.eos_token

        self.text = []

        self.waiting_options = [
            "You know, that is a really thoughtful way to look at it. I was just considering how that fits into our activity today.",
            "Let me take a good look at what we have found so far. It is really interesting how all these pieces are coming together.",
            "I am really glad you shared that with me. It iss exactly that kind of creativity that makes working on this so much fun.",
            "You know, I was just noticing how much effort you are putting into this today. It is really wonderful to see how you are approaching these ideas.", 
            "It is so interesting to hear your perspective on this. I always find that everyone sees things just a little bit differently."
        ]

        self.timeout_options = [
            'That was great, thank you.',
            'Thank you for sharing your thoughts.',
            'Amazing disucssions.'
            ]


    # def response(self, input_text=None):
    #     if input_text is None:
    #         input_text = "What is the meaning of life?"
    #     inputs = self.tokenizer(input_text, return_tensors="pt", padding=True)

    #     # Pass attention_mask during generation
    #     output = self.model.generate(
    #         inputs.input_ids,
    #         attention_mask=inputs.attention_mask,
    #         max_length=50,
    #         pad_token_id=self.tokenizer.eos_token_id,  # Set padding token ID explicitly
    #         do_sample=True,
    #         temperature=0.5,  # Add some randomness
    #         top_p=0.9,        # Focus on the top 90% of probable tokens
    #     )

    #     # Decode and print the output
    #     print(self.tokenizer.decode(output[0], skip_special_tokens=True))
    #     self.text.append(self.tokenizer.decode(output[0], skip_special_tokens=True))
    
    def _initialize_rag(self):
        try:
            with open(self.rag_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Chunk by paragraphs
            chunks = [c.strip() for c in content.split('\n\n') if c.strip()]
            
            if not chunks:
                # Fallback to lines if no double newlines exist
                chunks = [c.strip() for c in content.split('\n') if c.strip()]
                
            self.rag_chunks = chunks
            if self.rag_chunks:
                self.vectorizer = TfidfVectorizer(stop_words='english')
                self.tfidf_matrix = self.vectorizer.fit_transform(self.rag_chunks)
                print(f"RAG initialized with {len(self.rag_chunks)} chunks.")
        except Exception as e:
            print(f"Error initializing RAG: {e}")

    def retrieve_rag_context(self, user_query, top_k=2):
        if not self.use_rag or not self.rag_chunks or self.vectorizer is None:
            return ""
        
        try:
            query_vec = self.vectorizer.transform([user_query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            
            # Get indices of top_k most similar chunks
            # To handle cases where we have fewer chunks than top_k
            k = min(top_k, len(self.rag_chunks))
            top_indices = similarities.argsort()[-k:][::-1]
            
            retrieved = []
            for idx in top_indices:
                if similarities[idx] > 0.05:  # Relevance threshold
                    retrieved.append(self.rag_chunks[idx])
                    
            if retrieved:
                return "\n\n".join(retrieved)
        except Exception as e:
            print(f"Error retrieving RAG context: {e}")
            
        return ""

    def get_response(self, system_prompt, user_prompt):
        rag_content = self.retrieve_rag_context(user_prompt)
        final_system_prompt = system_prompt
        if rag_content:
            final_system_prompt += f"\n\nContext information:\n{rag_content}"

        messages = [
            {"role": "system", "content": final_system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7
            }
        }
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=LLM_TIMEOUT  # Wait a maximum of 10 seconds
            )
            response.raise_for_status()
            result = response.json()["message"]["content"]
        except requests.exceptions.Timeout:
            result = random.choice(self.timeout_options)
        
        print(result)
        return result


    def get_response_with_tts_sync(self, text):
        """Get LLM response with conversation memory"""
        if not text:
            return "I didn't understand that."
        
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": text
            })
            
            # Trim history to keep memory usage low
            # Keep system message + last N exchanges
            if len(self.conversation_history) > (self.max_history * 2):
                # Keep first message if it's a system message, otherwise start fresh
                if self.conversation_history[0].get("role") == "system":
                    self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-(self.max_history * 2):]
                else:
                    self.conversation_history = self.conversation_history[-(self.max_history * 2):]
            
            # Use /api/chat endpoint for conversation support
            print( self.conversation_history)
            
            api_messages = list(self.conversation_history)
            rag_content = self.retrieve_rag_context(text)
            if rag_content:
                if api_messages and api_messages[0].get("role") == "system":
                    original_system = api_messages[0]["content"]
                    api_messages[0] = {
                        "role": "system",
                        "content": f"{original_system}\n\nContext information:\n{rag_content}"
                    }
                else:
                    api_messages.insert(0, {
                        "role": "system",
                        "content": f"Context information:\n{rag_content}"
                    })

            response = requests.post(f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": api_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_ctx": 2048
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            if response.status_code == 200:
                assistant_message = response.json()["message"]["content"].strip()
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                print(f"🤖 AI: {assistant_message}")
                print(f"💾 History: {len(self.conversation_history)} messages")
                return assistant_message
            else:
                error_msg = "Sorry, having trouble responding."
                return error_msg
                
        except Exception as e:
            print(f"❌ LLM error: {e}")
            error_msg = "Connection issue."
            return error_msg


    def get_response_threaded(self, system_prompt, user_prompt, on_success):
        """
        Wraps get_response in a background thread.
        :param system_prompt: The system instructions
        :param user_prompt: The user input
        :param on_success: Callback function that takes the string response
        :param on_error: Callback function that takes an error message/exception
        """
        def worker():
            try:
                # Call your existing function
                result = self.get_response(system_prompt, user_prompt)
                # Send the result back via the success callback
                on_success(result)
            except Exception as e:
                # Catch errors (timeouts, 500s, etc.) and send back via error callback
                print(f"Threaded LLM Error: {e}")

        # Create and start the thread
        thread = threading.Thread(target=worker, daemon=True)
        return thread

if __name__ == "__main__":
    conv = Conversation()
    resp=conv.get_response_with_tts_sync("Hello, how are you?")
    print(resp)

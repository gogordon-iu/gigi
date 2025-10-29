from transformers import AutoModelForCausalLM, AutoTokenizer
import ollama
import requests

class Conversation:
    def __init__(self):
        print("Initiazling conversation ...")

        model_name = "EleutherAI/gpt-neo-125M"  # Replace with a smaller model if needed
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "llama3.2:1b-instruct-q4_K_M"
        self.conversation_history = []
        self.max_history = 5 
        # Assign eos_token as pad_token
        self.tokenizer.pad_token = self.tokenizer.eos_token

        self.text = []

    def response(self, input_text=None):
        if input_text is None:
            input_text = "What is the meaning of life?"
        inputs = self.tokenizer(input_text, return_tensors="pt", padding=True)

        # Pass attention_mask during generation
        output = self.model.generate(
            inputs.input_ids,
            attention_mask=inputs.attention_mask,
            max_length=50,
            pad_token_id=self.tokenizer.eos_token_id,  # Set padding token ID explicitly
            do_sample=True,
            temperature=0.5,  # Add some randomness
            top_p=0.9,        # Focus on the top 90% of probable tokens
        )

        # Decode and print the output
        print(self.tokenizer.decode(output[0], skip_special_tokens=True))
        self.text.append(self.tokenizer.decode(output[0], skip_special_tokens=True))
    
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
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": self.conversation_history,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 100
                    }
                },
                timeout=30
            )
            
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
        
if __name__ == "__main__":
    conv = Conversation()
    resp=conv.get_response_with_tts_sync("Hello, how are you?")
    print(resp)

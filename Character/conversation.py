import requests
import threading
import random
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from characterDefinitions import IS_ROBOT

LLM_TIMEOUT = 120


# ------------------------------------------------------------------
# Output sanitiser — applied to every LLM response before returning
# ------------------------------------------------------------------
def clean_response(text: str) -> str:
    """
    Strips role echoes and hallucinated extra turns without truncating sentences.
    """
    if not text:
        return text
    # Strip echoed role prefix
    text = re.sub(r"^(robot:|assistant:|student:|gigi:)\s*", "", text.strip(), flags=re.IGNORECASE)
    # Cut if the model hallucinated a new speaker turn
    text = re.split(r"\n\s*(student:|robot:|user:|assistant:|gigi:)", text, flags=re.IGNORECASE)[0]
    return text.strip() or "That sounds really interesting — tell me more!"


# ------------------------------------------------------------------
# Conversation
# ------------------------------------------------------------------
class Conversation:
    def __init__(self, system_prompt=None, use_rag=False, rag_file_path=None):
        self.use_rag = use_rag
        self.rag_file_path = rag_file_path
        self.rag_chunks = []
        self.vectorizer = None
        self.tfidf_matrix = None

        if self.use_rag and self.rag_file_path:
            self._initialize_rag()

        if IS_ROBOT:
            self.ollama_url   = "http://localhost:8080/rkllm_chat"
            self.ollama_model = "qwen"
            self.fast_model   = "qwen"
        else:
            self.ollama_url   = "http://localhost:11434/v1/chat/completions"
            self.ollama_model = "llama3.2:1b-instruct-q4_K_M"
            self.fast_model   = "llama3.2:1b-instruct-q4_K_M"
        self.conversation_history = []

        default_system = (
            "Your name is Gigi, a social robot teaching assistant. "
            "You are going to interact with children in a friendly and engaging manner. "
            "You are perky, curious and generally happy. "
            "Reply with ONE short conversational sentence. "
            "Do NOT use lists, bullet points, or numbers. "
            "Do NOT give multiple ideas or explanations. "
            "Speak naturally as if talking out loud. "
            "Stop immediately after the first sentence."
        )

        self.conversation_history.append({
            "role": "system",
            "content": system_prompt if system_prompt else default_system
        })

        self.max_history = 5

        self.waiting_options = [
            "You know, that is a really thoughtful way to look at it. I was just considering how that fits into our activity today.",
            "Let me take a good look at what we have found so far. It is really interesting how all these pieces are coming together.",
            "I am really glad you shared that with me. It is exactly that kind of creativity that makes working on this so much fun.",
            "You know, I was just noticing how much effort you are putting into this today. It is really wonderful to see how you are approaching these ideas.",
            "It is so interesting to hear your perspective on this. I always find that everyone sees things just a little bit differently."
        ]

        self.timeout_options = [
            'That was great, thank you.',
            'Thank you for sharing your thoughts.',
            'Amazing discussions.'
        ]

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------
    def _initialize_rag(self):
        try:
            with open(self.rag_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = [c.strip() for c in content.split('\n\n') if c.strip()]
            if not chunks:
                chunks = [c.strip() for c in content.split('\n') if c.strip()]

            self.rag_chunks = chunks
            if self.rag_chunks:
                self.vectorizer  = TfidfVectorizer(stop_words='english')
                self.tfidf_matrix = self.vectorizer.fit_transform(self.rag_chunks)
                print(f"RAG initialized with {len(self.rag_chunks)} chunks.")
        except Exception as e:
            print(f"Error initializing RAG: {e}")

    def retrieve_rag_context(self, user_query, top_k=2):
        if not self.use_rag or not self.rag_chunks or self.vectorizer is None:
            return ""
        try:
            query_vec    = self.vectorizer.transform([user_query])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            k            = min(top_k, len(self.rag_chunks))
            top_indices  = similarities.argsort()[-k:][::-1]
            retrieved    = [self.rag_chunks[idx] for idx in top_indices if similarities[idx] > 0.05]
            if retrieved:
                return "\n\n".join(retrieved)
        except Exception as e:
            print(f"Error retrieving RAG context: {e}")
        return ""

    # ------------------------------------------------------------------
    # Core response helper — shared by both public methods
    # ------------------------------------------------------------------
    def _call_npu(self, messages: list, model: str = None) -> str:
        """
        Send `messages` to the NPU server and return the raw text response.
        Falls back to a timeout phrase on any error.
        """
        payload = {
            "model":    model if model else self.ollama_model,
            "messages": messages,
            "stream":   False
        }
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=LLM_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"]
            print(f"⚠️  NPU returned empty choices: {data}")
        except Exception as e:
            print(f"❌ NPU Server Error: {e}")
        return random.choice(self.timeout_options)

    # ------------------------------------------------------------------
    # Public: stateless single-turn  (used by InteractionManager)
    # ------------------------------------------------------------------
    def check_fluid_done(self, transcript: str) -> bool:
        """
        Uses a fast LLM to check if the user has responded to the last robot query.
        """
        last_robot_query = ""
        for msg in reversed(self.conversation_history):
            if msg["role"] in ["assistant", "system", "gigi", "robot"]:
                last_robot_query = msg["content"]
                break

        system_prompt = (
            "You are a logical evaluator. Classify if the User's response answers the Robot's question. "
            "If the user provides a valid answer ANYWHERE in their response, even if they also talk about unrelated things, it is considered ANSWERED. "
            "First, print your reasoning. Then, on a new line at the very end, output exactly 'CONCLUSION: ANSWERED' or 'CONCLUSION: UNANSWERED'.\n\n"
            "=== EXAMPLES ===\n"
            "Robot: What's your favorite color?\nUser: My favorite is blue.\n"
            "Reasoning: The user explicitly states their favorite color is blue.\nCONCLUSION: ANSWERED\n\n"
            "Robot: What's your favorite color?\nUser: Today is Thursday.\n"
            "Reasoning: The user talks about the day of the week, which does not answer the question about color.\nCONCLUSION: UNANSWERED\n\n"
            "Robot: What did you eat for breakfast?\nUser: I woke up really late today and was super tired, but I managed to eat some cereal.\n"
            "Reasoning: The user mentions eating cereal, which answers the question, despite the unrelated preamble.\nCONCLUSION: ANSWERED\n"
            "=== END OF EXAMPLES ==="
        )

        user_prompt = (
            "Now, evaluate the following:\n\n"
            f"Robot: {last_robot_query}\n"
            f"User: {transcript}\n"
            "Reasoning:"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            raw = self._call_npu(messages, model=self.fast_model)
            response_text = raw.strip().upper()
            print(f"DEBUG: Response from check_fluid_done:\n{response_text}")
            
            # Look for the structured conclusion
            if "CONCLUSION: ANSWERED" in response_text and "CONCLUSION: UNANSWERED" not in response_text:
                return True
            elif "CONCLUSION: UNANSWERED" in response_text:
                return False
                
            # Fallback in case it forgot the "CONCLUSION:" prefix, check the last line
            last_line = response_text.split('\n')[-1]
            if "ANSWERED" in last_line and "UNANSWERED" not in last_line:
                return True
            return False
        except Exception as e:
            print(f"Error in check_fluid_done: {e}")
            return False

    def get_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Stateless call: builds a fresh 2-message payload, returns ONE sentence.
        Does NOT touch conversation_history.
        """
        rag_content = self.retrieve_rag_context(user_prompt)
        final_system = system_prompt
        if rag_content:
            final_system += f"\n\nContext information:\n{rag_content}"

        messages = [
            {"role": "system", "content": final_system},
            {"role": "user",   "content": user_prompt}
        ]

        raw    = self._call_npu(messages)
        result = clean_response(raw)          # ← basic cleaning only, no sentence truncation
        print(f"🤖 Gigi: {result}")
        return result

    # ------------------------------------------------------------------
    # Public: stateful multi-turn  (used by free-form chat)
    # ------------------------------------------------------------------
    def get_response_with_tts_sync(self, text: str) -> str:
        """
        Stateful call: maintains conversation_history, returns ONE sentence.
        """
        if not text:
            return "I didn't understand that."

        try:
            self.conversation_history.append({"role": "user", "content": text})

            # Trim history, keeping the system message
            if len(self.conversation_history) > (self.max_history * 2):
                if self.conversation_history[0].get("role") == "system":
                    self.conversation_history = (
                        [self.conversation_history[0]] +
                        self.conversation_history[-(self.max_history * 2):]
                    )
                else:
                    self.conversation_history = self.conversation_history[-(self.max_history * 2):]

            print(self.conversation_history)

            # Inject RAG into a copy — don't mutate persistent history
            api_messages = list(self.conversation_history)
            rag_content  = self.retrieve_rag_context(text)
            if rag_content:
                if api_messages and api_messages[0].get("role") == "system":
                    api_messages[0] = {
                        "role":    "system",
                        "content": api_messages[0]["content"] + f"\n\nContext information:\n{rag_content}"
                    }
                else:
                    api_messages.insert(0, {"role": "system", "content": f"Context information:\n{rag_content}"})

            raw    = self._call_npu(api_messages)
            result = _first_sentence(raw)       # ← truncate here too

            self.conversation_history.append({"role": "assistant", "content": result})

            print(f"🤖 Gigi: {result}")
            print(f"💾 History: {len(self.conversation_history)} messages")
            return result

        except Exception as e:
            print(f"❌ LLM error: {e}")
            return "Connection issue."

    # ------------------------------------------------------------------
    # Public: fire-and-forget threaded call
    # ------------------------------------------------------------------
    def get_response_threaded(self, system_prompt: str, user_prompt: str, on_success):
        def worker():
            try:
                result = self.get_response(system_prompt, user_prompt)
                on_success(result)
            except Exception as e:
                print(f"Threaded LLM Error: {e}")

        return threading.Thread(target=worker, daemon=True)


if __name__ == "__main__":
    conv = Conversation()
    resp = conv.get_response(system_prompt="You are Gigi.", user_prompt="Hello, how are you?")
    print(resp)
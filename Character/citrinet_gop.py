import os
import json
import numpy as np

class SimpleBPETokenizer:
    """A pure Python greedy BPE tokenizer matching NeMo SentencePiece tokenizer behavior."""
    def __init__(self, vocab_path):
        if os.path.exists(vocab_path):
            with open(vocab_path, "r", encoding="utf-8") as f:
                self.vocab = json.load(f)
        else:
            self.vocab = []
        self.token_to_id = {tok: idx for idx, tok in enumerate(self.vocab)}
        
    def tokenize(self, text):
        if not self.vocab:
            return []
        text = text.lower().strip()
        words = text.split()
        tokens = []
        for word in words:
            # SentencePiece BPE prefix for word start (U+2581)
            word_str = " " + word
            curr_idx = 0
            while curr_idx < len(word_str):
                matched = False
                for length in range(len(word_str) - curr_idx, 0, -1):
                    sub = word_str[curr_idx:curr_idx + length]
                    if sub in self.token_to_id:
                        tokens.append(self.token_to_id[sub])
                        curr_idx += length
                        matched = True
                        break
                if not matched:
                    # Fallback for unknown characters
                    tokens.append(self.token_to_id.get("[unk]", 0))
                    curr_idx += 1
        return tokens


class MelPreprocessor:
    """A pure NumPy/Librosa audio preprocessor matching NeMo's Citrinet Mel preprocessor."""
    def __init__(self, sample_rate=16000, n_mels=64, n_fft=512, win_length=400, hop_length=160):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.win_length = win_length
        self.hop_length = hop_length
        
    def preprocess(self, audio):
        import librosa
        
        # Pre-emphasis filter
        audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])
        
        # Short-Time Fourier Transform
        stft = librosa.stft(
            audio,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            win_length=self.win_length,
            window='hann',
            center=True
        )
        
        # Power spectrogram
        power = np.abs(stft) ** 2
        
        # Mel filterbank (using Slaney scale, matching NeMo defaults)
        mel = librosa.feature.melspectrogram(
            S=power,
            sr=self.sample_rate,
            n_mels=self.n_mels,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            htk=False,
            fmin=0.0,
            fmax=8000.0
        )
        
        # Log scaling
        log_mel = np.log(mel + 1e-5)
        
        # Per-channel mean-variance normalization
        mean = log_mel.mean(axis=1, keepdims=True)
        std = log_mel.std(axis=1, keepdims=True)
        log_mel = (log_mel - mean) / (std + 1e-5)
        
        return log_mel


class CitrinetGOP:
    """Offline SOTA Pronunciation Assessment engine using NeMo Citrinet-256 on Orange Pi 5 Pro NPU."""
    def __init__(self, model_path=None, vocab_path=None):
        _char_dir = os.path.dirname(os.path.abspath(__file__))
        _resources_dir = os.path.abspath(os.path.join(_char_dir, "..", "Resources"))
        
        if model_path is None:
            model_path = os.path.join(_resources_dir, "citrinet_256.rknn")
        if vocab_path is None:
            vocab_path = os.path.join(_resources_dir, "citrinet_vocab.json")
            
        self.tokenizer = SimpleBPETokenizer(vocab_path)
        self.preprocessor = MelPreprocessor()
        self.rknn = None
        self.use_mock = False
        
        if not os.path.exists(model_path):
            print(f"[Citrinet GOP] RKNN model file not found at {model_path}. Running in MOCK mode.")
            self.use_mock = True
        else:
            try:
                from rknnlite.api import RKNNLite
                self.rknn = RKNNLite()
                ret = self.rknn.load_rknn(model_path)
                if ret != 0:
                    raise RuntimeError(f"load_rknn failed with code {ret}")
                ret = self.rknn.init_runtime()
                if ret != 0:
                    raise RuntimeError(f"init_runtime failed with code {ret}")
                print(f"[Citrinet GOP] Citrinet-256 RKNN model loaded successfully from {model_path}.")
            except Exception as e:
                print(f"[Citrinet GOP] Failed to initialize RKNN runtime: {e}. Running in MOCK mode.")
                self.use_mock = True

    def calculate_gop(self, audio_float, target_text, transcription=None):
        """
        Assess pronunciation of target_text from audio_float.
        Returns:
          gop_score (float): Score between 0 and 100.
        """
        if self.use_mock:
            # In mock mode, compute simulated score using a string similarity check (levenshtein distance fallback)
            # This allows testing the pipeline without NPU hardware or model files.
            from difflib import SequenceMatcher
            if transcription:
                t_clean = transcription.lower().strip()
                target_clean = target_text.lower().strip()
                if target_clean in t_clean.split():
                    similarity = 1.0
                else:
                    similarity = SequenceMatcher(None, target_clean, t_clean).ratio()
            else:
                similarity = 0.0
            sim_score = float(similarity * 100.0)
            return sim_score

        try:
            # 1. Preprocess audio to log-mel spectrogram features
            log_mel = self.preprocessor.preprocess(audio_float)
            
            # Citrinet-256 expects shape (1, 64, 298)
            STATIC_T = 298
            if log_mel.shape[1] < STATIC_T:
                log_mel = np.pad(log_mel, ((0, 0), (0, STATIC_T - log_mel.shape[1])), mode='constant')
            else:
                log_mel = log_mel[:, :STATIC_T]
            log_mel = np.expand_dims(log_mel, axis=0).astype(np.float32)

            # 2. Run NPU Inference
            outputs = self.rknn.inference(inputs=[log_mel])
            logits = outputs[0][0] # Shape (T, V) where T = 298 (or downsampled frames) and V is vocab size
            
            # NeMo Citrinet-256 outputs log probabilities (CTC logits)
            # Apply log-softmax to get correct log-posterior probabilities if not already applied by model
            # For Citrinet, logits are raw, so we apply log_softmax
            exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
            log_probs = np.log(exp_logits / np.sum(exp_logits, axis=-1, keepdims=True) + 1e-20)
            
            # 3. Tokenize target text
            target_tokens = self.tokenizer.tokenize(target_text)
            if not target_tokens:
                return 0.0
                
            # 4. Perform CTC Forced Alignment (Viterbi Search)
            T, V = log_probs.shape
            U = len(target_tokens)
            
            # Construct Y_prime with interleaved blanks (blank is token index 0)
            Y_prime = []
            for token in target_tokens:
                Y_prime.append(0)
                Y_prime.append(token)
            Y_prime.append(0)
            S = len(Y_prime)
            
            # Viterbi dynamic programming table
            dp = np.full((T, S), -np.inf)
            backpointers = np.zeros((T, S), dtype=int)
            
            dp[0, 0] = log_probs[0, Y_prime[0]]
            if S > 1:
                dp[0, 1] = log_probs[0, Y_prime[1]]
                
            for t in range(1, T):
                for s in range(S):
                    # Option 1: stay in same state
                    opt1 = dp[t-1, s]
                    best_prev = 0
                    
                    # Option 2: transition from s-1
                    opt2 = dp[t-1, s-1] if s > 0 else -np.inf
                    
                    # Option 3: transition from s-2 (skip blank)
                    if s > 1 and Y_prime[s] != 0 and Y_prime[s] != Y_prime[s-2]:
                        opt3 = dp[t-1, s-2]
                    else:
                        opt3 = -np.inf
                        
                    max_val = max(opt1, opt2, opt3)
                    if max_val == -np.inf:
                        continue
                        
                    dp[t, s] = log_probs[t, Y_prime[s]] + max_val
                    
                    if max_val == opt1:
                        backpointers[t, s] = s
                    elif max_val == opt2:
                        backpointers[t, s] = s - 1
                    else:
                        backpointers[t, s] = s - 2
            
            # 5. Backtrack path
            # Find the best ending state at t = T-1 (either S-1 or S-2)
            best_s = S-1 if dp[T-1, S-1] > dp[T-1, S-2] else S-2
            if dp[T-1, best_s] == -np.inf:
                # If alignment failed, fallback to average score of the target tokens
                return 0.0
                
            path = []
            curr_s = best_s
            for t in range(T - 1, -1, -1):
                path.append(curr_s)
                curr_s = backpointers[t, curr_s]
            path.reverse()
            
            # 6. Calculate GOP Score
            scores = []
            for t in range(T):
                state = path[t]
                if state % 2 == 1: # Odd indices are actual target tokens (not blank)
                    token_id = Y_prime[state]
                    frame_log_probs = log_probs[t]
                    max_log_prob = np.max(frame_log_probs)
                    # GOP frame score
                    frame_score = frame_log_probs[token_id] - max_log_prob
                    scores.append(frame_score)
            
            if not scores:
                return 0.0
                
            mean_score = np.mean(scores)
            # Map log-scale score to 0-100 range
            gop_score = np.exp(mean_score) * 100.0
            return float(gop_score)
            
        except Exception as e:
            print(f"[Citrinet GOP] Error during assessment: {e}")
            return 0.0

    def close(self):
        if self.rknn:
            self.rknn.release()

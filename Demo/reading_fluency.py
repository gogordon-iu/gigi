import os
import json
import sys
import time
import datetime
import string
import re
import random
import threading
from difflib import SequenceMatcher
from PIL import Image

# Append parent dir, Character dir, and Demo dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(current_dir)

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)

character_dir = os.path.join(gigi_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

if current_dir not in sys.path:
    sys.path.append(current_dir)

from character import Character
from capabilities import extract_name

class BackgroundFaceTracker:
    """
    Manages active face follow tracking in a background thread.
    Automatically handles the camera feed overlay, visual feedback icons,
    and torso-based sweep searches when a face is lost for 5+ seconds.
    """
    def __init__(self, gigi):
        self.gigi = gigi
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if not self.gigi.vision:
            print("[Reading Fluency] Vision is disabled, cannot start face follow tracking.")
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self.gigi.follow_face,
            kwargs={'stop_event': self.stop_event},
            daemon=True
        )
        self.thread.start()
        print("[Reading Fluency] Background face follow tracker started.")

    def stop(self):
        if self.thread:
            self.stop_event.set()
            self.thread.join(timeout=1.5)
            self.thread = None
            print("[Reading Fluency] Background face follow tracker stopped.")

def play_reading_fluency(show_karaoke=True, run_hello=True, run_selection=True, story_override=None, run_comprehension=True, force_reread=False):
    print("====================================================")
    print("             GIGI Reading Fluency Demo              ")
    print("====================================================")
    
    # Initialize character with wakeup=True to show face and move to home position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="ReadingFluency")
    
    word_bank = {}
    word_bank_file = None

    def save_word_bank():
        nonlocal word_bank_file, word_bank
        if word_bank_file:
            try:
                with open(word_bank_file, 'w', encoding='utf-8') as f:
                    json.dump(word_bank, f, indent=4)
            except Exception as e:
                print(f"[Word Bank] Error saving word bank: {e}")

    # Allow some time for initialization
    time.sleep(2)
    
    # Ensure assets exist for the demo
    assets_dir = os.path.join(gigi_dir, 'Assets', 'ReadingFluency')
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        
    passage_file = os.path.join(assets_dir, 'passage.txt')
    if not os.path.exists(passage_file):
        with open(passage_file, 'w') as f:
            f.write("The quick brown fox jumps over the lazy dog. It was a sunny day and everyone was happy.")
            
    questions_file = os.path.join(assets_dir, 'questions.txt')
    if not os.path.exists(questions_file):
        with open(questions_file, 'w') as f:
            f.write("What animal jumped over the dog?\nHow was the weather that day?\n")

    tracker = BackgroundFaceTracker(gigi)

    session_log_file = None
    start_session_time = time.time()
    last_event_time = start_session_time

    def log_reading_event(msg):
        nonlocal last_event_time, session_log_file
        now = time.time()
        elapsed = now - start_session_time
        dt = now - last_event_time
        last_event_time = now

        timestamp = datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] (+{elapsed:6.3f}s, dt={dt:6.3f}s) {msg}"
        print(log_line)
        if not session_log_file and getattr(gigi, 'logger', None) and gigi.logger.session_dir:
            session_log_file = os.path.join(gigi.logger.session_dir, "reading_fluency_session.log")
        if session_log_file:
            try:
                with open(session_log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line + "\n")
            except Exception as e:
                print(f"[Logger Error] Could not write to session log: {e}")

    def on_ui_state_update(active, passage_words, current_word_idx, word_states, last_wrong_heard, reading_status):
        if not active:
            log_reading_event(f"[UI Display] active=False (Overlay Hidden)")
            return
        words_summary = []
        if passage_words:
            for idx, w in enumerate(passage_words):
                if w == "\n":
                    words_summary.append("[NEWLINE]")
                    continue
                st = word_states[idx] if (word_states and idx < len(word_states)) else 'unread'
                color_label = "GREEN" if st == 'correct' else ("RED" if st == 'wrong' else "WHITE/GRAY")
                box_label = " [YELLOW HIGHLIGHT BOX]" if (current_word_idx is not None and idx == current_word_idx) else ""
                words_summary.append(f"{idx}:'{w}'({color_label}{box_label})")
        highlight_word = passage_words[current_word_idx] if (passage_words and current_word_idx is not None and 0 <= current_word_idx < len(passage_words)) else "None"
        status_str = f", status='{reading_status}'" if reading_status else ""
        log_reading_event(f"[UI Display Update{status_str}] HighlightedWord: '{highlight_word}' (idx={current_word_idx}) | Words: [{', '.join(words_summary)}]")

    if gigi.face:
        gigi.face.ui_logger = on_ui_state_update

    def speak_and_log(text, sequence=None, movement=None):
        t_start = time.time()
        log_reading_event(f"[Robot Speech START] text='{text}' | sequence={sequence} | movement={movement}")
        kwargs = {'viseme_data': {'text': text, 'file': None}}
        if sequence:
            kwargs['face_data'] = {'sequence': sequence}
        if movement:
            kwargs['movement_data'] = movement
        gigi.run_character(**kwargs)
        t_end = time.time()
        duration = t_end - t_start
        log_reading_event(f"[Robot Speech END] duration={duration:.3f}s for text='{text}'")

    try:
        log_reading_event("Starting Reading Fluency session...")
        log_reading_event(f"Parameters: show_karaoke={show_karaoke}, run_hello={run_hello}, run_selection={run_selection}, story_override={story_override}, run_comprehension={run_comprehension}")
        # Resolve username
        name = "Goren"
        
        if run_hello:
            # Start initial background vision system to recognize the user
            if gigi.vision:
                print("[Reading Fluency] Starting background vision system...")
                gigi.vision.run_vision()
                time.sleep(1.0)

            # Introduction
            speak_and_log('Hello! My name is Gigi. I am your reading assistant today.', movement='wave_hello')
            
            # Greet the person by name if recognized during introduction
            name = None
            if gigi.vision:
                print("[Reading Fluency] Checking recognized faces in the face cache...")
                all_faces = gigi.vision.face_cache.get_all_faces()
                print(f"[Reading Fluency] Face cache contains {len(all_faces)} active face(s).")
                for face_id, face_info in all_faces.items():
                    face_name = face_info.get('name', 'Unknown')
                    print(f"[Reading Fluency] Face ID {face_id} detected in cache: name='{face_name}', recognition_attempted={face_info.get('recognition_attempted', False)}")
                    is_face_pattern = re.match(r'^face_\d{4}$', face_name) is not None
                    is_unknown = (face_name == 'Unknown' or is_face_pattern or (face_name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
                    
                    if not is_unknown and face_name != 'Recognizing...':
                        name = face_name
                        print(f"[Reading Fluency] Selected recognized user: '{name}' (from Face ID {face_id})")
                        break
                if not name:
                    print("[Reading Fluency] No recognized registered user found in face cache.")
                        
            if name:
                speak_and_log(f'Hello {name}, it is great to see you again!', sequence='smile')
            else:
                # Fallback to asking name via speech and extracting it using robust LLM-based name extraction
                speak_and_log("What is your name? Tell me clearly!")
                if gigi.hearing:
                    gigi.hearing.texts = []
                    t_name_start = time.time()
                    gigi.listen_backchannel(timeout=8)
                    t_name_end = time.time()
                    heard_text = " ".join(gigi.hearing.texts).strip()
                    log_reading_event(f"[Name Recognition] Heard '{heard_text}' in {t_name_end - t_name_start:.3f}s")
                    if heard_text:
                        name = extract_name(heard_text, gigi=gigi)
                    else:
                        name = "Friend"
                else:
                    name = "Friend"
                    
                speak_and_log(f"It is wonderful to meet you, {name}!", sequence='smile')
            
        # Initialize logging session with the resolved user name
        gigi.log_user_name(name)
        log_reading_event(f"Resolved user name: {name}")

        # Resolve user directory and load/initialize the word bank
        if getattr(gigi, 'logger', None) and gigi.logger.session_dir:
            user_dir = os.path.dirname(gigi.logger.session_dir)
            word_bank_file = os.path.join(user_dir, "word_bank.json")
            log_reading_event(f"Word bank file path: '{word_bank_file}'")
            if os.path.exists(word_bank_file):
                try:
                    with open(word_bank_file, 'r', encoding='utf-8') as f:
                        word_bank = json.load(f)
                    log_reading_event(f"[Word Bank] Loaded word bank for '{name}' with {len(word_bank)} words.")
                except Exception as e:
                    log_reading_event(f"[Word Bank] Error loading word bank: {e}")
            else:
                log_reading_event("[Word Bank] Word bank file does not exist yet. Will create on save.")

        # Gigi asks the student to choose a story
        # Scan for available story options (*_passage.txt)
        passage_files = [f for f in os.listdir(assets_dir) if f.endswith('_passage.txt')]
        options = [f[:-12] for f in passage_files]
        options.sort()
        log_reading_event(f"Available stories found: {options}")
        
        # Fallback to defaults if no options found
        if not options:
            default_passage = os.path.join(assets_dir, 'space_passage.txt')
            with open(default_passage, 'w') as f:
                f.write("The quick brown fox jumps over the lazy dog. It was a sunny day and everyone was happy.")
            default_questions = os.path.join(assets_dir, 'space_questions.txt')
            with open(default_questions, 'w') as f:
                f.write("What animal jumped over the dog?\nHow was the weather that day?\n")
            options = ['space']

        # Join options into readable text
        if len(options) > 1:
            options_text = ", ".join(options[:-1]) + ", and " + options[-1]
        else:
            options_text = options[0]

        selected_option = None
        if run_selection:
            # Story selection via voice response
            speak_and_log(f"I have some stories for you to read. We can read about {options_text}. Which one would you like to choose?")
            
            if gigi.hearing:
                for attempt in range(3):
                    gigi.hearing.texts = []
                    t_sel_start = time.time()
                    gigi.listen_backchannel(timeout=8)
                    t_sel_end = time.time()
                    heard_text = " ".join(gigi.hearing.texts).strip().lower()
                    log_reading_event(f"[Story Selection] Attempt {attempt + 1}: Heard '{heard_text}' in {t_sel_end - t_sel_start:.3f}s")
                    
                    for opt in options:
                        base_opt = opt.rstrip('s')
                        if opt == "test" and ("text" in heard_text or "test" in heard_text):
                            selected_option = "test"
                            break
                        elif base_opt in heard_text:
                            selected_option = opt
                            break
                    
                    if selected_option:
                        log_reading_event(f"[Story Selection] Match found! Selected story: '{selected_option}'")
                        break
                        
                    if attempt < 2:
                        speak_and_log(f"Sorry, I didn't catch that. Which story would you like: {options_text}?")
                
                if not selected_option:
                    selected_option = options[0]
                    log_reading_event(f"[Story Selection] No valid response after 3 attempts. Defaulting to: '{selected_option}'")
            else:
                selected_option = options[0]
                log_reading_event(f"[Story Selection] Hearing module disabled. Defaulting to: '{selected_option}'")
        else:
            selected_option = story_override if story_override else options[0]
            log_reading_event(f"[Story Selection] Selection phase skipped. Using override/default: '{selected_option}'")

        # Dynamically load themed face images into self.guidance_images
        face_assets_dir = os.path.join(assets_dir, 'face')
        if gigi.face and os.path.exists(face_assets_dir):
            for file in os.listdir(face_assets_dir):
                if file.startswith(selected_option) and file.endswith(('.png', '.jpg', '.jpeg')):
                    img_name = file.split('.')[0]
                    img_path = os.path.join(face_assets_dir, file)
                    try:
                        img = Image.open(img_path)
                        if gigi.face.IMAGE_OPTION == "cv":
                            import numpy as np
                            import cv2
                            img_array = np.array(img.convert("RGB"))
                            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                        elif gigi.face.IMAGE_OPTION == "pygame":
                            import pygame
                            img_array = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                        gigi.face.guidance_images[img_name] = img_array
                        print(f"[Reading Fluency] Dynamically loaded guidance image '{img_name}'")
                    except Exception as e:
                        print(f"[Reading Fluency] Error loading guidance image {file}: {e}")

        # Show the name1.png image
        theme_img = None
        if gigi.face:
            theme_img = f"{selected_option}1"
            if theme_img in gigi.face.guidance_images:
                gigi.face.guidance = theme_img
            else:
                theme_img = None

        speak_and_log(f"Great selection! Let's read the {selected_option} story. Please read the passage in front of you slowly and clearly.")

        # Disable face tracking during reading to prevent user distraction
        gigi.disable_face_tracking = True

        # Keep initial vision thread active to prevent camera restart race conditions
        # if gigi.vision:
        #     gigi.vision.stop_vision()
        #     time.sleep(0.5)

        # Load selected passage and questions files
        passage_file = os.path.join(assets_dir, f"{selected_option}_passage.txt")
        questions_file = os.path.join(assets_dir, f"{selected_option}_questions.txt")

        with open(passage_file, 'r', encoding='utf-8') as f:
            passage_text = f.read().strip()
            print(f"\n--- Selected Theme: {selected_option} ---")
            print(f"--- Please read the following passage ---\n{passage_text}\n-----------------------------------------\n")
            
        gigi.log_variable("selected_story", selected_option)
        gigi.log_variable("passage_text", passage_text)
        
        # Split passage into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', passage_text) if s.strip()]
        log_reading_event(f"Passage text loaded: '{passage_text}'")
        log_reading_event(f"Parsed {len(sentences)} sentences: {sentences}")

        # Pre-warm audio for unique words in the background so "The word is {w}. Let's keep reading!" is instant
        def prewarm_passage_speech():
            if getattr(gigi, 'speech', None):
                words = set(re.findall(r'\b[a-zA-Z]+\b', passage_text))
                for w in words:
                    txt = f"The word is {w}. Let's keep reading!"
                    try:
                        gigi.speech.update_audio_objects(text=txt)
                    except Exception:
                        pass
        threading.Thread(target=prewarm_passage_speech, daemon=True).start()

        reading_mistakes = []
        gigi.log_variable("reading_mistakes", reading_mistakes)

        if gigi.hearing:
            # Dynamically set shorter buffer size for rapid real-time corrections
            if hasattr(gigi.hearing, 'audio_processor'):
                gigi.hearing.audio_processor.buffer_duration = 0.8
                log_reading_event("Set audio_processor buffer_duration to 0.8s")
            if hasattr(gigi.hearing, '_raw_buf_duration'):
                gigi.hearing._raw_buf_duration = 0.8
                log_reading_event("Set hearing _raw_buf_duration to 0.8s")

            NUMBER_MAP = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five',
                '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
                '11': 'eleven', '12': 'twelve', '13': 'thirteen', '14': 'fourteen', '15': 'fifteen',
                '16': 'sixteen', '17': 'seventeen', '18': 'eighteen', '19': 'nineteen', '20': 'twenty'
            }

            def normalize_word_str(w):
                clean = w.lower().strip().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                return NUMBER_MAP.get(clean, clean)

            def is_match(w1, w2):
                n1 = normalize_word_str(w1)
                n2 = normalize_word_str(w2)
                return n1 == n2 or SequenceMatcher(None, n1, n2).ratio() > 0.75

            fillers = {"um", "uh", "ah", "like", "so", "well", "and", "i", "mean"}

            def count_syllables(word):
                word = word.lower().strip()
                word = word.translate(str.maketrans('', '', string.punctuation))
                if not word:
                    return 0
                vowels = "aeiouy"
                count = 0
                if word[0] in vowels:
                    count += 1
                for index in range(1, len(word)):
                    if word[index] in vowels and word[index - 1] not in vowels:
                        count += 1
                if word.endswith("e"):
                    count -= 1
                if count == 0:
                    count += 1
                return count

            def is_prefix_or_syllable(heard, expected):
                """
                Check if 'heard' is a syllable, prefix, or partial sounding-out of 'expected'.
                Helps prevent interrupting users who read slowly or sound out words syllable-by-syllable.
                """
                h = normalize_word_str(heard)
                e = normalize_word_str(expected)
                if not h or not e:
                    return False
                if e.startswith(h):
                    return True
                if len(h) >= 2 and h in e:
                    return True
                pref = e[:len(h)]
                if len(pref) >= 3 and levenshtein_distance(h, pref) <= 1:
                    return True
                return False

            def get_reread_probability(word):
                if force_reread:
                    return 1.0
                clean = word.lower().translate(str.maketrans('', '', string.punctuation)).strip()
                length = len(clean)
                syllables = count_syllables(clean)
                if length <= 3 or syllables <= 1:
                    return 0.20
                elif length <= 5 or syllables == 2:
                    return 0.55
                else:
                    return 0.85

            # Clear guidance before starting reading to prevent screen overlap/distraction
            if gigi.face:
                gigi.face.guidance = None

            current_sentence_idx = 0
            while current_sentence_idx < len(sentences):
                active_sentence = sentences[current_sentence_idx]
                log_reading_event(f"--- Starting sentence {current_sentence_idx + 1}/{len(sentences)} ---")
                log_reading_event(f"Active sentence: '{active_sentence}'")
                preview_sentence = sentences[current_sentence_idx + 1] if current_sentence_idx + 1 < len(sentences) else ""
                
                active_words = active_sentence.split()
                preview_words = preview_sentence.split()
                
                # display_words will be active_words + ["\n"] + preview_words (if preview exists)
                display_words = active_words + ["\n"] + preview_words if preview_words else active_words
                
                active_states = ['unread'] * len(active_words)
                display_states = active_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else active_states
                
                passage_words = active_words # check_fluency runs against active_words
                word_states = active_states # check_fluency updates active_states
                current_word_idx = 0
                sentence_corrections_count = 0
                consecutive_silence_count = 0
                no_more_corrections_for_sentence = False
                
                while current_word_idx < len(active_words):
                    sentence_mistakes = []
                    listen_start_word_idx = current_word_idx
                    listen_start_word_states = list(word_states)
                    
                    # Enable pronunciation verification mode for the active sentence
                    gigi.hearing.pronunciation_mode = True
                    gigi.hearing.pronunciation_engine = 'citrinet'
                    # Set pronunciation grammar to the entire active sentence so Vosk can recognize any word in it
                    grammar_words = []
                    for w in active_words:
                        grammar_words.append(w)
                        norm = normalize_word_str(w)
                        if norm != w:
                            grammar_words.append(norm)
                    gigi.hearing.pronunciation_grammar = grammar_words

                    if show_karaoke and gigi.face:
                        local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                        gigi.face.update_reading_fluency(
                            active=True,
                            passage_words=display_words,
                            current_word_idx=current_word_idx,
                            word_states=local_display_states,
                            last_wrong_heard=None
                        )
                    
                    # Dynamic callback to detect mistakes vs off-topic talking in real time
                    def check_fluency(text):
                        nonlocal current_word_idx, word_states, sentence_mistakes
                        log_reading_event(f"[Fluid ASR Callback] Heard text snippet: '{text}'")
                        words_heard = [w.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation)) for w in text.split()]
                        words_heard = [w for w in words_heard if w]
                        if not words_heard:
                            return False
                            
                        local_word_states = list(listen_start_word_states)
                        local_sentence_mistakes = []
                        p_idx = listen_start_word_idx
                        
                        matched_count = 0
                        unmatched_count = 0
                        last_wrong = None
                        
                        # Define words we always auto-pass
                        AUTO_PASS_WORDS = {
                            "a", "an", "the", "and", "in", "on", "at", "to", "of", "for", "by", 
                            "is", "it", "its", "it's", "as", "or", "if", "up", "so", "but", "with"
                        }

                        h_idx = 0
                        while h_idx < len(words_heard):
                            h_word = words_heard[h_idx]
                            if h_word in fillers:
                                h_idx += 1
                                continue
                            
                            # Sliding window of 4 expected words starting at p_idx
                            window_size = 4
                            window = passage_words[p_idx : p_idx + window_size]
                            found_match = False
                            for offset, exp_word in enumerate(window):
                                expected_clean = exp_word.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                if is_match(h_word, expected_clean):
                                    # Handle skipped words before the matched word
                                    for j in range(p_idx, p_idx + offset):
                                        expected_skip = passage_words[j].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                        # If user starts reading from the second word of the sentence (j == 0, p_idx == 0, offset == 1), accept it!
                                        if (p_idx == 0 and j == 0) or expected_skip in AUTO_PASS_WORDS or word_bank.get(expected_skip) == "correct":
                                            local_word_states[j] = 'correct'
                                            word_bank[expected_skip] = "correct"
                                            save_word_bank()
                                        else:
                                            local_word_states[j] = 'wrong'
                                            local_sentence_mistakes.append({
                                                "expected": passage_words[j],
                                                "heard": "[skipped]",
                                                "index": j
                                            })
                                            word_bank[expected_skip] = "incorrect"
                                            save_word_bank()
                                            unmatched_count += 1
                                    # Mark matched word as correct
                                    local_word_states[p_idx + offset] = 'correct'
                                    word_bank[expected_clean] = "correct"
                                    save_word_bank()
                                    p_idx = p_idx + offset + 1
                                    matched_count += 1
                                    found_match = True
                                    break
                                    
                            if found_match:
                                h_idx += 1
                            else:
                                if p_idx < len(passage_words):
                                    expected_clean = passage_words[p_idx].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                    # If user starts from the second word and misses word 0 entirely, accept word 0!
                                    if p_idx == 0 and len(passage_words) > 1 and is_match(h_word, passage_words[1].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))):
                                        local_word_states[0] = 'correct'
                                        word_bank[expected_clean] = "correct"
                                        save_word_bank()
                                        local_word_states[1] = 'correct'
                                        p_clean_1 = passage_words[1].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                        word_bank[p_clean_1] = "correct"
                                        save_word_bank()
                                        p_idx = 2
                                        matched_count += 1
                                        h_idx += 1
                                        continue
                                    
                                    # Syllable / slow sounding out detection (e.g. "spa... space", "tel... telescope")
                                    if is_prefix_or_syllable(h_word, expected_clean):
                                        # Check if next heard word completes the full expected word
                                        if h_idx + 1 < len(words_heard) and is_match(words_heard[h_idx + 1], expected_clean):
                                            local_word_states[p_idx] = 'correct'
                                            word_bank[expected_clean] = "correct"
                                            save_word_bank()
                                            p_idx += 1
                                            matched_count += 1
                                            h_idx += 2
                                            continue
                                        elif h_idx == len(words_heard) - 1:
                                            # Partial syllable currently in progress. Keep highlight on p_idx, do not mark as mistake!
                                            log_reading_event(f"[Fluid ASR] In-progress syllable sounding out detected: '{h_word}' for expected '{expected_clean}'")
                                            h_idx += 1
                                            continue

                                    if expected_clean in AUTO_PASS_WORDS or word_bank.get(expected_clean) == "correct":
                                        # Check if the spoken word matches any subsequent word in the remaining window
                                        matches_subsequent = False
                                        for sub_word in window[1:]:
                                            sub_clean = sub_word.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                            if is_match(h_word, sub_clean):
                                                matches_subsequent = True
                                                break
                                        
                                        if matches_subsequent:
                                            local_word_states[p_idx] = 'correct'
                                            p_idx += 1
                                            continue
                                        else:
                                            local_word_states[p_idx] = 'correct'
                                            p_idx += 1
                                            h_idx += 1
                                            continue
                                    else:
                                        local_word_states[p_idx] = 'wrong'
                                        local_sentence_mistakes.append({
                                            "expected": passage_words[p_idx],
                                            "heard": h_word,
                                            "index": p_idx
                                        })
                                        last_wrong = {"heard": h_word, "expected": passage_words[p_idx]}
                                        word_bank[expected_clean] = "incorrect"
                                        save_word_bank()
                                        p_idx += 1
                                        unmatched_count += 1
                                else:
                                    unmatched_count += 1
                                h_idx += 1
                                
                        # Update nonlocal variables
                        word_states = local_word_states
                        sentence_mistakes = local_sentence_mistakes
                        current_word_idx = p_idx
                        
                        # Determine if finished or talking off-topic
                        is_talking = (matched_count == 0) or (unmatched_count >= 3 and matched_count < unmatched_count)
                        
                        log_reading_event(f"[Fluid Match Result] matched={matched_count}, unmatched={unmatched_count}, is_talking_offtopic={is_talking}")
                        log_reading_event(f"[Fluid Match Result] Word states: {word_states}")
                        if sentence_mistakes:
                            log_reading_event(f"[Fluid Match Result] Mistakes tracked: {sentence_mistakes}")
                        
                        if not is_talking:
                            if show_karaoke and gigi.face:
                                local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                                # Yellow highlight travels with the current active reading word index
                                highlight_idx = p_idx if p_idx < len(passage_words) else None
                                gigi.face.update_reading_fluency(
                                    active=True,
                                    passage_words=display_words,
                                    current_word_idx=highlight_idx,
                                    word_states=local_display_states,
                                    last_wrong_heard=None
                                )
                            # Continuous reading: only stop when the full sentence is finished!
                            should_stop = (p_idx >= len(passage_words))
                            log_reading_event(f"[Fluid Match Result] Sentence completed? {should_stop} (p_idx={p_idx}/{len(passage_words)})")
                            return should_stop
                        return False

                    t_listen_start = time.time()
                    log_reading_event(f"[Listening Turn START] Starting at word index {current_word_idx} ('{active_words[current_word_idx]}')")
                    if gigi.face:
                        gigi.face.set_reading_status("listening")

                    gigi.listen_fluid(timeout=30, n_transcripts=1, check_callback=check_fluency, run_speaker_recognition=False, show_camera_feed=False)
                    
                    t_listen_end = time.time()
                    listen_duration = t_listen_end - t_listen_start
                    if gigi.face:
                        gigi.face.set_reading_status("idle")

                    # Inspect results after fluid listening returns
                    words_read_this_turn = current_word_idx - listen_start_word_idx
                    log_reading_event(f"[Listening Turn FINISHED] duration={listen_duration:.3f}s | words_read_this_turn={words_read_this_turn} | mistakes={sentence_mistakes}")

                    # Silence management: Handle >5s pure silence (coax on 1st silence, advance on 2nd silence)
                    if words_read_this_turn == 0 and len(sentence_mistakes) == 0:
                        consecutive_silence_count += 1
                        log_reading_event(f"[Silence Manager] Pure silence detected. consecutive_silence_count={consecutive_silence_count}")
                        if consecutive_silence_count == 1:
                            coax_prompts = [
                                "Take your time! You can keep reading the words on the screen.",
                                "You're doing great! Try reading the next word out loud whenever you're ready.",
                                "Whenever you're ready, keep reading the sentence out loud!"
                            ]
                            coax_text = random.choice(coax_prompts)
                            log_reading_event(f"[Silence Manager] 1st silence. Coaxing user: '{coax_text}'")
                            speak_and_log(coax_text, sequence='smile')
                            continue
                        else:
                            advance_text = "OK, let's continue to the next sentence."
                            log_reading_event(f"[Silence Manager] 2nd consecutive silence. Advancing to next sentence: '{advance_text}'")
                            speak_and_log(advance_text, sequence='smile')
                            consecutive_silence_count = 0
                            current_sentence_idx += 1
                            break
                    else:
                        if words_read_this_turn > 0:
                            consecutive_silence_count = 0

                    if sentence_mistakes:
                        if no_more_corrections_for_sentence:
                            log_reading_event("[Reading Fluency] Ignoring mistakes on final fluency run for this sentence. Advancing past sentence.")
                            current_word_idx = len(active_words)
                            sentence_mistakes = []
                            continue
                            
                        sentence_corrections_count += 1
                        log_reading_event(f"[Reading Fluency] Sentence corrections count incremented to {sentence_corrections_count} (out of 3)")
                        if sentence_corrections_count >= 3:
                            log_reading_event(f"[Reading Fluency] 3rd correction reached for this sentence. Resetting to beginning with corrections disabled.")
                            speak_and_log("Let's read this sentence one more time from the beginning. Just read it all the way through!", sequence='smile')
                            time.sleep(0.5)
                            word_states = ['unread'] * len(active_words)
                            current_word_idx = 0
                            no_more_corrections_for_sentence = True
                            sentence_mistakes = []
                            continue

                        first_mistake = sentence_mistakes[0]
                        selected_word = first_mistake["expected"]
                        selected_idx = first_mistake["index"]
                        expected_clean = selected_word.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                        
                        reread_prob = get_reread_probability(selected_word)
                        if random.random() >= reread_prob:
                            log_reading_event(f"[Fluency Decision] Skipping re-read for '{selected_word}' (len={len(expected_clean)}, syllables={count_syllables(expected_clean)}, prob={reread_prob:.2f}). Auto-passing to maintain fluency.")
                            word_states[selected_idx] = 'correct'
                            current_word_idx = selected_idx + 1
                            sentence_mistakes = []
                            continue

                        log_reading_event(f"[Word Correct] Immediate correction triggered for: '{selected_word}' at index {selected_idx}")
                        
                        # Log mistake details
                        reading_mistakes.append({
                            "sentence": active_sentence,
                            "expected": selected_word,
                            "heard": first_mistake["heard"]
                        })
                        gigi.log_variable("reading_mistakes", reading_mistakes)
                        
                        # Light up the selected word (mark it wrong, others correct/unread)
                        temp_states = list(word_states)
                        temp_states[selected_idx] = 'wrong'
                        temp_display_states = temp_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else temp_states
                        
                        if show_karaoke and gigi.face:
                            gigi.face.update_reading_fluency(
                                active=True,
                                passage_words=display_words,
                                current_word_idx=selected_idx,
                                word_states=temp_display_states,
                                last_wrong_heard=None
                            )
                        
                        # Switch to pronunciation verification mode for this specific word
                        gigi.hearing.pronunciation_mode = True
                        gigi.hearing.pronunciation_engine = 'citrinet'
                        gigi.hearing.pronunciation_grammar = [selected_word]
                        
                        review_prompts = [
                            "Can you try saying the highlighted word one more time?",
                            "Let's try that highlighted word again! Can you read it for me?",
                            "How do we say this highlighted word? Can you read it again?",
                            "I want to make sure I heard you correctly. Could you say that word again?",
                            "Let's practice this highlighted one. Can you say it one more time?",
                            "How does the highlighted word sound? Can you read it again?",
                            "Let's take another look at the highlighted word. Can you say it?",
                            "Can you give the highlighted word another try?",
                            "I missed the highlighted word. Could you read it again?",
                            "Let's try to fix the highlighted word. Can you say it one more time?",
                            "Could you say the highlighted word again for me?",
                            "Let's give the highlighted word another go. Can you read it?",
                            "Let's try pronouncing the highlighted word again. What does it say?",
                            "Can we try the highlighted word one more time? Say it.",
                            "I'd love to hear you say the highlighted word again. Can you try?",
                            "Let's double-check the highlighted word. Can you read it one more time?",
                            "Let's practice saying the highlighted word. Can you try it?",
                            "Can you try reading the highlighted word again for me?",
                            "Let's give the highlighted word another shot. Can you say it?",
                            "Could you try to read the highlighted word one more time?"
                        ]
                        if word_bank.get(expected_clean) == "incorrect":
                            reinforcement_prompts = [
                                "I know this highlighted word can be tricky, but you are doing great! Let's try saying it one more time.",
                                "You have practiced this highlighted word before, and you are getting so close! Let's try it again.",
                                "This is one of our special challenge words. I believe in you! Can you read it for me?",
                                "Don't worry, we can do hard things! Let's try pronouncing the highlighted word together one more time."
                            ]
                            prompt = random.choice(reinforcement_prompts)
                            log_reading_event(f"[Pronunciation Review] Word '{expected_clean}' already marked incorrect in word bank. Selecting positive reinforcement prompt: '{prompt}'")
                        else:
                            prompt = random.choice(review_prompts)
                            log_reading_event(f"[Pronunciation Review] Selecting review prompt: '{prompt}'")
                            
                        speak_and_log(prompt, movement='open_close_arms')
                        
                        success = False
                        if gigi.hearing:
                            gigi.hearing.texts = []
                            # Reduce silence duration to 0.5s for single word correction
                            old_silence = gigi.hearing.silence_duration
                            gigi.hearing.silence_duration = 0.5
                            log_reading_event("Pronunciation check: temporarily reduced silence_duration to 0.5s")
                            
                            t_pron_start = time.time()
                            if gigi.face:
                                gigi.face.set_reading_status("listening")

                            gigi.listen_backchannel(timeout=8, show_camera_feed=False)
                            
                            t_pron_end = time.time()
                            pron_duration = t_pron_end - t_pron_start
                            if gigi.face:
                                gigi.face.set_reading_status("idle")

                            gigi.hearing.silence_duration = old_silence
                            log_reading_event(f"Pronunciation check listening completed in {pron_duration:.3f}s. Restored original silence_duration.")
                            
                            corrected_text = " ".join(gigi.hearing.texts).strip()
                            log_reading_event(f"[Pronunciation ASR] Heard text: '{corrected_text}'")
                            corrected_words = [w.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation)) for w in corrected_text.split()]
                            corrected_words = [w for w in corrected_words if w]
                            
                            expected_clean = selected_word.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                            for cw in corrected_words:
                                match_check = is_match(cw, expected_clean)
                                log_reading_event(f"[Pronunciation Check] Comparing word '{cw}' against expected '{expected_clean}': match={match_check}")
                                if match_check:
                                    success = True
                                    break
                                    
                            # Incorporate SOTA Citrinet-GOP scoring from NPU/Numpy
                            raw_audio = gigi.hearing.get_full_audio()
                            if raw_audio is not None and getattr(gigi.hearing, 'citrinet_gop', None) is not None:
                                gop_score = gigi.hearing.citrinet_gop.calculate_gop(raw_audio, expected_clean, transcription=corrected_text)
                                log_reading_event(f"[Citrinet GOP] Calculated score: {gop_score:.2f} for word '{expected_clean}' (Success threshold >= 50.0)")
                                if gop_score >= 50.0:
                                    success = True
                                    
                        log_reading_event(f"[Pronunciation Outcome] Correction succeeded? {success}")
                        if success:
                            # Corrected! Reset the entire sentence so they read it again
                            log_reading_event(f"[Pronunciation Outcome] Resetting sentence index to 0. Updating word bank mapping '{expected_clean}' -> 'correct'")
                            word_states = ['unread'] * len(active_words)
                            current_word_idx = 0
                            
                            # If corrected on second attempt, change mark from "incorrect" to "correct"
                            word_bank[expected_clean] = "correct"
                            save_word_bank()
                            
                            affirmations = [
                                "You got it! Great job!",
                                "Perfect! You solved it!",
                                "Awesome job! That is correct!",
                                "Yes, that's it! Wonderful!"
                            ]
                            affirmation = random.choice(affirmations)
                            speak_and_log(f"{affirmation} Now, please read the sentence again from the beginning.", sequence='smile')
                            time.sleep(0.5)
                        else:
                            # Not corrected, tell them the word and move past
                            log_reading_event(f"[Pronunciation Outcome] Correction failed. Moving past word. Updating word bank mapping '{expected_clean}' -> 'incorrect' (if not already 'correct')")
                            word_states[selected_idx] = 'correct'
                            current_word_idx = selected_idx + 1
                            if word_bank.get(expected_clean) != "correct":
                                word_bank[expected_clean] = "incorrect"
                                save_word_bank()
                            
                            if show_karaoke and gigi.face:
                                local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                                gigi.face.update_reading_fluency(
                                    active=True,
                                    passage_words=display_words,
                                    current_word_idx=current_word_idx,
                                    word_states=local_display_states,
                                    last_wrong_heard=None
                                )
                            
                            speak_and_log(f"The word is {selected_word}. Let's keep reading!")
                            time.sleep(0.5)
                            
                        # Disable pronunciation mode after review
                        gigi.hearing.pronunciation_mode = False
                        gigi.hearing.pronunciation_engine = 'vosk'
                    else:
                        if current_word_idx < len(active_words) and not all(s == 'correct' for s in word_states):
                            # Incomplete reading: student paused or stopped before finishing the sentence
                            log_reading_event(f"[Sentence Loop] Partial reading detected ({current_word_idx}/{len(active_words)} words). Prompting to continue.")
                            speak_and_log("You're doing great! Let's keep reading the rest of the sentence.", sequence='smile')
                            time.sleep(0.5)
                            continue
                        else:
                            # Completed sentence with all words matched
                            log_reading_event("[Sentence Loop] Finished reading sentence with all words matched.")
                            current_word_idx = len(active_words)
                
                # Make sure all words are marked correct when moving to the next sentence
                for j in range(len(word_states)):
                    word_states[j] = 'correct'
                
                if show_karaoke and gigi.face:
                    local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                    gigi.face.update_reading_fluency(
                        active=True,
                        passage_words=display_words,
                        current_word_idx=None,
                        word_states=local_display_states,
                        last_wrong_heard=None
                    )

                current_sentence_idx += 1
                
                if current_sentence_idx < len(sentences):
                    # Preview the next sentence immediately on screen
                    next_sentence_text = sentences[current_sentence_idx]
                    next_active_words = [w for w in next_sentence_text.split() if w]
                    next_preview_words = [w for w in sentences[current_sentence_idx + 1].split() if w] if current_sentence_idx + 1 < len(sentences) else []
                    next_display_words = next_active_words + ["\n"] + next_preview_words if next_preview_words else next_active_words
                    next_display_states = ['unread'] * len(next_active_words) + ['unread'] + ['unread'] * len(next_preview_words) if next_preview_words else ['unread'] * len(next_active_words)
                    
                    if show_karaoke and gigi.face:
                        gigi.face.update_reading_fluency(
                            active=True,
                            passage_words=next_display_words,
                            current_word_idx=0,
                            word_states=next_display_states,
                            last_wrong_heard=None
                        )
                    
                    speak_and_log("Great!", sequence='smile')
                    time.sleep(0.5)

            if show_karaoke and gigi.face:
                gigi.face.update_reading_fluency(active=False)
                theme_img = f"{selected_option}2"
                if theme_img in gigi.face.guidance_images:
                    gigi.face.guidance = theme_img
                else:
                    gigi.face.guidance = None
            
            gigi.hearing.pronunciation_mode = False
            gigi.hearing.pronunciation_engine = 'vosk'
        else:
            print("Hearing module is not enabled. Simulating reading time...")
            if show_karaoke and gigi.face:
                theme_img = f"{selected_option}2"
                if theme_img in gigi.face.guidance_images:
                    gigi.face.guidance = theme_img
            time.sleep(5)
            
        # Comprehension questions check
        if run_comprehension:
            log_reading_event("Initiating comprehension check...")
            speak_and_log('Great job reading the story! Now, let us answer some questions.')
            
            discussion_responses = []
            if os.path.exists(questions_file):
                with open(questions_file, 'r', encoding='utf-8') as f:
                    questions = [line.strip() for line in f.readlines() if line.strip()]
            else:
                questions = ["Did you enjoy reading the story?"]
                
            positive_feedbacks = [
                "I see! Great.",
                "Got it! Awesome.",
                "Perfect, thank you for sharing!",
                "Alright, good job!",
                "Excellent response!",
                "Thanks! That makes sense."
            ]
            
            for q in questions:
                log_reading_event(f"Gigi asks question: '{q}'")
                speak_and_log(q)
                
                if gigi.hearing:
                    log_reading_event("Listening for answer...")
                    if gigi.face:
                        gigi.face.set_reading_status("listening")
                    
                    t_ans_start = time.time()
                    gigi.hearing.texts = []
                    gigi.listen_backchannel(timeout=10, show_camera_feed=False)
                    t_ans_end = time.time()
                    ans_duration = t_ans_end - t_ans_start
                    
                    if gigi.face:
                        gigi.face.set_reading_status("idle")
                    
                    answer = " ".join(gigi.hearing.texts).strip()
                    log_reading_event(f"Student answered in {ans_duration:.3f}s: '{answer}'")
                    discussion_responses.append({"question": q, "answer": answer})
                    gigi.log_variable("discussion", discussion_responses)
                    
                    feedback = random.choice(positive_feedbacks)
                    speak_and_log(feedback, sequence='smile')
                else:
                    discussion_responses.append({"question": q, "answer": None})
                    gigi.log_variable("discussion", discussion_responses)
                    time.sleep(3)
                    
            # Goodbye / Final activity feedback
            log_reading_event("Concluding session. Gigi waves goodbye.")
            speak_and_log('We are all done for today. You did wonderful with the reading and questions! Goodbye for now!', movement='wave_hello')
        
        # Return to home position
        if gigi.movement:
            gigi.movement.home_position()
            log_reading_event("Returned robot movement to home position.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Reading Fluency] Error: {e}")
    finally:
        # Clean up and stop threads
        gigi.disable_face_tracking = False
        if gigi.face:
            gigi.face.guidance = None
        tracker.stop()
        gigi.stop_character()
        print("Reading Fluency Demo finished.")

def readingFluencyDemo():
    play_reading_fluency()

if __name__ == "__main__":
    play_reading_fluency()

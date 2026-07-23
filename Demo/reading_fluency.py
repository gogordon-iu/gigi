import os
import sys
import time
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

def play_reading_fluency(show_karaoke=True):
    print("====================================================")
    print("             GIGI Reading Fluency Demo              ")
    print("====================================================")
    
    # Initialize character with wakeup=True to show face and move to home position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="ReadingFluency")
    
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

    try:
        # Start initial background vision system to recognize the user
        if gigi.vision:
            print("[Reading Fluency] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)

        # Introduction
        gigi.run_character(
            viseme_data={'text': 'Hello! My name is Gigi. I am your reading assistant today.', 'file': None},
            movement_data='wave_hello'
        )
        
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
            gigi.run_character(
                viseme_data={'text': f'Hello {name}, it is great to see you again!', 'file': None},
                face_data={'sequence': 'smile'}
            )
        else:
            # Fallback to asking name via speech and extracting it using robust LLM-based name extraction
            gigi.run_character(
                viseme_data={'text': "What is your name? Tell me clearly!", 'file': None}
            )
            if gigi.hearing:
                gigi.hearing.texts = []
                gigi.listen_backchannel(timeout=8)
                heard_text = " ".join(gigi.hearing.texts).strip()
                print(f"[Reading Fluency] Raw hearing transcript: '{heard_text}'")
                if heard_text:
                    name = extract_name(heard_text, gigi=gigi)
                else:
                    name = "Friend"
            else:
                name = "Friend"
                
            gigi.run_character(
                viseme_data={'text': f"It is wonderful to meet you, {name}!", 'file': None},
                face_data={'sequence': 'smile'}
            )
            
        # Initialize logging session with the resolved user name
        gigi.log_user_name(name)

        # Gigi asks the student to choose a story
        # Scan for available story options (*_passage.txt)
        passage_files = [f for f in os.listdir(assets_dir) if f.endswith('_passage.txt')]
        options = [f[:-12] for f in passage_files]
        options.sort()
        
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

        # Story selection via voice response
        selected_option = None
        gigi.run_character(
            viseme_data={'text': f"I have some stories for you to read. We can read about {options_text}. Which one would you like to choose?", 'file': None}
        )
        
        if gigi.hearing:
            for attempt in range(3):
                gigi.hearing.texts = []
                gigi.listen_backchannel(timeout=8)
                heard_text = " ".join(gigi.hearing.texts).strip().lower()
                print(f"[Reading Fluency] Story selection attempt {attempt + 1}: '{heard_text}'")
                
                for opt in options:
                    base_opt = opt.rstrip('s')
                    if opt == "test" and ("text" in heard_text or "test" in heard_text):
                        selected_option = "test"
                        break
                    elif base_opt in heard_text:
                        selected_option = opt
                        break
                
                if selected_option:
                    break
                    
                if attempt < 2:
                    gigi.run_character(
                        viseme_data={'text': f"Sorry, I didn't catch that. Which story would you like: {options_text}?", 'file': None}
                    )
            
            if not selected_option:
                selected_option = options[0]
                print(f"[Reading Fluency] No valid response, defaulting to '{selected_option}'")
        else:
            selected_option = options[0]
            print(f"[Reading Fluency] Hearing disabled, defaulting to '{selected_option}'")

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

        gigi.run_character(
            viseme_data={'text': f"Great selection! Let's read the {selected_option} story. Please read the passage in front of you slowly and clearly.", 'file': None},
            face_data={'guidance': theme_img} if theme_img else None
        )

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

        reading_mistakes = []
        gigi.log_variable("reading_mistakes", reading_mistakes)

        if gigi.hearing:
            # Dynamically set shorter buffer size for rapid real-time corrections
            if hasattr(gigi.hearing, 'audio_processor'):
                gigi.hearing.audio_processor.buffer_duration = 0.8
            if hasattr(gigi.hearing, '_raw_buf_duration'):
                gigi.hearing._raw_buf_duration = 0.8

            def is_match(w1, w2):
                return w1 == w2 or SequenceMatcher(None, w1, w2).ratio() > 0.75

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

            # Clear guidance before starting reading to prevent screen overlap/distraction
            if gigi.face:
                gigi.face.guidance = None

            current_sentence_idx = 0
            while current_sentence_idx < len(sentences):
                active_sentence = sentences[current_sentence_idx]
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
                
                while current_word_idx < len(active_words):
                    sentence_mistakes = []
                    
                    # Enable pronunciation verification mode for the active sentence
                    gigi.hearing.pronunciation_mode = True
                    gigi.hearing.pronunciation_engine = 'citrinet'
                    # Set pronunciation grammar to the entire active sentence so Vosk can recognize any word in it
                    gigi.hearing.pronunciation_grammar = active_words

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
                        words_heard = [w.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation)) for w in text.split()]
                        words_heard = [w for w in words_heard if w]
                        if not words_heard:
                            return False
                            
                        local_word_states = list(word_states)
                        local_sentence_mistakes = []
                        p_idx = current_word_idx
                        
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
                                    # Mark skipped words as wrong, except small words in AUTO_PASS_WORDS
                                    for j in range(p_idx, p_idx + offset):
                                        expected_skip = passage_words[j].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                        if expected_skip in AUTO_PASS_WORDS:
                                            local_word_states[j] = 'correct'
                                        else:
                                            local_word_states[j] = 'wrong'
                                            local_sentence_mistakes.append({
                                                "expected": passage_words[j],
                                                "heard": "[skipped]",
                                                "index": j
                                            })
                                    # Mark matched word as correct
                                    local_word_states[p_idx + offset] = 'correct'
                                    p_idx = p_idx + offset + 1
                                    matched_count += 1
                                    found_match = True
                                    break
                                    
                            if found_match:
                                h_idx += 1
                            else:
                                # If the current expected word is in AUTO_PASS_WORDS, we auto-pass it
                                if p_idx < len(passage_words):
                                    expected_clean = passage_words[p_idx].lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                                    if expected_clean in AUTO_PASS_WORDS:
                                        local_word_states[p_idx] = 'correct'
                                        p_idx += 1
                                        # Do not increment h_idx, so we try to match h_word again!
                                        continue
                                    else:
                                        local_word_states[p_idx] = 'wrong'
                                        local_sentence_mistakes.append({
                                            "expected": passage_words[p_idx],
                                            "heard": h_word,
                                            "index": p_idx
                                        })
                                        last_wrong = {"heard": h_word, "expected": passage_words[p_idx]}
                                        p_idx += 1
                                unmatched_count += 1
                                h_idx += 1
                                
                        # Update nonlocal variables
                        word_states = local_word_states
                        sentence_mistakes = local_sentence_mistakes
                        
                        # Determine if finished or talking off-topic
                        is_talking = (matched_count == 0) or (unmatched_count >= 3 and matched_count < unmatched_count)
                        
                        if not is_talking:
                            if show_karaoke and gigi.face:
                                local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                                gigi.face.update_reading_fluency(
                                    active=True,
                                    passage_words=display_words,
                                    current_word_idx=p_idx,
                                    word_states=local_display_states,
                                    last_wrong_heard=last_wrong
                                )
                            # Stop immediately if there's any mistake OR if we finished the sentence
                            return unmatched_count >= 1 or p_idx >= len(passage_words)
                        return False

                    print(f"Listening to sentence starting at word index {current_word_idx}...")
                    gigi.listen_fluid(timeout=30, n_transcripts=1, check_callback=check_fluency, run_speaker_recognition=False, show_camera_feed=False)
                    
                    # Inspect results after fluid listening returns
                    if sentence_mistakes:
                        first_mistake = sentence_mistakes[0]
                        selected_word = first_mistake["expected"]
                        selected_idx = first_mistake["index"]
                        
                        print(f"[Word Correct] Immediate correction for: '{selected_word}' at index {selected_idx}")
                        
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
                        prompt = random.choice(review_prompts)
                        gigi.run_character(
                            viseme_data={'text': prompt, 'file': None},
                            movement_data='open_close_arms'
                        )
                        
                        success = False
                        if gigi.hearing:
                            gigi.hearing.texts = []
                            gigi.listen_backchannel(timeout=8, show_camera_feed=False)
                            
                            corrected_text = " ".join(gigi.hearing.texts).strip()
                            corrected_words = [w.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation)) for w in corrected_text.split()]
                            corrected_words = [w for w in corrected_words if w]
                            
                            expected_clean = selected_word.lower().replace("’", "'").translate(str.maketrans('', '', string.punctuation))
                            for cw in corrected_words:
                                if is_match(cw, expected_clean):
                                    success = True
                                    break
                                    
                            # Incorporate SOTA Citrinet-GOP scoring from NPU/Numpy
                            raw_audio = gigi.hearing.get_full_audio()
                            if raw_audio is not None and getattr(gigi.hearing, 'citrinet_gop', None) is not None:
                                gop_score = gigi.hearing.citrinet_gop.calculate_gop(raw_audio, expected_clean, transcription=corrected_text)
                                print(f"[Citrinet GOP] Word: '{expected_clean}' -> GOP Score: {gop_score:.2f}")
                                if gop_score >= 50.0:
                                    success = True
                                    
                        if success:
                            # Corrected! Reset the entire sentence so they read it again
                            word_states = ['unread'] * len(active_words)
                            current_word_idx = 0
                            
                            affirmations = [
                                "You got it! Great job!",
                                "Perfect! You solved it!",
                                "Awesome job! That is correct!",
                                "Yes, that's it! Wonderful!"
                            ]
                            affirmation = random.choice(affirmations)
                            gigi.run_character(
                                viseme_data={'text': f"{affirmation} Now, please read the sentence again from the beginning.", 'file': None},
                                face_data={'sequence': 'smile'}
                            )
                            time.sleep(0.5)
                        else:
                            # Not corrected, tell them the word and move past
                            word_states[selected_idx] = 'correct'
                            current_word_idx = selected_idx + 1
                            
                            if show_karaoke and gigi.face:
                                local_display_states = word_states + ['unread'] + ['unread'] * len(preview_words) if preview_words else word_states
                                gigi.face.update_reading_fluency(
                                    active=True,
                                    passage_words=display_words,
                                    current_word_idx=current_word_idx,
                                    word_states=local_display_states,
                                    last_wrong_heard=None
                                )
                            
                            gigi.run_character(
                                viseme_data={'text': f"The word is {selected_word}. Let's keep reading!", 'file': None}
                            )
                            time.sleep(0.5)
                            
                        # Disable pronunciation mode after review
                        gigi.hearing.pronunciation_mode = False
                        gigi.hearing.pronunciation_engine = 'vosk'
                    else:
                        # Completed sentence without mistakes
                        current_word_idx = len(active_words)
                
                # Make sure all words are marked correct when moving to the next sentence
                for j in range(len(word_states)):
                    word_states[j] = 'correct'
                
                current_sentence_idx += 1
                
                if current_sentence_idx < len(sentences):
                    gigi.run_character(
                        viseme_data={'text': "Great!", 'file': None},
                        face_data={'sequence': 'smile'}
                    )
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
        print("Initiating comprehension check...")
        gigi.run_character(
            viseme_data={'text': 'Great job reading the story! Now, let us answer some questions.', 'file': None}
        )
        
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
            print(f"Gigi asks: {q}")
            gigi.run_character(
                viseme_data={'text': q, 'file': None}
            )
            
            if gigi.hearing:
                print("Listening for answer...")
                gigi.face.set_reading_status("listening")
                
                gigi.hearing.texts = []
                gigi.listen_backchannel(timeout=10, show_camera_feed=False)
                
                gigi.face.set_reading_status("idle")
                
                answer = " ".join(gigi.hearing.texts).strip()
                print(f"Student answered: {answer}")
                discussion_responses.append({"question": q, "answer": answer})
                gigi.log_variable("discussion", discussion_responses)
                
                feedback = random.choice(positive_feedbacks)
                gigi.run_character(
                    viseme_data={'text': feedback, 'file': None},
                    face_data={'sequence': 'smile'}
                )
            else:
                discussion_responses.append({"question": q, "answer": None})
                gigi.log_variable("discussion", discussion_responses)
                time.sleep(3)
                
        # Goodbye / Final activity feedback
        print("Concluding demo...")
        gigi.run_character(
            viseme_data={'text': 'We are all done for today. You did wonderful with the reading and questions! Goodbye for now!', 'file': None},
            movement_data='wave_hello'
        )
        
        # Return to home position
        if gigi.movement:
            gigi.movement.home_position()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Reading Fluency] Error: {e}")
    finally:
        # Clean up and stop threads
        if gigi.face:
            gigi.face.guidance = None
        tracker.stop()
        gigi.stop_character()
        print("Reading Fluency Demo finished.")

def readingFluencyDemo():
    play_reading_fluency()

if __name__ == "__main__":
    play_reading_fluency()

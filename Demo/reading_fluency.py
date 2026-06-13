import os
import sys
import time
import string
import re
import random
import threading
from difflib import SequenceMatcher

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

        # Gigi asks the student to read
        gigi.run_character(
            viseme_data={'text': 'Please read the passage in front of you slowly and clearly.', 'file': None}
        )
        
        # Stop initial vision thread so background tracker can manage its lifecycle cleanly
        if gigi.vision:
            gigi.vision.stop_vision()
            time.sleep(0.5)

        # Read the passage text
        with open(passage_file, 'r') as f:
            passage_text = f.read().strip()
            print(f"\n--- Please read the following passage ---\n{passage_text}\n-----------------------------------------\n")
            
        # Log passage text and initialize mistakes tracking
        gigi.log_variable("passage_text", passage_text)
        passage_words = passage_text.split()
        current_word_idx = 0
        reading_mistakes = []
        gigi.log_variable("reading_mistakes", reading_mistakes)
        
        word_states = ['unread'] * len(passage_words)
        if show_karaoke and gigi.face:
            gigi.face.update_reading_fluency(
                active=True,
                passage_words=passage_words,
                current_word_idx=current_word_idx,
                word_states=word_states,
                last_wrong_heard=None
            )
        
        if gigi.hearing:
            # Dynamically set shorter buffer size for rapid real-time corrections
            if hasattr(gigi.hearing, 'audio_processor'):
                gigi.hearing.audio_processor.buffer_duration = 0.8
            if hasattr(gigi.hearing, '_raw_buf_duration'):
                gigi.hearing._raw_buf_duration = 0.8

            def is_match(w1, w2):
                return w1 == w2 or SequenceMatcher(None, w1, w2).ratio() > 0.75

            fillers = {"um", "uh", "ah", "like", "so", "well", "and", "i", "mean"}

            # Dynamic callback to detect mistakes vs off-topic talking in real time
            def check_fluency(text):
                nonlocal current_word_idx, word_states
                words_heard = [w.translate(str.maketrans('', '', string.punctuation)).lower() for w in text.split()]
                words_heard = [w for w in words_heard if w]
                if not words_heard:
                    return False
                    
                matched_count = 0
                unmatched_count = 0
                temp_idx = current_word_idx
                
                # Check real-time progress using a local copy of states
                local_word_states = list(word_states)
                last_wrong = None
                
                for i, h_word in enumerate(words_heard):
                    if h_word in fillers:
                        continue
                    window_size = 3
                    found_match = False
                    for offset in range(window_size):
                        check_idx = temp_idx + offset
                        if check_idx < len(passage_words):
                            expected = passage_words[check_idx].translate(str.maketrans('', '', string.punctuation)).lower()
                            if is_match(h_word, expected):
                                for j in range(temp_idx, check_idx + 1):
                                    local_word_states[j] = 'correct'
                                temp_idx = check_idx + 1
                                matched_count += 1
                                found_match = True
                                break
                    if not found_match:
                        if temp_idx < len(passage_words):
                            expected = passage_words[temp_idx].translate(str.maketrans('', '', string.punctuation)).lower()
                            local_word_states[temp_idx] = 'wrong'
                            last_wrong = {"heard": h_word, "expected": expected}
                        if i < len(words_heard) - 1:
                            unmatched_count += 1
                            
                is_talking = (matched_count == 0) or (unmatched_count >= 3 and matched_count < unmatched_count)
                
                if not is_talking:
                    if show_karaoke and gigi.face:
                        gigi.face.update_reading_fluency(
                            active=True,
                            current_word_idx=temp_idx,
                            word_states=local_word_states,
                            last_wrong_heard=last_wrong
                        )
                    return unmatched_count >= 1 or temp_idx >= len(passage_words)
                    
                return False

            # Start active face tracking while student is reading
            tracker.start()

            while current_word_idx < len(passage_words):
                gigi.hearing.texts = []
                print(f"Listening for words starting from index {current_word_idx}...")
                gigi.listen_fluid(timeout=15, n_transcripts=1, check_callback=check_fluency)
                
                if not gigi.hearing.texts:
                    print("No speech detected. Pausing...")
                    continue
                    
                last_text = gigi.hearing.texts[-1]
                words_heard = [w.translate(str.maketrans('', '', string.punctuation)).lower() for w in last_text.split()]
                words_heard = [w for w in words_heard if w]
                
                # Detect restart from the beginning of the passage
                if current_word_idx > 0 and len(words_heard) >= 2 and len(passage_words) >= 2:
                    p0 = passage_words[0].translate(str.maketrans('', '', string.punctuation)).lower()
                    p1 = passage_words[1].translate(str.maketrans('', '', string.punctuation)).lower()
                    if is_match(words_heard[0], p0) and is_match(words_heard[1], p1):
                        print("\n[Restart detected. Resetting to the beginning of the passage.]")
                        current_word_idx = 0
                        word_states = ['unread'] * len(passage_words)
                        if show_karaoke and gigi.face:
                            gigi.face.update_reading_fluency(
                                active=True,
                                current_word_idx=current_word_idx,
                                word_states=word_states,
                                last_wrong_heard=None
                            )
                
                matched_idx = current_word_idx
                matched_count = 0
                unmatched_count = 0
                first_unmatched_word = None
                first_unmatched_expected = None
                
                for h_word in words_heard:
                    if not h_word: continue
                    if h_word in fillers: continue
                    
                    window_size = 3
                    found_match = False
                    for offset in range(window_size):
                        check_idx = matched_idx + offset
                        if check_idx < len(passage_words):
                            expected = passage_words[check_idx].translate(str.maketrans('', '', string.punctuation)).lower()
                            if is_match(h_word, expected):
                                for j in range(matched_idx, check_idx + 1):
                                    word_states[j] = 'correct'
                                matched_idx = check_idx + 1
                                matched_count += 1
                                found_match = True
                                break
                                
                    if not found_match:
                        unmatched_count += 1
                        if first_unmatched_word is None and matched_idx < len(passage_words):
                            first_unmatched_word = h_word
                            first_unmatched_expected = passage_words[matched_idx].translate(str.maketrans('', '', string.punctuation)).lower()
                            
                is_talking = (matched_count == 0) or (unmatched_count >= 3 and matched_count < unmatched_count)
                
                if is_talking:
                    print(f"[Student is talking / off-topic: '{last_text}'] -> Ignoring.")
                    continue
                    
                if unmatched_count >= 1 and first_unmatched_expected is not None:
                    print(f"Mistake found: heard '{first_unmatched_word}', expected '{first_unmatched_expected}'")
                    # Stop tracking briefly to animate correction response cleanly
                    tracker.stop()
                    
                    # Log the mistake details and update display
                    word_states[matched_idx] = 'wrong'
                    last_wrong = {"heard": first_unmatched_word, "expected": first_unmatched_expected}
                    if show_karaoke and gigi.face:
                        gigi.face.update_reading_fluency(
                            active=True,
                            current_word_idx=matched_idx,
                            word_states=word_states,
                            last_wrong_heard=last_wrong
                        )
                    
                    mistake_info = {
                        "word_index": matched_idx,
                        "expected": first_unmatched_expected,
                        "heard": first_unmatched_word,
                        "timestamp": time.strftime("%H:%M:%S")
                    }
                    reading_mistakes.append(mistake_info)
                    gigi.log_variable("reading_mistakes", reading_mistakes)
                    
                    # Choose a random hint for word attack skills
                    hints = [
                        "Do you see any chunks you know?",
                        "Can you flip the vowel?",
                        "Does that sound right?",
                        "Does it make sense?"
                    ]
                    hint = random.choice(hints)
                    gigi.run_character(
                        viseme_data={'text': f"Let's try that word again. {hint}", 'file': None}
                    )
                    
                    # Listen for the child trying to correct the word
                    success = False
                    if gigi.hearing:
                        tracker.start()
                        gigi.hearing.texts = []
                        gigi.listen_backchannel(timeout=8)
                        tracker.stop()
                        
                        corrected_text = " ".join(gigi.hearing.texts).strip()
                        corrected_words = [w.translate(str.maketrans('', '', string.punctuation)).lower() for w in corrected_text.split()]
                        corrected_words = [w for w in corrected_words if w]
                        
                        # Check if they said the correct word
                        for cw in corrected_words:
                            if is_match(cw, first_unmatched_expected):
                                success = True
                                break
                                
                    if success:
                        # Affirmation for solving the word + read sentence again
                        word_states[matched_idx] = 'correct'
                        
                        affirmations = [
                            "You got it! Great job!",
                            "Perfect! You solved it!",
                            "Awesome job! That is correct!",
                            "Yes, that's it! Wonderful!"
                        ]
                        affirmation = random.choice(affirmations)
                        
                        # Find the sentence start to guide them back
                        sentence_start_idx = 0
                        for i in range(matched_idx - 1, -1, -1):
                            w = passage_words[i]
                            if w.endswith('.') or w.endswith('!') or w.endswith('?'):
                                sentence_start_idx = i + 1
                                break
                                
                        # Extract the words of the sentence to show/guide them
                        sentence_words_list = []
                        for i in range(sentence_start_idx, len(passage_words)):
                            sentence_words_list.append(passage_words[i])
                            if passage_words[i].endswith('.') or passage_words[i].endswith('!') or passage_words[i].endswith('?'):
                                break
                        sentence_str = " ".join(sentence_words_list)
                        print(f"Sentence to re-read: '{sentence_str}'")
                        
                        # Reset sentence word states to unread so they can read them again
                        for j in range(sentence_start_idx, matched_idx + 1):
                            word_states[j] = 'unread'
                        
                        current_word_idx = sentence_start_idx
                        if show_karaoke and gigi.face:
                            gigi.face.update_reading_fluency(
                                active=True,
                                current_word_idx=current_word_idx,
                                word_states=word_states,
                                last_wrong_heard=None
                            )
                        
                        gigi.run_character(
                            viseme_data={'text': f"{affirmation} Now, please read the sentence again with the correct word.", 'file': None},
                            face_data={'sequence': 'smile'}
                        )
                        tracker.start()
                    else:
                        # Fallback if they couldn't get it: tell them the word and move past
                        word_states[matched_idx] = 'correct' # Move past it
                        current_word_idx = matched_idx + 1 # Move past the mistake
                        if show_karaoke and gigi.face:
                            gigi.face.update_reading_fluency(
                                active=True,
                                current_word_idx=current_word_idx,
                                word_states=word_states,
                                last_wrong_heard=None
                            )
                        
                        gigi.run_character(
                            viseme_data={'text': f"The word is {first_unmatched_expected}. Let's keep reading!", 'file': None}
                        )
                        tracker.start()
                else:
                    current_word_idx = matched_idx
                    if show_karaoke and gigi.face:
                        gigi.face.update_reading_fluency(
                            active=True,
                            current_word_idx=current_word_idx,
                            word_states=word_states,
                            last_wrong_heard=None
                        )
                    
                if current_word_idx >= len(passage_words):
                    print("Student finished reading the passage successfully.")
                    break

            tracker.stop()
            
            # Disable reading fluency mode after reading is finished
            if show_karaoke and gigi.face:
                gigi.face.update_reading_fluency(active=False)
        else:
            print("Hearing module is not enabled. Simulating reading time...")
            time.sleep(5)
            
        # Access questions from text file and initiate discussion
        print("Initiating short discussion...")
        gigi.run_character(
            viseme_data={'text': 'Great job reading the passage! Now, let us answer some questions.', 'file': None}
        )
        
        discussion_responses = []
        with open(questions_file, 'r') as f:
            questions = f.readlines()
            
        for q in questions:
            q = q.strip()
            if not q:
                continue
                
            print(f"Gigi asks: {q}")
            gigi.run_character(
                viseme_data={'text': q, 'file': None}
            )
            
            if gigi.hearing:
                print("Listening for answer...")
                # Start face follow tracking while child is answering
                tracker.start()
                
                gigi.hearing.texts = []
                gigi.listen_backchannel(timeout=10)
                
                # Stop tracker before Gigi speaks its answer responses
                tracker.stop()
                
                if gigi.hearing.texts:
                    answer = " ".join(gigi.hearing.texts)
                    print(f"Student answered: {answer}")
                    discussion_responses.append({"question": q, "answer": answer})
                    gigi.log_variable("discussion", discussion_responses)
                    
                    # Asynchronous LLM processing with filler speech latency hiding
                    if gigi.conversation:
                        llm_response = []
                        llm_done = threading.Event()
                        
                        def on_success(res):
                            llm_response.append(res)
                            llm_done.set()
                            
                        system_prompt = (
                            "You are Gigi, a friendly reading assistant. "
                            "The student just finished reading a passage and is answering the question: '{}'. "
                            "Respond to their answer: '{}' in one short, warm, encouraging sentence. "
                            "Do not ask any more questions. Keep it simple and natural.".format(q, answer)
                        )
                        
                        # Call local LLM asynchronously
                        t = gigi.conversation.get_response_threaded(
                            system_prompt=system_prompt,
                            user_prompt=answer,
                            on_success=on_success
                        )
                        t.start()
                        
                        # Immediately play a filler/acknowledgment to keep the conversation fluent
                        fillers = [
                            "I see! That is very interesting.",
                            "Hmm, let me think about that response.",
                            "Got it! That makes a lot of sense.",
                            "Oh, that is a really cool answer!"
                        ]
                        filler = random.choice(fillers)
                        print(f"Gigi filler: {filler}")
                        gigi.run_character(viseme_data={'text': filler, 'file': None})
                        
                        # Wait for LLM (up to 5 seconds)
                        llm_done.wait(timeout=5)
                        
                        response_text = llm_response[0] if llm_response else "Thanks for sharing that!"
                        print(f"Gigi response: {response_text}")
                        
                        gigi.run_character(
                            viseme_data={'text': response_text, 'file': None},
                            face_data={'sequence': 'smile'}
                        )
                    else:
                        gigi.run_character(
                            viseme_data={'text': 'That is an interesting answer. Good job.', 'file': None},
                            face_data={'sequence': 'smile'}
                        )
                else:
                    print("No answer received.")
                    discussion_responses.append({"question": q, "answer": None})
                    gigi.log_variable("discussion", discussion_responses)
                    gigi.run_character(
                        viseme_data={'text': 'Okay, let us move on.', 'file': None}
                    )
            else:
                discussion_responses.append({"question": q, "answer": None})
                gigi.log_variable("discussion", discussion_responses)
                time.sleep(3)
                
        # Goodbye
        print("Concluding demo...")
        gigi.run_character(
            viseme_data={'text': 'We are all done for today. You did wonderful! Goodbye!', 'file': None},
            movement_data='wave_hello'
        )
        
        # Return to home position
        if gigi.movement:
            gigi.movement.home_position()
            
    except Exception as e:
        print(f"[Reading Fluency] Error: {e}")
    finally:
        # Clean up and stop threads
        tracker.stop()
        gigi.stop_character()
        print("Reading Fluency Demo finished.")

def readingFluencyDemo():
    play_reading_fluency()

if __name__ == "__main__":
    play_reading_fluency()

import os
import sys
import time
import string
import re
import random
import threading
from difflib import SequenceMatcher

# Append the necessary paths to import Character modules
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir)
gigi_dir = os.path.dirname(scripts_dir)

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)

character_dir = os.path.join(gigi_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

from Character.character import Character

def readingFluencyDemo():
    print("Initializing Gigi for Reading Fluency Demo...")
    
    # Initialize character with wakeup=True to show face and move to home position
    gigi = Character(character_name="fuzzy", wakeup=True)
    
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

    # 1. Gigi starts vision concurrently in the background
    if gigi.vision:
        print("[Demo] Starting background vision system...")
        gigi.vision.run_vision()

    # 2. Gigi first introduces itself while vision tracks faces in parallel
    print("Demonstrating Introduction...")
    gigi.run_character(
        viseme_data={'text': 'Hello! My name is Gigi. I am your reading assistant today.', 'file': None},
        movement_data='wave_hello'
    )
    
    # 3. Greet the person by name if recognized during introduction.
    # No 10-second wait! We check the background vision results immediately.
    print("Demonstrating Face Recognition...")
    recognized_name = None
    if gigi.vision:
        # Give the vision thread a tiny moment (0.5s) to finalize recognition
        time.sleep(0.5)
        
        all_faces = gigi.vision.face_cache.get_all_faces()
        face_detected = len(all_faces) > 0
        
        for face_id, face_info in all_faces.items():
            name = face_info.get('name', 'Unknown')
            is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
            is_unknown = (name == 'Unknown' or is_face_pattern or (name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
            
            if not is_unknown and name != 'Recognizing...':
                recognized_name = name
                break
                
        if recognized_name:
            gigi.run_character(
                viseme_data={'text': f'Hello {recognized_name}, it is great to see you again!', 'file': None},
                face_data={'sequence': 'smile'}
            )
        elif face_detected:
            gigi.run_character(
                viseme_data={'text': 'Hello there! It is great to meet you.', 'file': None},
                face_data={'sequence': 'smile'}
            )
        else:
            print("No face detected during introduction.")
            gigi.run_character(
                viseme_data={'text': 'Hello there! Let us start reading.', 'file': None}
            )
        # Stop vision to conserve CPU/GPU resources on Orange Pi
        gigi.vision.stop_vision()
    else:
        print("Vision module is not enabled.")
        gigi.run_character(
            viseme_data={'text': 'Hello there! It is great to meet you.', 'file': None}
        )

    # 4. Gigi asks the student to read
    print("Asking student to read...")
    gigi.run_character(
        viseme_data={'text': 'Please read the passage in front of you slowly and clearly.', 'file': None}
    )
    
    # 5. Gigi listens and corrects mistakes in real time, ignoring off-topic talks
    print("Listening to reading...")
    with open(passage_file, 'r') as f:
        passage_text = f.read().strip()
        print(f"\n--- Please read the following passage ---\n{passage_text}\n-----------------------------------------\n")
        
    passage_words = passage_text.split()
    current_word_idx = 0
    
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
            nonlocal current_word_idx
            words_heard = [w.translate(str.maketrans('', '', string.punctuation)).lower() for w in text.split()]
            words_heard = [w for w in words_heard if w]
            if not words_heard:
                return False
                
            matched_count = 0
            unmatched_count = 0
            temp_idx = current_word_idx
            
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
                            temp_idx = check_idx + 1
                            matched_count += 1
                            found_match = True
                            break
                if not found_match:
                    # Ignore the last word of a chunk in case it was cut off during speaking
                    if i < len(words_heard) - 1:
                        unmatched_count += 1
                        
            # Determine if the student is talking off-topic (e.g. no words matched or too many consecutive mistakes)
            is_talking = (matched_count == 0) or (unmatched_count >= 3 and matched_count < unmatched_count)
            
            if is_talking:
                return False # Ignore off-topic speech (do not interrupt)
            if unmatched_count >= 1:
                return True # Stop listening immediately to make a correction
            if temp_idx >= len(passage_words):
                return True # Completed passage, stop listening
                
            return False

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
                gigi.run_character(
                    viseme_data={'text': f'The correct word is {first_unmatched_expected}.', 'file': None}
                )
                current_word_idx = matched_idx + 1 # Move past the mistake
            else:
                current_word_idx = matched_idx
                
            if current_word_idx >= len(passage_words):
                print("Student finished reading the passage successfully.")
                break
    else:
        print("Hearing module is not enabled. Simulating reading time...")
        time.sleep(5)
        
    # 6. Access questions from text file and initiate discussion
    print("Initiating short discussion...")
    gigi.run_character(
        viseme_data={'text': 'Great job reading the passage! Now, let us answer some questions.', 'file': None}
    )
    
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
            gigi.hearing.texts = []
            gigi.listen_backchannel(timeout=10)
            
            if gigi.hearing.texts:
                answer = " ".join(gigi.hearing.texts)
                print(f"Student answered: {answer}")
                
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
                gigi.run_character(
                    viseme_data={'text': 'Okay, let us move on.', 'file': None}
                )
        else:
            time.sleep(3)
            
    # 7. Goodbye
    print("Concluding demo...")
    gigi.run_character(
        viseme_data={'text': 'We are all done for today. You did wonderful! Goodbye!', 'file': None},
        movement_data='wave_hello'
    )
    
    # Return to home position
    if gigi.movement:
        gigi.movement.home_position()
        
    # Clean up and stop threads
    gigi.stop_character()
    print("Reading Fluency Demo finished.")

if __name__ == "__main__":
    readingFluencyDemo()

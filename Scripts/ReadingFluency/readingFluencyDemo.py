import os
import sys
import time
import string

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

    # 1. Gigi first introduces itself
    print("Demonstrating Introduction...")
    gigi.run_character(
        viseme_data={'text': 'Hello! My name is Gigi. I am your reading assistant today.', 'file': None},
        movement_data='wave_hello'
    )
    
    # 2. It tries to recognize the face in front of her. 
    # If she does, she greets that person. If not, she greets a generic greeting.
    print("Demonstrating Face Recognition...")
    recognized_name = None
    if gigi.vision:
        gigi.vision.run_vision()
        print("Looking for a face...")
        if hasattr(gigi.vision, 'face_db') and hasattr(gigi.vision.face_db, 'known_names'):
            print(f"Known faces in database: {gigi.vision.face_db.known_names}")
        
        start_time = time.time()
        timeout = 10.0
        face_detected = False
        
        while time.time() - start_time < timeout:
            all_faces = gigi.vision.face_cache.get_all_faces()
            if all_faces:
                face_detected = True
                for face_id, face_info in all_faces.items():
                    name = face_info.get('name', 'Unknown')
                    import re
                    is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                    is_unknown = (name == 'Unknown' or is_face_pattern or (name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
                    
                    if not is_unknown and name != 'Recognizing...':
                        recognized_name = name
                        break
            if recognized_name:
                break
            time.sleep(0.2)
            
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
            print("No face detected within timeout.")
            gigi.run_character(
                viseme_data={'text': 'Hello there! Let us start reading.', 'file': None}
            )
        gigi.vision.stop_vision()
    else:
        print("Vision module is not enabled.")
        gigi.run_character(
            viseme_data={'text': 'Hello there! It is great to meet you.', 'file': None}
        )

    # 3. Then she asks the student to read the passage in front of them slowly.
    print("Asking student to read...")
    gigi.run_character(
        viseme_data={'text': 'Please read the passage in front of you slowly and clearly.', 'file': None}
    )
    
    # 4. Gigi listens to what they are reading and compares with the text.
    print("Listening to reading...")
    with open(passage_file, 'r') as f:
        passage_text = f.read().strip()
        print(f"\n--- Please read the following passage ---\n{passage_text}\n-----------------------------------------\n")
        
    passage_words = passage_text.split()
    current_word_idx = 0
    
    if gigi.hearing:
        while current_word_idx < len(passage_words):
            gigi.hearing.texts = []
            
            # Fluid listening callback to interrupt on mistakes
            def check_fluency(text):
                nonlocal current_word_idx
                words_heard = text.lower().split()
                if not words_heard:
                    return False
                    
                # Check the latest word in the current transcribed chunk
                idx = current_word_idx + len(words_heard) - 1
                if idx < len(passage_words):
                    expected = passage_words[idx]
                    expected_clean = expected.translate(str.maketrans('', '', string.punctuation)).lower()
                    latest_clean = words_heard[-1].translate(str.maketrans('', '', string.punctuation))
                    
                    if expected_clean and latest_clean and expected_clean != latest_clean:
                        return True # Mistake found, stop listening
                        
                if current_word_idx + len(words_heard) >= len(passage_words):
                    return True # Finished reading passage, stop listening
                    
                return False
                
            print(f"Listening for words starting from index {current_word_idx}...")
            gigi.listen_fluid(timeout=15, n_transcripts=1, check_callback=check_fluency)
            
            if not gigi.hearing.texts:
                print("No speech detected. Stopping reading check.")
                break
                
            last_text = gigi.hearing.texts[-1]
            words_heard = last_text.lower().split()
            
            mistake_found = False
            for i, w in enumerate(words_heard):
                if current_word_idx >= len(passage_words):
                    break
                    
                expected = passage_words[current_word_idx]
                expected_clean = expected.translate(str.maketrans('', '', string.punctuation)).lower()
                w_clean = w.translate(str.maketrans('', '', string.punctuation))
                
                if expected_clean and w_clean and expected_clean != w_clean:
                    print(f"Mistake found: heard '{w_clean}', expected '{expected_clean}'")
                    # Gigi speaks the correct word
                    gigi.run_character(
                        viseme_data={'text': f'The correct word is {expected_clean}.', 'file': None}
                    )
                    mistake_found = True
                    current_word_idx += 1 # Move past the mistake
                    break
                else:
                    current_word_idx += 1
                    
            if current_word_idx >= len(passage_words) and not mistake_found:
                print("Student finished reading the passage successfully.")
                break
    else:
        print("Hearing module is not enabled. Simulating reading time...")
        time.sleep(5)
        
    # 5. Access questions from text file and initiate discussion
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
                # Simple conversational response
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
            
    # 6. She says bye
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

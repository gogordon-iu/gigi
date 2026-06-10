import os
import sys
import time
import re
import random

# Append the necessary paths to import Character modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)

character_dir = os.path.join(parent_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

from character import Character
from characterDefinitions import IS_ROBOT

# Assets Directory
ASSETS_DIR = os.path.join(parent_dir, "Assets", "MathQuest")
LOCKED_CHEST = os.path.join(ASSETS_DIR, "locked_chest.png")
OPEN_CHEST = os.path.join(ASSETS_DIR, "open_chest.png")
KEY_EARNED = os.path.join(ASSETS_DIR, "key_earned.png")

# Number word mappings
ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9
}
TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90
}

def parse_spoken_number(text):
    if not text:
        return None
    
    # Check for direct digits first
    digits = re.findall(r'\d+', text)
    if digits:
        return int(digits[0])
        
    text_lower = text.lower().strip()
    # Remove punctuation
    text_clean = re.sub(r'[^\w\s]', ' ', text_lower)
    words = text_clean.split()
    
    # accumulated words representing numbers
    all_number_words = set(list(ONES.keys()) + list(TEENS.keys()) + list(TENS.keys()) + ["hundred", "and"])
    
    accumulated_words = []
    for w in words:
        if w in all_number_words:
            accumulated_words.append(w)
        else:
            if accumulated_words:
                break
                
    if not accumulated_words:
        return None
        
    i = 0
    val = 0
    while i < len(accumulated_words):
        w = accumulated_words[i]
        if w == "and":
            i += 1
            continue
            
        if w in ONES:
            if i + 1 < len(accumulated_words) and accumulated_words[i+1] == "hundred":
                val += ONES[w] * 100
                i += 2
            else:
                val += ONES[w]
                i += 1
        elif w in TEENS:
            val += TEENS[w]
            i += 1
        elif w in TENS:
            val += TENS[w]
            i += 1
        elif w == "hundred":
            val = max(100, val * 100)
            i += 1
        else:
            i += 1
            
    return val

def parse_difficulty(text):
    if not text:
        return "easy"
    text_lower = text.lower().strip()
    if "hard" in text_lower:
        return "hard"
    elif "medium" in text_lower or "explorer" in text_lower:
        return "medium"
    return "easy"

def parse_play_again(text):
    if not text:
        return False
    text_lower = text.lower().strip()
    yes_words = ["yes", "yeah", "yep", "sure", "play", "again", "okay", "ok", "y"]
    words = re.findall(r'\b\w+\b', text_lower)
    return any(word in yes_words for word in words)

def get_counting_hint(f1, f2):
    sequence = [str(f1 * i) for i in range(1, f2)]
    return ", ".join(sequence)

def generate_questions(difficulty, count=5):
    if difficulty == "easy":
        tables = [1, 2, 3, 5, 10]
    elif difficulty == "medium":
        tables = [4, 6, 7, 8]
    else:
        tables = [9, 11, 12]
        
    questions = []
    attempts = 0
    while len(questions) < count and attempts < 100:
        attempts += 1
        f1 = random.choice(tables)
        f2 = random.randint(1, 10)
        q = (f1, f2)
        if q not in questions:
            questions.append(q)
            
    while len(questions) < count:
        f1 = random.choice(tables)
        f2 = random.randint(1, 10)
        questions.append((f1, f2))
        
    return questions

def get_user_input(gigi, timeout=10):
    if gigi.hearing:
        gigi.hearing.texts = []
        print(f"[Math Quest] Listening for {timeout} seconds...")
        gigi.listen_backchannel(timeout=timeout)
        heard = " ".join(gigi.hearing.texts).strip()
        print(f"[Math Quest] Heard: '{heard}'")
        return heard
    else:
        print("\n[Math Quest] (Hearing disabled) Please type your response in the terminal:")
        try:
            res = input("> ").strip()
            return res
        except (KeyboardInterrupt, EOFError):
            return "quit"

def play_math_quest():
    print("====================================================")
    print("             GIGI Math Quest Game Demo              ")
    print("====================================================")
    
    # Initialize character
    gigi = Character(character_name="fuzzy", wakeup=True, activity="MathQuest")
    time.sleep(2)
    
    try:
        # Start background vision
        if gigi.vision:
            print("[Math Quest] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # Welcome message
        gigi.run_character(
            viseme_data={'text': "Hello adventurer! Welcome to Gigi's Math Quest!", 'file': None},
            movement_data='wave_hello'
        )
        
        # Explain the quest
        gigi.run_character(
            viseme_data={'text': "I found a mysterious locked treasure chest, but we need five golden keys to open it! We can earn them by solving multiplication questions together.", 'file': None}
        )
        
        # Display locked chest
        print("[Math Quest] Displaying locked chest image.")
        gigi.face.display_image_file(LOCKED_CHEST)
        gigi._cv_wait(3.0)
        gigi.face.display_image_file(None) # Restore face
        
        playing = True
        while playing:
            gigi.run_character(
                viseme_data={'text': "What level would you like to play? Easy, Medium, or Hard?", 'file': None},
                movement_data='open_arms'
            )
            
            # Gaze tracking check
            if gigi.vision:
                gigi.lookat_something(what="face", timeout=1.5)
                
            level_resp = get_user_input(gigi, timeout=8)
            difficulty = parse_difficulty(level_resp)
            print(f"[Math Quest] Selected difficulty: {difficulty}")
            
            gigi.run_character(
                viseme_data={'text': f"Great choice! Let's search for our first golden key in {difficulty} level!", 'file': None}
            )
            
            questions = generate_questions(difficulty, count=5)
            keys_collected = 0
            
            for idx, (f1, f2) in enumerate(questions):
                correct_ans = f1 * f2
                print(f"[Math Quest] Q{idx+1}: {f1} * {f2} = {correct_ans}")
                
                # Ask question
                gigi.run_character(
                    viseme_data={'text': f"Question {idx+1}. What is {f1} times {f2}?", 'file': None}
                )
                
                answered_correctly = False
                attempts = 0
                max_attempts = 2
                
                while attempts < max_attempts and not answered_correctly:
                    attempts += 1
                    
                    if gigi.vision:
                        gigi.lookat_something(what="face", timeout=1.5)
                        
                    response = get_user_input(gigi, timeout=10)
                    parsed_val = parse_spoken_number(response)
                    print(f"[Math Quest] Attempt {attempts}: Spoken '{response}' -> parsed '{parsed_val}'")
                    
                    if parsed_val == correct_ans:
                        answered_correctly = True
                        keys_collected += 1
                        
                        # Celebration speech
                        congrats = [
                            f"Awesome job! {f1} times {f2} is indeed {correct_ans}!",
                            f"Spot on! That's exactly {correct_ans}!",
                            f"You got it! You are so good at this!",
                            f"Fantastic! You've earned a golden key!"
                        ]
                        gigi.run_character(
                            viseme_data={'text': random.choice(congrats), 'file': None},
                            movement_data='clap'
                        )
                        # Smile and show key
                        gigi.face.run_sequence('smile')
                        gigi.face.display_image_file(KEY_EARNED)
                        gigi._cv_wait(2.5)
                        gigi.face.display_image_file(None) # Restore face
                    else:
                        # Encouragement for incorrect answer
                        if attempts < max_attempts:
                            hint = get_counting_hint(f1, f2)
                            gigi.run_character(
                                viseme_data={'text': f"That was a super try! You are thinking so hard. Let's count by {f1}s: {hint}. What comes next? What is {f1} times {f2}?", 'file': None},
                                movement_data='open_arms'
                            )
                        else:
                            # Grant key for effort
                            keys_collected += 1
                            gigi.run_character(
                                viseme_data={'text': f"You worked so hard on that question! {f1} times {f2} is {correct_ans}. Since you tried your best, you absolutely deserve a key! Here is your golden key!", 'file': None},
                                movement_data='clap'
                            )
                            gigi.face.run_sequence('smile')
                            gigi.face.display_image_file(KEY_EARNED)
                            gigi._cv_wait(2.5)
                            gigi.face.display_image_file(None) # Restore face
                            
            # Completed Quest!
            print(f"[Math Quest] Quest complete. Keys collected: {keys_collected}")
            
            gigi.run_character(
                viseme_data={'text': "Hooray! We collected all five golden keys! Let's unlock the treasure chest!", 'file': None},
                movement_data='clap'
            )
            gigi.face.run_sequence('smile')
            
            # Display open chest
            gigi.face.display_image_file(OPEN_CHEST)
            
            gigi.run_character(
                viseme_data={'text': "Wow, look at all the gold and gems! You solved all the math mysteries and unlocked the treasure! You are a multiplication master!", 'file': None}
            )
            gigi._cv_wait(5.0)
            gigi.face.display_image_file(None) # Restore face
            
            gigi.run_character(
                viseme_data={'text': "Would you like to play again and search for another treasure?", 'file': None}
            )
            
            play_again_resp = get_user_input(gigi, timeout=8)
            if not parse_play_again(play_again_resp):
                playing = False
                
        # Goodbye
        gigi.run_character(
            viseme_data={'text': "Thank you for playing Math Quest with me! See you next time, bye bye!", 'file': None},
            movement_data='wave_hello'
        )
        if gigi.movement:
            gigi.movement.home_position()
            
    except Exception as e:
        print(f"[Math Quest] Error: {e}")
    finally:
        if gigi.vision:
            gigi.vision.stop_vision()
        gigi.stop_character()
        print("[Math Quest] Game finished cleanly.")

if __name__ == "__main__":
    play_math_quest()

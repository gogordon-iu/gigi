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

WORD_TO_DIGIT = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
}

def parse_user_response(text):
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    # Check for give up phrases
    give_up_phrases = ["give up", "quit", "reveal", "show me", "stop", "concede"]
    if any(phrase in text_lower for phrase in give_up_phrases):
        return "give_up"
        
    # Replace number words with digits
    processed_text = text_lower
    for word, digit in WORD_TO_DIGIT.items():
        processed_text = re.sub(r'\b' + word + r'\b', digit, processed_text)
        
    # Extract all digits
    digits = [char for char in processed_text if char.isdigit()]
    
    if len(digits) >= 4:
        return "".join(digits[:4])
        
    return None

def parse_play_again(text):
    if not text:
        return False
    text_lower = text.lower().strip()
    yes_words = ["yes", "yeah", "yep", "sure", "play", "again", "okay", "ok", "y"]
    words = re.findall(r'\b\w+\b', text_lower)
    return any(word in yes_words for word in words)

def check_guess(secret, guess):
    bulls = 0
    cows = 0
    
    secret_matched = [False] * 4
    guess_matched = [False] * 4
    
    # First pass: check for bulls (exact matches)
    for i in range(4):
        if guess[i] == secret[i]:
            bulls += 1
            secret_matched[i] = True
            guess_matched[i] = True
            
    # Second pass: check for cows (partial matches)
    for i in range(4):
        if not guess_matched[i]:
            for j in range(4):
                if not secret_matched[j] and guess[i] == secret[j]:
                    cows += 1
                    secret_matched[j] = True
                    break
                    
    return bulls, cows

def get_user_input(gigi, timeout=10):
    if gigi.hearing:
        gigi.hearing.texts = []
        print(f"[Mastermind] Listening for {timeout} seconds...")
        gigi.listen_backchannel(timeout=timeout)
        heard = " ".join(gigi.hearing.texts).strip()
        print(f"[Mastermind] Heard: '{heard}'")
        return heard
    else:
        # Fallback to terminal input for testing / simulation
        print("\n[Mastermind] (Hearing disabled) Please type your response in the terminal:")
        try:
            res = input("> ").strip()
            return res
        except (KeyboardInterrupt, EOFError):
            return "quit"

def play_mastermind():
    print("====================================================")
    print("             GIGI Mastermind Game Demo              ")
    print("====================================================")
    
    # Initialize character with wakeup=True to enable startup look/position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="Mastermind")
    gigi.face.overlay_text = None
    time.sleep(2)  # Allow motors and modules to initialize
    
    try:
        # Start background vision to look for face / track face
        if gigi.vision:
            print("[Mastermind] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # Welcome message
        gigi.run_character(
            viseme_data={'text': "Hi there! Let's play a fun game of Mastermind with numbers!", 'file': None},
            movement_data='wave_hello'
        )
        
        gigi.run_character(
            viseme_data={'text': "I will pick four secret numbers from zero to nine without repeats. You will try to guess them! Are you ready?", 'file': None}
        )
        
        # Look at the child
        if gigi.vision:
            gigi.lookat_something(what="face", timeout=2.0)
            
        ready_response = get_user_input(gigi, timeout=8)
        # Even if they don't say yes, we start the game to keep it engaging
        
        playing = True
        while playing:
            # Generate secret code
            secret = "".join(str(d) for d in random.sample(range(10), 4))
            print(f"[DEBUG] Secret code generated: {secret}")
            
            gigi.run_character(
                viseme_data={'text': "Okay! I have chosen my secret numbers. Tell me your first guess of four digits!", 'file': None},
                movement_data='open_arms'
            )
            
            attempts = 0
            game_over = False
            
            while not game_over:
                # Gaze redirection if face detected
                if gigi.vision:
                    gigi.lookat_something(what="face", timeout=1.5)
                    
                # Clear overlay text before the user guesses
                gigi.face.overlay_text = None
                
                response = get_user_input(gigi, timeout=10)
                parsed = parse_user_response(response)
                
                if parsed == "give_up":
                    # Display code on screen
                    code_display = " ".join(secret)
                    print(f"[Mastermind] Child gave up. Displaying secret code: {code_display}")
                    
                    # Speak encouragement first
                    gigi.run_character(
                        viseme_data={'text': "No worries! Mastermind is a tricky game. Let me show you the secret code on my screen!", 'file': None},
                        movement_data='open_arms'
                    )
                    
                    # Display code on screen
                    gigi.face.display_text(f"Secret Code:\n\n{code_display}")
                    
                    # Speak encouraging words while code is displayed
                    gigi.run_character(
                        viseme_data={'text': f"The numbers were {', '.join(secret)}. You did a wonderful job trying!", 'file': None}
                    )
                    
                    # Wait 4 seconds for display
                    gigi._cv_wait(4.0)
                    
                    # Restore face
                    gigi.face.display_text(None)
                    
                    gigi.run_character(
                        viseme_data={'text': "Would you like to try again and play a new game?", 'file': None}
                    )
                    
                    play_again_resp = get_user_input(gigi, timeout=8)
                    if parse_play_again(play_again_resp):
                        game_over = True
                    else:
                        playing = False
                        game_over = True
                        
                elif parsed is not None:
                    # Display the 4 digits heard from the child
                    gigi.face.overlay_text = " ".join(parsed)
                    gigi.face.display_text(None) # Force face update to show digits
                    
                    attempts += 1
                    bulls, cows = check_guess(secret, parsed)
                    print(f"[Mastermind] Attempt {attempts}: Guess '{parsed}' -> Bulls: {bulls}, Cows: {cows}")
                    
                    if bulls == 4:
                        # Success celebration!
                        gigi.run_character(
                            viseme_data={'text': f"Yay! You got it! The secret code was indeed {', '.join(secret)}!", 'file': None},
                            movement_data='clap'
                        )
                        # Show big smile
                        gigi.face.run_sequence('smile')
                        gigi.run_character(
                            viseme_data={'text': f"You guessed it in {attempts} tries! You are a mastermind champion!", 'file': None}
                        )
                        gigi.run_character(
                            viseme_data={'text': "Would you like to play another game?", 'file': None}
                        )
                        
                        play_again_resp = get_user_input(gigi, timeout=8)
                        if parse_play_again(play_again_resp):
                            game_over = True
                        else:
                            playing = False
                            game_over = True
                    else:
                        # Build friendly response text
                        feedback_parts = []
                        if bulls > 0:
                            feedback_parts.append(f"{bulls} number{'s' if bulls != 1 else ''} in the correct place")
                        if cows > 0:
                            feedback_parts.append(f"{cows} number{'s' if cows != 1 else ''} correct but in the wrong place")
                            
                        if not feedback_parts:
                            feedback_text = "None of those numbers are in my secret code, but that is very helpful clues! Try some different numbers!"
                            movement = 'look_from_side_to_side'
                        else:
                            feedback_text = f"You have " + " and ".join(feedback_parts) + ". Good try, keep going!"
                            movement = 'open_arms'
                            
                        gigi.run_character(
                            viseme_data={'text': feedback_text, 'file': None},
                            movement_data=movement
                        )
                else:
                    gigi.run_character(
                        viseme_data={'text': "I didn't quite hear four numbers. Remember to say four different digits between zero and nine!", 'file': None}
                    )
                    
        # Outro
        gigi.run_character(
            viseme_data={'text': "Thanks for playing Mastermind with me today! You are awesome. Bye bye!", 'file': None},
            movement_data='wave_hello'
        )
        if gigi.movement:
            gigi.movement.home_position()
            
    except Exception as e:
        print(f"[Mastermind] Error during game: {e}")
    finally:
        if gigi.vision:
            gigi.vision.stop_vision()
        gigi.face.overlay_text = None
        gigi.stop_character()
        print("[Mastermind] Gigi Mastermind game demo finished cleanly.")

if __name__ == "__main__":
    play_mastermind()

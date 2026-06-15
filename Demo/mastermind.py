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

def parse_game_mode(text, gigi=None):
    if not text:
        return None
    text_lower = text.lower().strip()
    
    if gigi and getattr(gigi, 'conversation', None):
        system_prompt = (
            "You are a game mode classifier for a Mastermind game.\n"
            "The child is deciding whether they want to guess Gigi's secret number, "
            "or whether Gigi should guess the child's secret number.\n\n"
            "Options:\n"
            "- 'child_guesses': The child wants to guess (e.g. 'I want to guess', 'my turn', 'you pick', 'I will guess').\n"
            "- 'gigi_guesses': Gigi should guess the child's number (e.g. 'you guess', 'your turn', 'you pick the number').\n\n"
            "Analyze the user prompt and classify it. Output ONLY 'child_guesses' or 'gigi_guesses'. "
            "If it is ambiguous or unrecognized, output 'unknown'. "
            "Do not include any extra words, punctuation, or explanations."
        )
        try:
            response = gigi.conversation.get_response(system_prompt=system_prompt, user_prompt=text)
            cleaned = response.strip().lower()
            if "child_guesses" in cleaned:
                return "child_guesses"
            elif "gigi_guesses" in cleaned:
                return "gigi_guesses"
        except Exception as e:
            print(f"[Mastermind LLM] Error calling LLM: {e}")

    gigi_guess_words = ["you", "gigi", "robot", "your turn", "you guess", "you pick", "gigi guess", "gigi pick"]
    child_guess_words = ["i", "me", "my", "my turn", "i guess", "i pick", "me guess", "me pick"]
    
    gigi_count = sum(word in text_lower for word in gigi_guess_words)
    child_count = sum(word in text_lower for word in child_guess_words)
    
    if gigi_count > child_count:
        return "gigi_guesses"
    elif child_count > gigi_count:
        return "child_guesses"
    else:
        if "you" in text_lower or "gigi" in text_lower or "robot" in text_lower:
            return "gigi_guesses"
        if "i" in text_lower or "me" in text_lower or "my" in text_lower:
            return "child_guesses"
        return None

def parse_feedback_response(text):
    if not text:
        return None
    text_lower = text.lower().strip()
    
    if "you got it" in text_lower or "correct" in text_lower or "all black" in text_lower or "four black" in text_lower or "4 black" in text_lower:
        return (4, 0)
        
    if ("none" in text_lower or "nothing" in text_lower or "zero" in text_lower or text_lower == "0") and "black" not in text_lower and "white" not in text_lower:
        return (0, 0)
        
    word_to_num = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "none": 0}
    for word, val in word_to_num.items():
        text_lower = re.sub(r'\b' + word + r'\b', str(val), text_lower)
        
    black_match = re.search(r'(\d)\s*(?:black|blak|blk|place)', text_lower)
    white_match = re.search(r'(\d)\s*(?:white|wite|wht|included)', text_lower)
    
    black = None
    white = None
    
    if black_match:
        black = int(black_match.group(1))
    if white_match:
        white = int(white_match.group(1))
        
    if black is not None and white is not None:
        return (black, white)
        
    if black is not None and "white" not in text_lower:
        return (black, 0)
    if white is not None and "black" not in text_lower:
        return (0, white)
        
    nums = re.findall(r'\d', text_lower)
    if len(nums) == 2:
        return (int(nums[0]), int(nums[1]))
        
    return None

def get_all_candidates():
    from itertools import permutations
    perms = permutations(range(10), 4)
    return ["".join(str(d) for d in p) for p in perms]

def filter_candidates(candidates, guess, black, white):
    filtered = []
    for cand in candidates:
        b, w = check_guess(cand, guess)
        if b == black and w == white:
            filtered.append(cand)
    return filtered

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
        
        playing = True
        while playing:
            gigi.run_character(
                viseme_data={'text': "Would you like to guess my secret number, or do you want me to guess your secret number?", 'file': None}
            )
            
            # Look at the child
            if gigi.vision:
                gigi.lookat_something(what="face", timeout=2.0)
                
            mode_response = get_user_input(gigi, timeout=8)
            mode = parse_game_mode(mode_response, gigi=gigi)
            
            if mode is None:
                gigi.run_character(
                    viseme_data={'text': "I didn't quite catch that! Should you guess, or should I guess?", 'file': None}
                )
                mode_response2 = get_user_input(gigi, timeout=8)
                mode = parse_game_mode(mode_response2, gigi=gigi)
                if mode is None:
                    # Default to child guessing
                    mode = "child_guesses"
                    
            if mode == "child_guesses":
                gigi.run_character(
                    viseme_data={'text': "I will pick four secret numbers from zero to nine without repeats. Try to guess them!", 'file': None}
                )
                
                # Generate secret code
                secret = "".join(str(d) for d in random.sample(range(10), 4))
                print(f"[DEBUG] Secret code generated: {secret}")
                local_guesses = []
                gigi.log_variable("secret_code", secret)
                gigi.log_variable("guesses", local_guesses)
                
                gigi.run_character(
                    viseme_data={'text': "Okay! I have chosen my secret numbers. Tell me your first guess of four digits!", 'file': None}
                )
                
                attempts = 0
                game_over = False
                
                while not game_over:
                    # Gaze redirection if face detected
                    if gigi.vision:
                        gigi.lookat_something(what="face", timeout=1.5)
                        
                    # Clear overlay text before the user guesses
                    gigi.face.overlay_text = None
                    
                    # Enable pronunciation mode for Vosk grammar restriction with all 4-digit combinations
                    if gigi.hearing:
                        import itertools
                        digits_list = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
                        # Generate all 10,000 combinations of 4-digit sequences
                        grammar_combinations = [" ".join(combo) for combo in itertools.product(digits_list, repeat=4)]
                        # Add control and give-up phrases
                        grammar_combinations.extend(["give up", "quit", "reveal", "show me", "stop", "concede"])
                        
                        gigi.hearing.pronunciation_mode = True
                        gigi.hearing.pronunciation_grammar = grammar_combinations
                        
                    response = get_user_input(gigi, timeout=10)
                    
                    if gigi.hearing:
                        gigi.hearing.pronunciation_mode = False
                        
                    parsed = parse_user_response(response)
                    
                    if parsed == "give_up":
                        # Display code on screen
                        code_display = " ".join(secret)
                        print(f"[Mastermind] Child gave up. Displaying secret code: {code_display}")
                        
                        # Speak encouragement first
                        gigi.run_character(
                            viseme_data={'text': "No worries! Mastermind is a tricky game. Let me show you the secret code on my screen!", 'file': None}
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
                        local_guesses.append({
                            "attempt": attempts,
                            "guess": parsed,
                            "raw_heard": response,
                            "bulls": bulls,
                            "cows": cows
                        })
                        gigi.log_variable("guesses", local_guesses)
                        
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
                                movement = None
                                
                            gigi.run_character(
                                viseme_data={'text': feedback_text, 'file': None},
                                movement_data=movement
                            )
                    else:
                        gigi.run_character(
                            viseme_data={'text': "I didn't quite hear four numbers. Remember to say four different digits between zero and nine!", 'file': None}
                        )
            else:
                # Gigi guesses mode
                gigi.run_character(
                    viseme_data={'text': "Hooray! I love guessing games! Please think of a four digit number from zero to nine with no repeating digits.", 'file': None}
                )
                gigi.run_character(
                    viseme_data={'text': "Write it down on a piece of paper so you don't forget! When I guess, tell me how many correct digits are in the correct place, which we'll call black. And how many are correct but in the wrong place, which we'll call white.", 'file': None}
                )
                gigi.run_character(
                    viseme_data={'text': "Let me know when you are ready to start!", 'file': None}
                )
                
                # Wait for ready response
                get_user_input(gigi, timeout=8)
                
                candidates = get_all_candidates()
                attempts = 0
                game_over = False
                candidates_history = []
                reprompt_last_guess = False
                guess = None
                
                while not game_over:
                    if not reprompt_last_guess:
                        if len(candidates) == 0:
                            gigi.run_character(
                                viseme_data={'text': "Oh dear! It seems some of the clues might have been a bit mixed up, because no numbers can fit that feedback! Let's restart our game.", 'file': None},
                                movement_data='look_from_side_to_side'
                            )
                            game_over = True
                            break
                            
                        if attempts == 0:
                            guess = "0123"  # Standard optimal first guess
                        else:
                            guess = random.choice(candidates)
                            
                        attempts += 1
                        
                    reprompt_last_guess = False
                    print(f"[Mastermind Solver] Attempt {attempts}: Gigi guesses '{guess}' (Candidates left: {len(candidates)})")
                    
                    # Display guess on screen
                    gigi.face.overlay_text = f"My Guess:\n{' '.join(guess)}"
                    gigi.face.display_text(None)
                    
                    # Say the guess
                    if attempts == 1:
                        guess_text = f"My first guess is {', '.join(guess)}."
                    else:
                        guess_text = f"My guess number {attempts} is {', '.join(guess)}."
                        
                    gigi.run_character(
                        viseme_data={'text': f"{guess_text} How many black and white indicators do I have?", 'file': None}
                    )
                    
                    feedback_received = False
                    while not feedback_received:
                        if gigi.vision:
                            gigi.lookat_something(what="face", timeout=1.5)
                            
                        response = get_user_input(gigi, timeout=12)
                        
                        if "quit" in response.lower() or "give up" in response.lower():
                            game_over = True
                            playing = False
                            feedback_received = True
                            break
                            
                        fb = parse_feedback_response(response)
                        if fb is not None:
                            black, white = fb
                            feedback_received = True
                        else:
                            gigi.run_character(
                                viseme_data={'text': "I didn't quite catch that. Please tell me the number of black and white indicators, like two black and one white.", 'file': None}
                            )
                            
                    if not playing:
                        break
                        
                    print(f"[Mastermind Solver] Feedback: {black} Black, {white} White")
                    
                    if black == 4:
                        # Gigi wins!
                        gigi.face.overlay_text = f"Victory!\n{' '.join(guess)}"
                        gigi.face.display_text(None)
                        
                        gigi.run_character(
                            viseme_data={'text': f"Yay! I got it! Your secret number was indeed {', '.join(guess)}!", 'file': None},
                            movement_data='clap'
                        )
                        gigi.face.run_sequence('smile')
                        gigi.run_character(
                            viseme_data={'text': f"I guessed it in {attempts} tries! That was so much fun!", 'file': None}
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
                        # Save state to history before filtering
                        candidates_history.append((list(candidates), guess))
                        new_candidates = filter_candidates(candidates, guess, black, white)
                        
                        if len(new_candidates) == 0:
                            # Warn the child and backtrack
                            gigi.run_character(
                                viseme_data={'text': f"Oh, wait a second! If my guess was {', '.join(guess)} and you said {black} black and {white} white, no numbers can fit that feedback. Could you please check your last answer?", 'file': None},
                                movement_data='look_from_side_to_side'
                            )
                            candidates, guess = candidates_history.pop()
                            reprompt_last_guess = True
                        else:
                            candidates = new_candidates
                    
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

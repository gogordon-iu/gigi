import os
import sys
import time
import re
import random
import urllib.request
import cv2
import numpy as np

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

# YOLOv11-nano ONNX Model Paths
RESOURCES_DIR = os.path.join(parent_dir, "Resources")
YOLO_MODEL_PATH = os.path.join(RESOURCES_DIR, "yolo11n.onnx")

# COCO classes representing toys/dolls/common props
PROP_CLASSES = {
    77: "teddy bear",
    32: "ball",
    73: "book",
    39: "bottle",
    41: "cup",
    67: "phone",
    24: "bag",
    26: "handbag",
    28: "box",
    15: "toy cat",
    16: "toy dog",
    58: "plant",
    29: "frisbee",
    35: "skateboard",
    76: "scissors",
    79: "toothbrush"
}

def download_model_if_needed():
    if not os.path.exists(YOLO_MODEL_PATH):
        print(f"[Object Detection] Model not found. Downloading YOLOv11-nano ONNX model to {YOLO_MODEL_PATH} (approx. 22MB)...")
        os.makedirs(RESOURCES_DIR, exist_ok=True)
        url = "https://huggingface.co/aaurelions/yolo11n.onnx/resolve/main/yolo11n.onnx?download=true"
        urllib.request.urlretrieve(url, YOLO_MODEL_PATH)
        print("[Object Detection] Model downloaded successfully.")
    else:
        echo_path = YOLO_MODEL_PATH
        print(f"[Object Detection] Model already exists at {YOLO_MODEL_PATH}")
    return YOLO_MODEL_PATH

def run_object_detection(net, frame):
    if frame is None:
        return []
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward()
    
    output = outputs[0]
    if len(output.shape) == 3:
        output = output[0]  # shape: (84, 8400)
    output = output.T      # shape: (8400, 84)

    boxes = []
    confidences = []
    class_ids = []

    for row in output:
        classes_scores = row[4:]
        class_id = np.argmax(classes_scores)
        confidence = classes_scores[class_id]
        
        if confidence > 0.40:
            cx, cy, box_w, box_h = row[0], row[1], row[2], row[3]
            # Map back to original coordinate space
            x = int((cx - box_w/2) * w / 640.0)
            y = int((cy - box_h/2) * h / 640.0)
            bw = int(box_w * w / 640.0)
            bh = int(box_h * h / 640.0)
            
            boxes.append([x, y, bw, bh])
            confidences.append(float(confidence))
            class_ids.append(int(class_id))
            
    indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.40, 0.45)
    
    detected = []
    if len(indices) > 0:
        for idx in indices.flatten():
            detected.append({
                "class_id": class_ids[idx],
                "confidence": confidences[idx],
                "box": boxes[idx]
            })
            
    return detected

def clean_response(text):
    if not text:
        return ""
    # Strip speakers and extra dialogue
    text = re.sub(r"^(robot:|assistant:|student:|gigi:)\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.split(r"\n\s*(student:|robot:|user:|assistant:|gigi:)", text, flags=re.IGNORECASE)[0]
    return text.strip()

def get_user_input(gigi, timeout=12):
    if gigi.hearing:
        gigi.hearing.texts = []
        print(f"[Story Game] Listening for {timeout} seconds...")
        gigi.listen_backchannel(timeout=timeout)
        heard = " ".join(gigi.hearing.texts).strip()
        print(f"[Story Game] Heard: '{heard}'")
        return heard
    else:
        print("\n[Story Game] (Hearing disabled) Please type your story continuation in the terminal:")
        try:
            res = input("> ").strip()
            return res
        except (KeyboardInterrupt, EOFError):
            return "the end"

def parse_confirmation(text):
    if not text:
        return False
    text_lower = text.lower().strip()
    yes_words = ["yes", "yeah", "yep", "sure", "correct", "right", "uh-huh", "y"]
    words = re.findall(r'\b[\w-]+\b', text_lower)
    return any(word in yes_words for word in words)

def play_story_game():
    print("====================================================")
    print("             GIGI Story Quest Game Demo             ")
    print("====================================================")
    
    # Ensure model is downloaded
    try:
        download_model_if_needed()
    except Exception as e:
        print(f"[Story Game] Error downloading model: {e}")
        return
        
    print("[Story Game] Initializing model...")
    try:
        net = cv2.dnn.readNetFromONNX(YOLO_MODEL_PATH)
        print("[Story Game] Model loaded successfully.")
    except Exception as e:
        print(f"[Story Game] Error loading YOLO model: {e}")
        return
        
    # Initialize character
    gigi = Character(character_name="fuzzy", wakeup=True, activity="StoryQuest")
    time.sleep(2)
    
    try:
        # Start background vision
        if gigi.vision:
            print("[Story Game] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # Greeting
        gigi.run_character(
            viseme_data={'text': "Hi there! Let's tell a magical make-belief story together!", 'file': None},
            movement_data='wave_hello'
        )
        
        gigi.run_character(
            viseme_data={'text': "Can you bring a toy, a doll, or any cool prop to play with? Hold it up in front of my camera so I can see what you brought!", 'file': None},
            movement_data='open_arms'
        )
        
        # Searching loop for prop
        detected_prop = None
        start_time = time.time()
        print("[Story Game] Looking for prop in camera feed (30s timeout)...")
        
        while time.time() - start_time < 30.0:
            if gigi.vision:
                frame = gigi.vision.get_latest_frame()
                if frame is not None:
                    detections = run_object_detection(net, frame)
                    # Filter out person (class 0)
                    props = [d for d in detections if d["class_id"] != 0]
                    
                    if props:
                        best_prop = max(props, key=lambda x: x["confidence"])
                        class_id = best_prop["class_id"]
                        detected_prop = PROP_CLASSES.get(class_id, "toy")
                        print(f"[Story Game] Detected: {detected_prop} (class {class_id}) with confidence {best_prop['confidence']:.2f}")
                        break
            time.sleep(0.3)
            
        # Confirmation/Fallback
        if detected_prop:
            gigi.run_character(
                viseme_data={'text': f"Oh! I see you brought a {detected_prop}! Is that what we are playing with?", 'file': None}
            )
            confirm_resp = get_user_input(gigi, timeout=8)
            if not parse_confirmation(confirm_resp):
                # Fallback to manual naming
                gigi.run_character(
                    viseme_data={'text': "Oh, my silly robot eyes! What is the name of the toy you brought?", 'file': None}
                )
                prop_resp = get_user_input(gigi, timeout=8)
                if prop_resp:
                    # Extract prop name using local LLM
                    system_extract = "Extract exactly the name of the toy or object the user mentions they brought. Reply with ONLY the noun (e.g. 'car', 'dinosaur', 'doll')."
                    raw_extract = gigi.conversation.get_response(system_extract, prop_resp)
                    detected_prop = clean_response(raw_extract)
                else:
                    detected_prop = "toy"
        else:
            # Fallback if nothing detected
            gigi.run_character(
                viseme_data={'text': "I couldn't quite see what you have. What is the name of the toy you brought to play with?", 'file': None}
            )
            prop_resp = get_user_input(gigi, timeout=8)
            if prop_resp:
                system_extract = "Extract exactly the name of the toy or object the user mentions they brought. Reply with ONLY the noun (e.g. 'car', 'dinosaur', 'doll')."
                raw_extract = gigi.conversation.get_response(system_extract, prop_resp)
                detected_prop = clean_response(raw_extract)
            else:
                detected_prop = "magic toy"
                
        print(f"[Story Game] Confirmed prop: {detected_prop}")
        gigi.log_variable("prop", detected_prop)
        
        # Start story
        gigi.run_character(
            viseme_data={'text': f"Excellent! A {detected_prop}! That is a perfect prop for our make-belief adventure.", 'file': None},
            movement_data='clap'
        )
        gigi.face.run_sequence('smile')
        
        gigi.run_character(
            viseme_data={'text': f"You start first! Tell me the first line of the story with your {detected_prop}.", 'file': None}
        )
        
        # Story history initialization
        story_history = []
        system_prompt = (
            f"You are Gigi, a friendly and perky social robot. You are playing a make-belief story game with a child "
            f"who brought a {detected_prop}. You are taking turns telling the story. Continue the story with exactly "
            f"ONE short, highly imaginative, child-friendly sentence. Do not repeat speaker names or write list points."
        )
        story_history.append({"role": "system", "content": system_prompt})
        
        game_active = True
        while game_active:
            # Gaze centering
            if gigi.vision:
                gigi.lookat_something(what="face", timeout=1.5)
                
            # Listen to child
            child_turn = get_user_input(gigi, timeout=20)
            
            if not child_turn:
                gigi.run_character(
                    viseme_data={'text': "I'm listening! What happens next in our story?", 'file': None}
                )
                continue
                
            # Check for termination
            lower_turn = child_turn.lower()
            finish_phrases = ["the end", "i am done", "finished", "stop the story", "bye bye", "that's it", "quit"]
            if any(phrase in lower_turn for phrase in finish_phrases):
                gigi.run_character(
                    viseme_data={'text': "Oh, what a wonderful adventure we had! The end! You are a great storyteller!", 'file': None},
                    movement_data='clap'
                )
                gigi.face.run_sequence('smile')
                game_active = False
                break
                
            story_history.append({"role": "user", "content": f"Child: {child_turn}"})
            
            # Gigi's turn
            # Play a short responsive filler
            fillers = [
                "Oh! And then?",
                "That is so exciting!",
                "Wow! Let's see what happens next...",
                "Ooh! That is a fun twist!"
            ]
            gigi.run_character(viseme_data={'text': random.choice(fillers), 'file': None})
            
            # Call NPU/LLM to generate continuation
            try:
                raw_resp = gigi.conversation._call_npu(story_history)
                gigi_continuation = clean_response(raw_resp)
                
                # Truncate to one sentence
                sentences = re.split(r'(?<=[.!?])\s+', gigi_continuation)
                if sentences:
                    gigi_continuation = sentences[0].strip()
                    
                print(f"[Story Game] Gigi story turn: {gigi_continuation}")
                story_history.append({"role": "assistant", "content": f"Gigi: {gigi_continuation}"})
                
                # Pick a random movement
                movement = random.choice(['open_arms', 'look_from_side_to_side', 'clap', 'home'])
                
                gigi.run_character(
                    viseme_data={'text': gigi_continuation, 'file': None},
                    movement_data=movement
                )
            except Exception as e:
                print(f"[Story Game] LLM continuation error: {e}")
                fallback_continuation = f"Then, all of a sudden, the {detected_prop} started to float in the air!"
                gigi.run_character(
                    viseme_data={'text': fallback_continuation, 'file': None},
                    movement_data='open_arms'
                )
                story_history.append({"role": "assistant", "content": f"Gigi: {fallback_continuation}"})
            
            # Log current progress of story turns
            gigi.log_variable("story_turns", [item for item in story_history if item["role"] != "system"])
                
        # Goodbye
        gigi.run_character(
            viseme_data={'text': "Thanks for playing make-belief stories with me today. Goodbye!", 'file': None},
            movement_data='wave_hello'
        )
        if gigi.movement:
            gigi.movement.home_position()
            
    except Exception as e:
        print(f"[Story Game] Error: {e}")
    finally:
        if gigi.vision:
            gigi.vision.stop_vision()
        gigi.stop_character()
        print("[Story Game] Gigi Story Quest finished cleanly.")

if __name__ == "__main__":
    play_story_game()

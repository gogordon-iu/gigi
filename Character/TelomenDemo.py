import sys
sys.path.append('../Resources')

import cv2
from nix.models.TTS import NixTTSInference
from character import Character

# Lookf_for face = Stephanie
# when detect, say "Hello Stephanie, how are you today?"
# then wait for response
# reply to the response. Then say "Goren, are You happy to be here?"
# wait for a thumbs up
# reply: I hope you have a great collaboration together. Bye bye!

# initialize character

fuzzy = Character(child=False, gender='female', activity='TelomenDemo', languages=['en'], full_screen=False)
# use vision to look for face
# fuzzy.vision.run_vision()
# found = fuzzy.vision.look_for(what="name", timeout=60)
# print(f"Found: {found}")

# Say something using tts
fuzzy.viseme.run_viseme(text="Hello Stephanie, how are you today?")

# wait for response using speech recognition

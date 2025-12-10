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

gigi = Character(child=False, gender='female', activity='TelomenDemo', languages=['en'], full_screen=True)
gigi.vision.run_vision()

face_name = "Stephanie"
# use vision to look for face
found = gigi.vision.look_for(what={"name": face_name}, timeout=60)

# Say something using tts
gigi_1 = f"You just saw a person named {face_name}. Say hi and introduce yourself to her. Invite a question about you."
print(f'***** Gigi prompt: {gigi_1} *****')
gigi_message = gigi.conv.get_response_with_tts_sync(gigi_1)
print(f'***** Gigi Response: {gigi_message} *****')
movement_thread = gigi.movement.movement_thread(motor_data="wave_hello")
movement_thread.start()
gigi.viseme.run_viseme(text=gigi_message)
movement_thread.join()

# wait for response using speech recognition
gigi.listen_backchannel()
response_1 = gigi.hearing.texts[-1]
print(f'***** Response: {response_1} *****')

# reply to the response
gigi_2 = f"{face_name} said: {response_1}. Reply to her concisely and then say: Goren, are you happy to be here?"
print(f'***** Gigi prompt: {gigi_2} *****')
gigi_message = gigi.conv.get_response_with_tts_sync(gigi_2)
print(f'***** Gigi Response: {gigi_message} *****')
movement_thread = gigi.movement.movement_thread(motor_data="look_from_side_to_side")
movement_thread.start()
gigi.viseme.run_viseme(text=gigi_message)
movement_thread.join()

# look for thumps up
found = gigi.vision.look_for(what={"gesture": "Thumbs Up"}, timeout=60)

gigi_3 = f"Goren did a thumbs up! Say goodbye to {face_name} and Goren and wish them a great day!"
print(f'***** Gigi prompt: {gigi_3} *****')
gigi_message = gigi.conv.get_response_with_tts_sync(gigi_3)
print(f'***** Gigi Response: {gigi_message} *****')
movement_thread = gigi.movement.movement_thread(motor_data="wave_hello")
movement_thread.start()
gigi.viseme.run_viseme(text=gigi_message)
movement_thread.join()

gigi.vision.cleanup()
gigi.movement.release()

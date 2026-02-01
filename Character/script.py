from character import *
from os.path import exists
from speechDefinitions import audio_path
from faceDefinitions import image_folder_path
import sys
sys.path.append('../Scripts')


# list of parameteres in script nodes
# 'pause': {'before': sec, 'after': sec} -- pauses before and/or after the node
# 'type': 'hear', 'find', 'speak', 'audio', 'move', 'show', 'face'
#
# 'hear': 'words': ['word1', 'word2']
# 'find': 'what': 'face'/'qr', 'timeout': sec -- how long to look before quitting
# 'speak': 'text': text
# 'audio': 'audio': filename -- play a filename.wav
# 'move': 'motors': 'name of sequence' / {'motor1': angle1, 'motor2': angle2}
# 'show': 'caption'/'image'/'video': filename -- shows filename on the screen
# 'face': 'face': 'name of sequence'

class Script:
    def __init__(self, graph=None, character=None, activity=None):
        self.graph = graph.graph
        self.data = graph.data
        self.character = character
        self.activity = activity
        if activity:
            self.character.set_activity(activity)


    def run(self, start_node="start"):
        current_node = start_node
        visited = []  # Keep track of visited nodes

        while current_node != "The End":
            print("current_node:", current_node)
            current_data = self.graph.nodes[current_node]
            edges = self.graph.out_edges(current_node, data=True)
            print("Edges:", edges)
            if len(edges) == 0:
                break

            node_data = {
                'viseme': None,
                'face': None,
                'audio': None,
                'movement': None,
                'caption': None,
                'image': None,
                'video': None
            }

            visited.append(current_node)
            print("Current node data: ", current_data)
            if isinstance(current_data['type'], str):
                current_data['type'] = [current_data['type']]

            current_data['type'] = [k.lower() for k in current_data['type']]
            print("Current node data type: ", current_data['type'])

            # check if there is a pause, before
            if 'pause' in current_data:
                if 'before' in current_data['pause']:
                    self.character.idle(duration=current_data['pause']['before'])

            # current_data["type"] is an array of types. If it is custom, there is only one
            if len(current_data["type"])==0:
                next_node = list(edges)[0][1]
            elif current_data["type"][0] in self.data['types']:
                print("Custom type: ", current_data["type"][0])   
                next_node = self.data['types'][current_data['type'][0]](current_node=current_node, current_data=current_data, data_=self.data)
            # First check if is sensory in nature, since they are unique
            elif "hear" in current_data['type']:
                if self.character:
                    # DEBUG
                    # self.character.lookat_face()
                    if self.character.hearing:
                        if "words" in current_data:                            
                            print("Hear, listening for one of the following: ", current_data["words"])
                            self.character.hearing.words = current_data["words"]
                        elif "silence" in current_data:
                            print("Hear, listening for silence...")
                            self.character.hearing.words = None
                        elif "conversation" in current_data:
                            print("Hear, listening for response ...")
                            self.character.hearing.words = None
                        if 'timeout' in current_data:
                            timeout = current_data['timeout']
                        else:
                            timeout = 10
                        self.character.listen_backchannel(timeout=timeout)
                        # default is timeout
                        output = 'timeout'
                        # if looking for words, check if any of the words are heard
                        if "words" in current_data:
                            # current_data["words"] is a string of words separated by commas
                            cleaned_words = [word.lower().replace('.', ' ').replace(',', ' ').replace('?', ' ').replace('!', ' ').strip() for word in json.loads(current_data["words"])]
                            cleaned_text = [t.lower().replace('.', ' ').replace(',', ' ').replace('?', ' ').replace('!', ' ').strip() for t in self.character.hearing.texts[-1].split()]
                            print(f'heard: {cleaned_text}')
                            print(f'words: {cleaned_words}')
                            for word in cleaned_words:
                                for heard in cleaned_text:
                                    if heard in word:
                                        output = word
                                        break
                                if output != 'timeout':
                                    break
                        else:
                            if len(self.character.hearing.texts) == 0:
                                output = 'timeout'
                            else:
                                output = self.character.hearing.texts[-1]
                        print("hear output: ", output)
                    else:
                        output = current_data["words"][0]
                        print("Simulated hear output: ", output)

                    is_conversation = False
                    response = None
                    if "conversation" in current_data:  # run prompt
                        if '%' in current_data['conversation']:
                            local_var = current_data['conversation'].split('%')[-1].strip()
                            print(f"local_var: {local_var}")
                            if local_var in self.data['types']:
                                print(f"prompt: {self.data['types'][local_var]}")
                                prompt_data = self.data['types'][local_var].replace("RESPONSE", output)
                                print(f"prompt data: {prompt_data}")
                                response = self.character.conv.get_response_with_tts_sync(prompt_data)
                                print(f"response: {response}")
                                is_conversation = True
                    next_node = list(edges)[0][1]   # default is to go to the next node (edge)                    
                    for u, v, data in edges:        # only change if there is a matching edge
                        if is_conversation:
                            if data['label'] in response:
                                next_node = v
                                break
                        else:
                            print(f'debug: {output} in {data["label"]}')
                            if output in data['label']:
                                next_node = v
                                break
            elif "find" in current_data['type']:
                print("Looking for %s..." % current_data['what'])
                if self.character:
                    what = current_data['what']
                    timeout = -1
                    if 'timeout' in current_data:
                        timeout = current_data['timeout']
                    if 'guidance' in current_data:
                        self.character.face.guidance = current_data['guidance']
                    look_what = {what: current_data['data']}
                    found_something = self.character.lookat_something(what=look_what, 
                                                                      timeout=timeout)
                    self.character.face.guidance = None
                    print(f"Found something: {found_something}, details: {found_something['data']}")
                    for u, v, data in edges:
                        if found_something['found'] and data['label'] == 'yes':
                            next_node = v
                            self.graph.nodes[v]['found'] = found_something['data']
                            break
                        if not found_something['found'] and data['label'] == 'no':
                            next_node = v
                            break
                        if found_something['found'] and data['label'] == found_something['data']:
                            next_node = v
                            break
            elif "script" in current_data['type']:
                print("Running script: ", current_data['script'], ". Activity name:", current_data['activity'])
                scriptGraph_package = __import__(current_data['script']['package_name'])
                scriptGraph_instance = getattr(scriptGraph_package, current_data['script']['class_name'])()
                scriptGraph_instance.init_graph()
                script_instance = Script(graph=scriptGraph_instance, character=self.character, activity=current_data['activity'])
                script_instance.run()
                next_node = list(edges)[0][1]

            # then check if it is action-based
            elif self.character:
                if "speak" in current_data['type']:
                    print("Speak: ", current_data['text'])
                    # DEBUG
                    # self.character.lookat_face()
                    # self.character.viseme.run_viseme(current_data['text'])
                    if '%' in current_data['text']:     # real time text was generated
                        local_var = current_data['text'].split('%')[-1].strip()
                        if local_var in self.data['types']:
                            text_data = self.data['types'][local_var]
                        else:
                            text_data = ""
                    else:
                        text_data = current_data['text']
                    node_data['viseme'] = {'text': text_data, 'file': None}
                if "audio" in current_data['type']:
                    print("Audio: ", current_data['audio'])
                    # DEBUG
                    # self.character.lookat_face()
                    # self.character.viseme.run_viseme(current_data['text'])
                    node_data['viseme'] = {'file': current_data['audio'], 'text': None}
                if "move" in current_data['type']:
                    print("Move motors  ", current_data['motors'])
                    node_data['movement'] = current_data['motors']
                    # self.character.movement.move_motors(current_data['motors'])
                if "show" in current_data['type']:
                    if 'caption' in current_data:
                        if '%' in current_data['caption']:
                            local_var = current_data['caption'].split('%')[-1].strip()
                            if local_var in self.data['types']:
                                caption_data = self.data['types'][local_var]
                            else:
                                caption_data = ""
                        else:
                            caption_data = current_data['caption']
                        print("Show caption: ", caption_data)
                        node_data['caption'] = {"caption": caption_data}
                    elif 'image' in current_data:
                        print("Show image: ", current_data['image'])
                        node_data['image'] = {"filename": current_data['image']}
                    elif 'video' in current_data:
                        print("Show video: ", current_data['video'])
                        node_data['video'] = {"filename": current_data['video']}
                    # self.character.face.display_image_file(current_data['image'])
                if "face" in current_data['type']:
                    print("Show face: ", current_data['face'])
                    if isinstance(current_data['face'], str):
                        node_data['face'] = {'sequence': current_data['face']}
                    elif isinstance(current_data['face'], dict):
                        node_data['face'] = current_data['face']
                    else:
                        node_data['face'] = {'parts': current_data['face']}
                    # self.character.face.display_image_file(current_data['image'])

                self.character.run_character(viseme_data=node_data['viseme'],
                                             movement_data=node_data['movement'], 
                                             caption_data=node_data['caption'],
                                             image_data=node_data['image'],
                                             video_data=node_data['video'],
                                             face_data=node_data['face'])
                
                next_node = list(edges)[0][1]
            print("-----")
            if current_node == "The End":
                break
            current_node = next_node

            # check if there is a pause, after
            if 'pause' in current_data:
                if 'after' in current_data['pause']:
                    self.character.idle(duration=current_data['pause']['after'])


            # if len(visited) > 50:
            #     break
        
        if "done_fun" in self.data:
            self.data["done_fun"]()

        if self.character:
            self.character.stop_character()

    def generateAllSpeech(self):
        print("Starting pre-script speech generation.")
        
        script_texts = [attr.get('text') for node, attr in self.graph.nodes(data=True) if attr.get('text')]
        for text in script_texts:
            print("Generating text: ", text)
            if '%' not in text:
                self.character.speech.update_audio_objects(text=text)

        script_audio = [attr.get('audio') for node, attr in self.graph.nodes(data=True) if attr.get('audio')]
        for audio in script_audio:
            print("Generating audio: ", audio)
            self.character.speech.update_audio_objects(file=audio)

    def check_assets(self):
        missing = False
        script_assets = []
        activity_path = f"../Assets/{self.character.activity_name}/"
        for node, attr in self.graph.nodes(data=True):
            if attr.get('audio'):
                audio_file = attr.get('audio')
                if not exists(audio_file):
                    audio_file = activity_path + 'audio/' + audio_file.split('/')[-1]
                if not exists(audio_file):
                    audio_file = audio_path + audio_file.split('/')[-1]
                if not exists(audio_file):
                    print("Missing audio file: ", audio_file)
                    missing = True
            if attr.get('image'):
                image_file = attr.get('image')
                if not exists(image_file):
                    image_file = activity_path + 'face/' + image_file.split('/')[-1]
                if not exists(image_file):
                    image_file = image_folder_path + image_file.split('/')[-1]
                if not exists(image_file):
                    print("Missing image file: ", image_file)
                    missing = True
            if attr.get('video'):
                video_file = attr.get('video')
                if not exists(video_file):
                    video_file = activity_path + 'face/' + video_file.split('/')[-1]
                if not exists(video_file):
                    video_file = image_folder_path + video_file.split('/')[-1]
                if not exists(video_file):
                    print("Missing video file: ", video_file)
                    missing = True
        if not missing:
            print("All assets are present.")


if __name__ == "__main__":
    # fuzzy = Character()
    pass

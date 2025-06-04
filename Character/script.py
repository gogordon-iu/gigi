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
# 'show': 'text'/'image'/'video': filename -- shows filename on the screen
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
            if current_data["type"][0] in self.data['types']:
                print("Custom type: ", current_data["type"][0])   
                next_node = self.data['types'][current_data['type'][0]](current_node=current_node, current_data=current_data, data_=self.data)
            # First check if is sensory in nature, since they are unique
            elif "hear" in current_data['type']:
                print("Hear, listening for one of the following: ", current_data["words"])
                if not IS_ROBOT:
                    break
                if self.character:
                    # DEBUG
                    # self.character.lookat_face()
                    if self.character.hearing:
                        self.character.hearing.words = current_data["words"]
                        self.character.listen_backchannel()
                        output = self.character.hearing.texts[-1]
                        print("hear output: ", output)
                        for u, v, data in edges:
                            if data['label'] == output:
                                next_node = v
                                break
            elif "find" in current_data['type']:
                print("Looking for %s..." % current_data['what'])
                if self.character:
                    what = current_data['what']
                    timeout = -1
                    if 'timeout' in current_data:
                        timeout = current_data['timeout']                      
                    found_something = self.character.lookat_something(what=what, 
                                                                      timeout=timeout)
                    for u, v, data in edges:
                        if found_something and data['label'] == 'yes':
                            next_node = v
                            self.graph.nodes[v]['found'] = self.character.vision.found[what]
                            break
                        if not found_something and data['label'] == 'no':
                            next_node = v
                            break
                        if found_something and data['label'] in self.character.vision.found[what].keys():
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
                    node_data['viseme'] = {'text': current_data['text'], 'file': None}
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
                        print("Show caption: ", current_data['caption'])
                        node_data['caption'] = {"caption": current_data['caption']}
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

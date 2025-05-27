import os
from faceDefinitions import *
from PIL import Image
from characterDefinitions import IS_ROBOT, base_assets_path
if IS_ROBOT:
    from mpv import MPV
import math
IMAGE_OPTION = "pygame"
if IMAGE_OPTION == "pygame":
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1" 
    import pygame
elif IMAGE_OPTION == "cv":
    from screeninfo import get_monitors
    import cv2
    import numpy as np
import time
import threading

class Face():
    def __init__(self, character="fuzzy", full_screen=True, activity=None):
        print("Initiliazing face ...")
        self.character = characters[character]
        self.show_face = True
        self.set_activity(activity_name=activity)
        
        # init screen options
        if IMAGE_OPTION == "pygame":
            pygame.init()

            # Set up the full-screen display
            self.infoObject = pygame.display.Info()
            if full_screen:
                self.screen_size = (self.infoObject.current_w, self.infoObject.current_h)
                self.screen = pygame.display.set_mode(self.screen_size, pygame.FULLSCREEN)
            else:
                self.screen_size = (self.infoObject.current_w/2, self.infoObject.current_h/2)
                self.screen = pygame.display.set_mode(self.screen_size)
        elif IMAGE_OPTION == "cv":
            screen = get_monitors()[0]
            screen_width, screen_height = screen.width, screen.height
            if full_screen:
                cv2.namedWindow("Image Viewer", cv2.WND_PROP_FULLSCREEN)
                self.screen_size = (screen_width, screen_height)
            else:
                cv2.namedWindow("Image Viewer", cv2.WINDOW_NORMAL)
                self.screen_size = (int(screen_width / 2), int(screen_height / 2))
            cv2.resizeWindow("Image Viewer", self.screen_size[0], self.screen_size[1])

        self.initialize_character(save=True)

    def set_activity(self, activity_name):
        self.activity = activity_name
        if self.activity:
            self.activity_face_path = base_assets_path + self.activity + "/face/"
        else:
            self.activity_face_path = base_assets_path + "face/"
        if not os.path.exists(self.activity_face_path):
            os.makedirs(self.activity_face_path)


    def initialize_character(self, save=False):
        self.characterfolder_path = image_folder_path + self.character["name"] + "/"
        if save:
            if not os.path.exists(self.characterfolder_path):
                os.mkdir(self.characterfolder_path)
                                
            # global initialization
            for part in global_parts:
                if not os.path.exists(self.characterfolder_path + part):
                    os.mkdir(self.characterfolder_path + part)
        
        # character variables
        image_name = image_folder_path + self.character["base_image_name"]
        self.character["images"] = {}
        
        # go over all the data in the sequence
        for part, part_sequence in self.character["part_sequence"].items():
            part_slice = self.character["part_slices"][part]
            self.character["images"][part] = {}
            for part_data in part_sequence:
                self.character["images"][part][part_data[0]] = {}
                for i in part_data[1]:
                    file_name = self.characterfolder_path + part + "/" + part_data[0]
                    file_name = f"{file_name}_slice_{i}.png"

                    if save:
                        # Open the image
                        image = Image.open(f"{image_name}{i:03}.png")
                        # Get the dimensions of the image
                        width, height = image.size
                        sliced_image = image.crop((0, math.floor(height * part_slice[0]), width, math.floor(height * part_slice[1])))
                        sliced_image.save(f"{file_name}")
                    else:
                        sliced_image = Image.open(f"{file_name}")
                    self.character["images"][part][part_data[0]][str(i)] = sliced_image
        return self.character

    def set_face(self, parts_selected):
        character = self.character
        # default
        images = {}
        for part in global_parts:
            images[part] = None
        for part, sequence in parts_selected.items():
            images[part] = character["images"][part][sequence[0]][sequence[1]]
        for part in global_parts:
            if not images[part]:
                images[part] = character["images"][part]["idle"]["1"]
                
        # Get the maximum width among all images
        max_width = max(img.width for img in images.values())

        # Resize images to have the same width (optional)
        for part in global_parts:
            images[part] = images[part].resize((max_width, images[part].height))

        # Calculate the total height of the stacked images
        total_height = sum(img.height for img in images.values())

        # Create a new blank image with the maximum width and total height
        stacked_image = Image.new('RGB', (max_width, total_height), color='white')

        # Paste each image onto the new image
        y_offset = 0
        for part in global_parts:
            stacked_image.paste(images[part], (0, y_offset))
            y_offset += images[part].height

        if IMAGE_OPTION == "pygame":
            # convert to pygame_image
            pygame_image = pygame.image.fromstring(stacked_image.tobytes(), stacked_image.size, stacked_image.mode)
            return pygame_image
        elif IMAGE_OPTION == "cv":
            cv_image = np.array(stacked_image)
            return cv_image

    def display_face(self, image_):
        # Scale the image to fill the screen
        if IMAGE_OPTION == "pygame":
            image_ = pygame.transform.scale(image_, self.screen_size)
            # Blit the image to the screen
            self.screen.blit(image_, (0, 0))

            # Update the display
            pygame.display.flip()
        elif IMAGE_OPTION == "cv":
            image_ = cv2.resize(image_, self.screen_size, interpolation=cv2.INTER_LINEAR)
            cv2.imshow("Image Viewer", image_)

    def get_sequence_length(self, sequence):
        max_length = 0
        for part, part_data in sequence.items():
            max_length = max(max_length, len(part_data[1]))
        return max_length

    def generate_face(self, parts_selected, stop_event=None, stop_condition=None, delay=0.5):
        if self.show_face:
            max_length = self.get_sequence_length(parts_selected)
            
            for i in range(max_length):
                start_time = time.time()    
                face = {}
                for part, part_data in parts_selected.items():
                    if i < len(part_data[1]):
                        face[part] = (part_data[0], part_data[1][i])
                face_image = self.set_face(face)
                self.display_face(face_image)

                current_time = time.time() - start_time
                left_delay = 0
                if current_time < delay:
                    left_delay = delay - current_time
                if left_delay > 0:
                    if IMAGE_OPTION == "pygame":
                        time.sleep(left_delay)
                    elif IMAGE_OPTION == "cv":
                        cv2.waitKey(int(left_delay * 1000))
            
                if stop_event:
                    if stop_event.is_set():
                        break

        # if the stop condition is the speech, send the stop event
        if stop_condition is not None and stop_event is not None:
            if "face" in stop_condition:
                stop_event.set()

    def generate_repetition(self, sequence, duration, delay=0.1):
        sequence_duration = self.get_sequence_length(sequence) * delay
        repetition = int(duration / sequence_duration)
        for i in range(repetition):
            self.generate_face(parts_selected=sequence)

    def sequence_thread(self, face_sequence_name="blink", face_sequence=None):
        if face_sequence is None:
            face_sequence = basic_sequences[face_sequence_name]
        stop_event = threading.Event()
        t = threading.Thread(target=self.generate_face, args=(face_sequence, stop_event, None, 0.1))
        return t
    
    def run_sequence_thread(self, face_sequence_name="blink", face_sequence=None):
        face_thread = self.sequence_thread(face_sequence_name, face_sequence)
        face_thread.start()
        face_thread.join()

    def run_sequence(self, face_sequence_name="blink", face_sequence=None):
        if face_sequence is None:
            face_sequence = basic_sequences[face_sequence_name]
        self.generate_face(parts_selected=face_sequence, delay=0.1)

    def display_text(self, text=None):    
        if text:
            # Create a blank image with white background
            font = pygame.font.Font(None, 36)  # Default font with size 36
            text_surface = font.render(text, True, (0, 0, 0))  # Black text
            text_width, text_height = text_surface.get_size()
            image_width, image_height = self.screen_size
            background = pygame.Surface((image_width, image_height))
            background.fill((255, 255, 255))  # White background

            # Center the text on the screen
            text_x = (image_width - text_width) // 2
            text_y = (image_height - text_height) // 2
            background.blit(text_surface, (text_x, text_y))

            self.show_face = False
            self.display_face(background)            
        else:
            self.show_face = True

    def display_image_file(self, filename=None):
        if filename:
            print("FACE DEBUG: ", filename)
            if not os.path.exists(filename):
                filename = self.activity_face_path + filename.split('/')[-1]
            print("FACE DEBUG: ", filename)
            if not os.path.exists(filename):
                filename = image_folder_path + filename.split('/')[-1]
            print("FACE DEBUG: ", filename)
            if os.path.exists(filename):
                print("FACE DEBUG FOUDN: ", filename)
                pil_image = Image.open(filename)
                mode = pil_image.mode
                size = pil_image.size
                data = pil_image.tobytes()

                # Create a Pygame Surface from the PIL image data
                image = pygame.image.fromstring(data, size, mode)
                self.show_face = False
                self.display_face(image)
        else:
            self.show_face = True

    def combine_seuqences(self, sequences=None):
        def densify_sequence(seq, delay, min_delay):
            """
            Repeats each element in seq (delay seconds apart) so that the time resolution
            is the minimal delay min_delay.
            
            For each event, repeat it int(delay / min_delay) times.
            """
            repeat_factor = int(delay / min_delay)
            return [item for item in seq for _ in range(repeat_factor)]
        
        min_delay = min([seq[0] for seq in sequences])

        combined_sequence = {}
        for seq in sequences:
            seq_delay = seq[0]
            for part, s in seq[1].items():
                if part not in combined_sequence:
                    combined_sequence[part] = (s[0], densify_sequence(seq=s[1], delay=seq_delay, min_delay=min_delay))
        return combined_sequence, min_delay


    def display_video_file(self, filename=None):
        # sudo apt update
        # sudo apt install mpv libmpv-dev        # packaged for Armbian/Ubuntu
        # pip install python-mpv                 # tiny ctypes wrapper
        if filename and IS_ROBOT:
            if not os.path.exists(filename):
                filename = self.activity_face_path + filename.split('/')[-1]
            if not os.path.exists(filename):
                filename = image_folder_path + filename.split('/')[-1]
            if os.path.exists(filename):
                player = MPV(fullscreen=True)          # create a player in FS mode
                player.play(filename)                  # starts video + audio immediately
                player.wait_for_playback()             # script blocks until it finishes
        else:
            self.show_face = True
            
if __name__ == "__main__":
    face = Face()
    # face.initialize_character()
    # # face.generate_face(parts_selected=basic_sequences["blink"])
    # face.generate_face(parts_selected=basic_sequences["look_right"])
    # face.generate_face(parts_selected=basic_sequences["idle"])
    # face.generate_face(parts_selected=basic_sequences["look_down"])
    # face.generate_face(parts_selected=basic_sequences["smile"])
    # face.run_sequence()

    c = face.combine_seuqences(sequences=[[0.1, basic_sequences["talk"]], [0.5, basic_sequences["look_left"]]])
    print(c)

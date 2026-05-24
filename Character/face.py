import os
from faceDefinitions import *
from PIL import Image
from characterDefinitions import IS_ROBOT, base_assets_path
if IS_ROBOT:
    from mpv import MPV
import math
IMAGE_OPTION = "cv"
if IMAGE_OPTION == "pygame":
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1" 
    import pygame
elif IMAGE_OPTION == "cv":
    from screeninfo import get_monitors
    import cv2
    import numpy as np
    import subprocess

import time
import threading


class Face():
    def __init__(self, character="fuzzy", full_screen=True, activity=None):
        print("Initiliazing face ...")
        self.IMAGE_OPTION = IMAGE_OPTION
        self.character = characters[character]
        self.show_face = True
        self.preloaded_image = None
        self.guidance = None
        self.guidance_images = {}
        self.set_activity(activity_name=activity)
        
        # init screen options
        if IMAGE_OPTION == "pygame":
            pygame.init()
            # Set up the full-screen display
            self.infoObject = pygame.display.Info()
            if full_screen:
                self.screen_size = (self.infoObject.current_w, self.infoObject.current_h)
                flags = pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE
                # flags = pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE
                self.screen = pygame.display.set_mode(self.screen_size, flags)
            else:
                self.screen_size = (self.infoObject.current_w/2, self.infoObject.current_h/2)
                self.screen = pygame.display.set_mode(self.screen_size)
        elif IMAGE_OPTION == "cv":
            screen = get_monitors()[0]
            screen_width, screen_height = screen.width, screen.height
            self.win_name = "face_window"
            if full_screen:
                cv2.namedWindow(self.win_name, cv2.WND_PROP_FULLSCREEN)
                # cv2.setWindowProperty(self.win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                self.screen_size = (screen_width, screen_height)
                
                if IS_ROBOT:
                    # show an initial frame so the window appears
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.imshow(self.win_name, frame)
                    cv2.waitKey(1)

                    # give WM a tiny moment to map the window
                    time.sleep(0.12)

                    win = self.win_name

                    subprocess.Popen(["wmctrl", "-a", self.win_name])  # bring to front
                    subprocess.Popen(["wmctrl", "-r", self.win_name, "-b", "add,fullscreen"])
                    subprocess.Popen([
                        "xprop", "-name", self.win_name,
                        "-f", "_MOTIF_WM_HINTS", "32c",
                        "-set", "_MOTIF_WM_HINTS", "0x2, 0x0, 0x0, 0x0, 0x0"
                    ])
                    # Hide cursor (non-blocking)
                    subprocess.Popen(["unclutter", "-grab", "-idle", "0"])
            else:
                cv2.namedWindow(self.win_name, cv2.WINDOW_NORMAL)
                self.screen_size = (int(screen_width / 2), int(screen_height / 2))
            cv2.resizeWindow(self.win_name, self.screen_size[0], self.screen_size[1])
        self.initialize_character(save=True)

    def stop_face(self):
        if IMAGE_OPTION == "pygame":
            pygame.quit()
        elif IMAGE_OPTION == "cv":
            cv2.destroyAllWindows()

    def set_activity(self, activity_name):
        self.activity = activity_name
        if self.activity:
            self.activity_face_path = base_assets_path + self.activity + "/face/"
        else:
            self.activity_face_path = base_assets_path + "face/"
        if not os.path.exists(self.activity_face_path):
            os.makedirs(self.activity_face_path)

        # check if there are guidance images for this activity
        guidance_path = self.activity_face_path + "guidance/"
        if os.path.exists(guidance_path):
            for file in os.listdir(guidance_path):
                if file.endswith(('.png', '.jpg', '.jpeg')):
                    guidance_name = file.split('.')[0]
                    img = Image.open(guidance_path + file)
                    if IMAGE_OPTION == "cv":
                        img_array = np.array(img.convert("RGB"))
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    elif IMAGE_OPTION == "pygame":
                        img_array = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                    self.guidance_images[guidance_name] = img_array

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
                    
                    if self.IMAGE_OPTION == "pygame":
                        pg_img = pygame.image.fromstring(sliced_image.tobytes(), sliced_image.size, sliced_image.mode).convert()
                        self.character["images"][part][part_data[0]][str(i)] = pg_img
                    elif self.IMAGE_OPTION == "cv":
                        cv_img = np.array(sliced_image.convert("RGB"))
                        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
                        self.character["images"][part][part_data[0]][str(i)] = cv_img
                    else:
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
            if images[part] is None:
                images[part] = character["images"][part]["idle"]["1"]
                
        if self.IMAGE_OPTION == "cv":
            # Direct numpy vertical concatenation is extremely fast!
            if isinstance(images["Eyes"], np.ndarray):
                return np.concatenate([images[part] for part in global_parts], axis=0)
            else:
                # Fallback for PIL Images
                cv_images = []
                for part in global_parts:
                    cv_img = np.array(images[part].convert("RGB"))
                    cv_images.append(cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR))
                return np.concatenate(cv_images, axis=0)
                
        elif self.IMAGE_OPTION == "pygame":
            # Direct pygame surface blitting
            if not isinstance(images["Eyes"], Image.Image):
                width = images["Eyes"].get_width()
                total_height = sum(images[part].get_height() for part in global_parts)
                stacked_surface = pygame.Surface((width, total_height))
                y_offset = 0
                for part in global_parts:
                    stacked_surface.blit(images[part], (0, y_offset))
                    y_offset += images[part].get_height()
                return stacked_surface
            else:
                # Fallback for PIL Images
                max_width = max(img.width for img in images.values())
                total_height = sum(img.height for img in images.values())
                stacked_image = Image.new('RGB', (max_width, total_height), color='white')
                y_offset = 0
                for part in global_parts:
                    stacked_image.paste(images[part], (0, y_offset))
                    y_offset += images[part].height
                return pygame.image.fromstring(stacked_image.tobytes(), stacked_image.size, stacked_image.mode)


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
            cv2.imshow(self.win_name, image_)
            cv2.waitKey(1)

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
                
                if self.guidance in self.guidance_images:
                    guidance_img = self.guidance_images[self.guidance]
                    h, w = face_image.shape[:2]
                    guidance_h, guidance_w = guidance_img.shape[:2]
                    scale_w = int(w * 0.2)
                    scale_h = int(guidance_h * scale_w / guidance_w)
                    guidance_resized = cv2.resize(guidance_img, (scale_w, scale_h))
                    face_image[h - scale_h:h, 0:scale_w] = guidance_resized
                    
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
            if IMAGE_OPTION == "pygame":
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
            elif IMAGE_OPTION == "cv":
                # Create a blank image with white background
                image_width, image_height = self.screen_size
                background = np.ones((image_height, image_width, 3), dtype=np.uint8) * 255  # White background

                # Set font and scale
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 1.5
                font_thickness = 2

                # Get text size
                (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, font_thickness)

                # Center the text on the screen
                text_x = (image_width - text_width) // 2
                text_y = (image_height + text_height) // 2

                # Put the text on the image
                cv2.putText(background, text, (text_x, text_y), font, font_scale, (0, 0, 0), font_thickness, cv2.LINE_AA)

                self.show_face = False
                self.display_face(background)

        else:
            self.show_face = True

    def _resolve_image_path(self, filename):
        if not os.path.exists(filename):
            filename = self.activity_face_path + filename.split('/')[-1]
        if not os.path.exists(filename):
            filename = image_folder_path + filename.split('/')[-1]
        return filename if os.path.exists(filename) else None

    def preload_image(self, filename):
        """Load and decode image on any thread — stores result for main-thread display."""
        self.preloaded_image = None
        path = self._resolve_image_path(filename)
        if not path:
            print(f"Image not found: {filename}")
            return
        try:
            pil_image = Image.open(path)
            if IMAGE_OPTION == "cv":
                if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and pil_image.info.get("transparency") is not None):
                    rgba = pil_image.convert("RGBA")
                    alpha = rgba.split()[-1]
                    background = Image.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=alpha)
                    image = np.array(background)
                else:
                    image = np.array(pil_image.convert("RGB"))
                self.preloaded_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            elif IMAGE_OPTION == "pygame":
                mode, size, data = pil_image.mode, pil_image.size, pil_image.tobytes()
                self.preloaded_image = pygame.image.fromstring(data, size, mode)
            print(f"Image preloaded: {path}")
        except Exception as e:
            print(f"Image preload error: {e}")

    def display_image_file(self, filename=None):
        if filename:
            self.preload_image(filename)
            if self.preloaded_image is not None:
                self.show_face = False
                self.display_face(self.preloaded_image)
        else:
            self.preloaded_image = None
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
            

    def add_guidance(self, guidance=None):
        if guidance and os.path.exists(guidance):
            guidance_img = Image.open(guidance)
            pil_image = Image.open(guidance)
            
            if IMAGE_OPTION == "cv":
                if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and pil_image.info.get("transparency") is not None):
                    rgba = pil_image.convert("RGBA")
                    alpha = rgba.split()[-1]
                    background = Image.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=alpha)
                    guidance_array = np.array(background)
                else:
                    guidance_array = np.array(pil_image.convert("RGB"))
                guidance_array = cv2.cvtColor(guidance_array, cv2.COLOR_RGB2BGR)
            elif IMAGE_OPTION == "pygame":
                guidance_array = pygame.image.fromstring(pil_image.tobytes(), pil_image.size, pil_image.mode)
            
            self.show_face = False
            self.guidance_image = guidance_array
            self.guidance_enabled = True
        else:
            self.guidance_enabled = False

if __name__ == "__main__":
    face = Face()
    face.initialize_character()
    # # face.generate_face(parts_selected=basic_sequences["blink"])
    # face.generate_face(parts_selected=basic_sequences["look_right"])
    # face.generate_face(parts_selected=basic_sequences["idle"])
    # face.generate_face(parts_selected=basic_sequences["look_down"])
    # face.generate_face(parts_selected=basic_sequences["smile"])
    # face.run_sequence()

    # c = face.combine_seuqences(sequences=[[0.1, basic_sequences["talk"]], [0.5, basic_sequences["look_left"]]])
    # print(c)
    face.set_activity(activity_name="Demo")
    face.display_image_file(filename="../Assets/Demo/face/cobot.jpg")
    face.display_text(text="Hello, I am Gigi!")
    cv2.waitKey(2000)

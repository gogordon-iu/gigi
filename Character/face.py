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
        self.face_running = True
        self.lock = threading.Lock()
        self.rendering_sequence = False
        self.face_update_counter = 0
        self.last_rendered_counter = 0
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
                cv2.namedWindow(self.win_name, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
                self.screen_size = (screen_width, screen_height)
                
                if IS_ROBOT:
                    # show an initial frame so the window appears
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.imshow(self.win_name, frame)
                    cv2.waitKey(1)

                    # give WM a tiny moment to map the window
                    time.sleep(0.12)
                    
                    # Set fullscreen after mapping (commented out to prevent screen blanking / HDMI signal loss on Orange Pi)
                    # cv2.setWindowProperty(self.win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

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
                    cv2.setWindowProperty(self.win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.namedWindow(self.win_name, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
                self.screen_size = (int(screen_width / 2), int(screen_height / 2))
                cv2.resizeWindow(self.win_name, self.screen_size[0], self.screen_size[1])
        self.initialize_character(save=True)
        
        # Reading Fluency Karaoke variables
        self.reading_fluency_active = False
        self.reading_passage_words = []
        self.reading_current_word_idx = 0
        self.reading_word_states = []
        self.reading_last_wrong_heard = None
        self.last_face_image = None
        self.reading_status = "idle"
        
        # Initialize visual feedback icons
        self._feedback_state = None
        self.overlay_text = None
        self.feedback_icons = {}
        try:
            ear_path = base_assets_path + "face/listening_ear.png"
            
            if os.path.exists(ear_path):
                img = Image.open(ear_path)
                if self.IMAGE_OPTION == "cv":
                    img_cv = np.array(img.convert("RGBA"))
                    self.feedback_icons["listening"] = cv2.cvtColor(img_cv, cv2.COLOR_RGBA2BGRA)
                elif self.IMAGE_OPTION == "pygame":
                    self.feedback_icons["listening"] = pygame.image.load(ear_path).convert_alpha()
                    
            print(f"[Face] Loaded visual feedback icons: {list(self.feedback_icons.keys())}")
        except Exception as e:
            print(f"[Face] Error loading visual feedback icons: {e}")

        # Render the initial idle face immediately so the screen is not left black during startup
        idle_face = {part: ("idle", "1") for part in global_parts}
        face_image = self.set_face(idle_face)
        self.display_face(face_image)

    @property
    def feedback_state(self):
        return self._feedback_state

    @feedback_state.setter
    def feedback_state(self, val):
        self._feedback_state = val
        # Increment update counter to signal main thread to redraw (safe across threads)
        self.face_update_counter = getattr(self, 'face_update_counter', 0) + 1

    def stop_face(self):
        self.show_face = False
        self.face_running = False
        if IMAGE_OPTION == "pygame":
            try:
                pygame.quit()
            except Exception as e:
                print(f"[Face] Warning: Error during pygame quit: {e}")
        elif IMAGE_OPTION == "cv":
            try:
                with self.lock:
                    cv2.destroyAllWindows()
            except Exception as e:
                print(f"[Face] Warning: Error during cv2 destroyAllWindows: {e}")

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
        import cv2
        if not getattr(self, 'face_running', True):
            return
        self.last_face_image = image_
        self.face_update_counter += 1
        
        # Scale/Draw the image to fill the screen
        if IMAGE_OPTION == "pygame":
            try:
                W, H = self.screen_size
                image_resized = pygame.transform.scale(image_, self.screen_size)
                
                # Overlay feedback state on the face
                if self.feedback_state in self.feedback_icons:
                    icon = self.feedback_icons[self.feedback_state]
                    scale_h = int(H * 0.15)
                    scale_w = int(icon.get_width() * scale_h / icon.get_height())
                    icon_resized = pygame.transform.smoothscale(icon, (scale_w, scale_h))
                    # Position it on top-right to avoid bottom overlay area
                    image_resized.blit(icon_resized, (W - scale_w - 10, 10))
                
                if getattr(self, 'guidance', None) in self.guidance_images:
                    if self.feedback_state not in self.feedback_icons:
                        guidance_img = self.guidance_images[self.guidance]
                        gh, gw = guidance_img.get_height(), guidance_img.get_width()
                        scale_w = int(W * 0.2)
                        scale_h = int(gh * scale_w / gw)
                        guidance_resized = pygame.transform.smoothscale(guidance_img, (scale_w, scale_h))
                        image_resized.blit(guidance_resized, (0, H - scale_h))

                if getattr(self, 'reading_fluency_active', False):
                    self.draw_reading_fluency_overlay_pygame(image_resized)
                
                if getattr(self, 'overlay_text', None):
                    text = str(self.overlay_text)
                    font = pygame.font.SysFont("Arial", 42, bold=True)
                    lines = text.split("\n")
                    surfaces = [font.render(line, True, (255, 255, 255)) for line in lines]
                    
                    max_w = max(surf.get_width() for surf in surfaces)
                    total_h = sum(surf.get_height() for surf in surfaces) + (len(surfaces) - 1) * 8
                    
                    pad_x = 20
                    pad_y = 15
                    card_w = max_w + 2 * pad_x
                    card_h = total_h + 2 * pad_y
                    margin = 15
                    x0 = (W - card_w) // 2
                    y0 = (H * 2 // 3) - card_h - margin if getattr(self, 'reading_fluency_active', False) else H - card_h - margin
                    
                    card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                    card_surf.fill((20, 30, 70, 204))
                    pygame.draw.rect(card_surf, (100, 200, 255), (0, 0, card_w, card_h), 2, border_radius=5)
                    
                    current_y = pad_y
                    for surf in surfaces:
                        line_x = pad_x + (max_w - surf.get_width()) // 2
                        card_surf.blit(surf, (line_x, current_y))
                        current_y += surf.get_height() + 8
                        
                    image_resized.blit(card_surf, (x0, y0))
                    
                # Overlay camera feed if requested and vision is running
                if getattr(self, 'show_camera_feed', False) and getattr(self, 'vision', None) is not None:
                    if self.vision.running:
                        cam_frame = self.vision.get_latest_frame()
                        if cam_frame is not None:
                            import cv2
                            rgb_frame = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
                            cam_h, cam_w = rgb_frame.shape[:2]
                            scale_w = int(W * 0.25)
                            scale_h = int(cam_h * scale_w / cam_w)
                            rgb_resized = cv2.resize(rgb_frame, (scale_w, scale_h))
                            pg_cam = pygame.image.fromstring(rgb_resized.tobytes(), (scale_w, scale_h), "RGB")
                            image_resized.blit(pg_cam, (W - scale_w, H - scale_h))
                    
                if getattr(self, 'face_running', True):
                    self.screen.blit(image_resized, (0, 0))
                    pygame.display.flip()
            except Exception as e:
                print(f"[Face] Warning: Error during pygame display update: {e}")
            
        elif IMAGE_OPTION == "cv":
            import threading
            if threading.current_thread() is not threading.main_thread():
                return
            try:
                W, H = self.screen_size
                image_resized = cv2.resize(image_, self.screen_size, interpolation=cv2.INTER_LINEAR)
                
                # Overlay feedback state on the face
                if self.feedback_state in self.feedback_icons:
                    icon = self.feedback_icons[self.feedback_state]
                    scale_h = int(H * 0.15)
                    scale_w = int(icon.shape[1] * scale_h / icon.shape[0])
                    icon_resized = cv2.resize(icon, (scale_w, scale_h))
                    icon_rgb = icon_resized[:, :, :3]
                    icon_alpha = icon_resized[:, :, 3] / 255.0
                    margin = 10
                    # Position it on top-right to avoid bottom overlay area
                    roi_y0 = margin
                    roi_y1 = margin + scale_h
                    roi_x0 = W - scale_w - margin
                    roi_x1 = W - margin
                    roi = image_resized[roi_y0:roi_y1, roi_x0:roi_x1]
                    for c in range(3):
                        roi[:, :, c] = (icon_alpha * icon_rgb[:, :, c] + (1 - icon_alpha) * roi[:, :, c]).astype(np.uint8)
                    image_resized[roi_y0:roi_y1, roi_x0:roi_x1] = roi
                
                if getattr(self, 'guidance', None) in self.guidance_images:
                    if self.feedback_state not in self.feedback_icons:
                        guidance_img = self.guidance_images[self.guidance]
                        gh, gw = guidance_img.shape[:2]
                        scale_w = int(W * 0.2)
                        scale_h = int(gh * scale_w / gw)
                        try:
                            guidance_resized = cv2.resize(guidance_img, (scale_w, scale_h))
                            image_resized[H - scale_h:H, 0:scale_w] = guidance_resized
                        except Exception as e:
                            print(f"[Face] Warning: Error resizing guidance image in display_face: {e}")

                if getattr(self, 'reading_fluency_active', False):
                    self.draw_reading_fluency_overlay_cv(image_resized)
                
                if getattr(self, 'overlay_text', None):
                    text = str(self.overlay_text)
                    font = cv2.FONT_HERSHEY_DUPLEX
                    font_scale = 1.2
                    thickness = 2
                    
                    lines = text.split("\n")
                    line_sizes = [cv2.getTextSize(line, font, font_scale, thickness) for line in lines]
                    
                    max_w = max(size[0][0] for size in line_sizes)
                    total_h = sum(size[0][1] for size in line_sizes) + (len(lines) - 1) * 12
                    
                    pad_x = 20
                    pad_y = 15
                    card_w = max_w + 2 * pad_x
                    card_h = total_h + 2 * pad_y
                    margin = 15
                    x0 = (W - card_w) // 2
                    y0 = (H * 2 // 3) - card_h - margin if getattr(self, 'reading_fluency_active', False) else H - card_h - margin
                    x1 = x0 + card_w
                    y1 = y0 + card_h
                    
                    # Ensure coordinates are within screen boundary
                    x0 = max(0, min(W - 1, x0))
                    y0 = max(0, min(H - 1, y0))
                    x1 = max(0, min(W - 1, x1))
                    y1 = max(0, min(H - 1, y1))
                    
                    card_w = x1 - x0
                    card_h = y1 - y0
                    
                    if card_w > 0 and card_h > 0:
                        roi = image_resized[y0:y1, x0:x1]
                        card_bg = np.zeros_like(roi)
                        card_bg[:] = (70, 30, 20)
                        alpha = 0.8
                        roi_blended = cv2.addWeighted(roi, 1 - alpha, card_bg, alpha, 0)
                        cv2.rectangle(roi_blended, (0, 0), (card_w, card_h), (255, 200, 100), 2, lineType=cv2.LINE_AA)
                        
                        current_y = pad_y
                        for line, ((w, h), baseline) in zip(lines, line_sizes):
                            current_y += h
                            # Center each line inside the card
                            line_x = pad_x + (max_w - w) // 2
                            # Ensure we don't draw outside the blended card boundary
                            if current_y <= card_h - 5:
                                cv2.putText(roi_blended, line, (line_x, current_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                            current_y += 12 # spacing
                        image_resized[y0:y1, x0:x1] = roi_blended
                
                # Overlay camera feed if requested and vision is running
                if getattr(self, 'show_camera_feed', False) and getattr(self, 'vision', None) is not None:
                    if self.vision.running:
                        cam_frame = self.vision.get_latest_frame()
                        if cam_frame is not None:
                            import cv2
                            cam_h, cam_w = cam_frame.shape[:2]
                            scale_w = int(W * 0.25)
                            scale_h = int(cam_h * scale_w / cam_w)
                            cam_resized = cv2.resize(cam_frame, (scale_w, scale_h))
                            image_resized[H - scale_h:H, W - scale_w:W] = cam_resized
                
                if getattr(self, 'face_running', True):
                    with self.lock:
                        cv2.imshow(self.win_name, image_resized)
                        cv2.waitKey(1)
            except Exception as e:
                print(f"[Face] Warning: Error during cv2 display update: {e}")

    def get_sequence_length(self, sequence):
        max_length = 0
        for part, part_data in sequence.items():
            max_length = max(max_length, len(part_data[1]))
        return max_length

    def generate_face(self, parts_selected, stop_event=None, stop_condition=None, delay=0.5, start_time=None):
        if getattr(self, 'show_face', True):
            self.rendering_sequence = True
            try:
                max_length = self.get_sequence_length(parts_selected)
                
                i = 0
                while i < max_length:
                    if not getattr(self, 'show_face', True):
                        break
                    
                    if start_time is not None:
                        # Synchronize index based on real elapsed time
                        elapsed = time.time() - start_time
                        i = int(elapsed / delay)
                        if i >= max_length:
                            break
                    
                    frame_start_time = time.time()    
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
                        try:
                            guidance_resized = cv2.resize(guidance_img, (scale_w, scale_h))
                            face_image[h - scale_h:h, 0:scale_w] = guidance_resized
                        except Exception as e:
                            print(f"[Face] Warning: Error resizing guidance image in generate_face: {e}")
                        
                    self.display_face(face_image)

                    if start_time is not None:
                        # Wait until the next frame time slot
                        next_frame_time = start_time + (i + 1) * delay
                        left_delay = next_frame_time - time.time()
                    else:
                        current_time = time.time() - frame_start_time
                        left_delay = delay - current_time
                    
                    if left_delay > 0:
                        if IMAGE_OPTION == "pygame":
                            time.sleep(left_delay)
                        elif IMAGE_OPTION == "cv":
                            try:
                                if getattr(self, 'show_face', True):
                                    import threading
                                    if threading.current_thread() is not threading.main_thread():
                                        time.sleep(left_delay)
                                    else:
                                        with self.lock:
                                            cv2.waitKey(int(left_delay * 1000))
                            except Exception as e:
                                print(f"[Face] Warning: Error during generate_face waitKey: {e}")
                
                    if start_time is None:
                        i += 1

                    if stop_event:
                        if stop_event.is_set():
                            break
            finally:
                self.rendering_sequence = False

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

    def update_reading_fluency(self, active, passage_words=None, current_word_idx=None, word_states=None, last_wrong_heard=None):
        self.reading_fluency_active = active
        if passage_words is not None:
            self.reading_passage_words = passage_words
        if current_word_idx is not None:
            self.reading_current_word_idx = current_word_idx
        if word_states is not None:
            self.reading_word_states = word_states
        elif passage_words is not None:
            self.reading_word_states = ['unread'] * len(passage_words)
        self.reading_last_wrong_heard = last_wrong_heard
        
        # Force a refresh of the display using the last face image if available
        if getattr(self, 'last_face_image', None) is not None:
            self.display_face(self.last_face_image)

    def set_reading_status(self, status):
        self.reading_status = status
        # Force a refresh of the display using the last face image if available
        if getattr(self, 'last_face_image', None) is not None:
            self.display_face(self.last_face_image)

    def draw_reading_fluency_overlay_cv(self, canvas):
        W, H = self.screen_size
        overlay_h = H // 3
        y0 = H - overlay_h
        
        # 1. Draw translucent background card (Dark Indigo/Slate)
        roi = canvas[y0:H, 0:W]
        overlay_bg = np.zeros_like(roi)
        overlay_bg[:] = (31, 11, 15) # Dark indigo (15, 11, 31) RGB
        alpha = 0.8
        roi_blended = cv2.addWeighted(roi, 1 - alpha, overlay_bg, alpha, 0)
        canvas[y0:H, 0:W] = roi_blended
        
        # 2. Draw border line at top of overlay
        cv2.line(canvas, (0, y0), (W, y0), (255, 200, 100), 2, lineType=cv2.LINE_AA)

        # 2.5 Draw real-time status indicator (pulsing dot + label)
        status = getattr(self, 'reading_status', 'idle')
        if status == 'listening':
            color_dot = (50, 220, 50)  # Green in BGR
            status_text = "Listening"
            # Pulses every 0.5 seconds
            if int(time.time() * 2) % 2 == 0:
                color_dot = (20, 150, 20)
        elif status == 'transcribing':
            color_dot = (0, 165, 255)  # Orange in BGR
            status_text = "Transcribing..."
        else:
            color_dot = (120, 120, 120)  # Gray in BGR
            status_text = "Idle"
            
        dot_x = W - 180
        dot_y = y0 + 22
        cv2.circle(canvas, (dot_x, dot_y), 6, color_dot, -1, lineType=cv2.LINE_AA)
        
        font_status = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(canvas, status_text, (dot_x + 15, dot_y + 5), font_status, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        
        # 3. Draw wrapped text
        font_word = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        
        margin_x = 45
        cursor_x = margin_x
        cursor_y = y0 + 50
        line_spacing = 45
        
        space_size, _ = cv2.getTextSize(" ", font_word, font_scale, thickness)
        space_w = space_size[0]
        
        for idx, word in enumerate(self.reading_passage_words):
            if word == "\n":
                cursor_x = margin_x
                cursor_y += line_spacing
                continue
            state = self.reading_word_states[idx] if idx < len(self.reading_word_states) else 'unread'
            word_size, _ = cv2.getTextSize(word, font_word, font_scale, thickness)
            word_w, word_h = word_size
            
            # Wrap if needed
            if cursor_x + word_w > W - margin_x:
                cursor_x = margin_x
                cursor_y += line_spacing
                
            if idx == self.reading_current_word_idx:
                # Karaoke Highlight box
                pad = 6
                cv2.rectangle(canvas, 
                              (cursor_x - pad, cursor_y - word_h - pad), 
                              (cursor_x + word_w + pad, cursor_y + pad), 
                              (0, 215, 255), # Yellow/Gold
                              thickness=cv2.FILLED)
                cv2.putText(canvas, word, (cursor_x, cursor_y), font_word, font_scale, (15, 11, 31), thickness, cv2.LINE_AA)
            else:
                if state == 'correct':
                    color = (50, 220, 50)
                    cv2.putText(canvas, word, (cursor_x, cursor_y), font_word, font_scale, color, thickness, cv2.LINE_AA)
                    cv2.line(canvas, (cursor_x, cursor_y + 8), (cursor_x + word_w, cursor_y + 8), color, 2, cv2.LINE_AA)
                elif state == 'wrong':
                    color = (70, 70, 255) # Red BGR
                    cv2.putText(canvas, word, (cursor_x, cursor_y), font_word, font_scale, color, thickness, cv2.LINE_AA)
                    cv2.line(canvas, (cursor_x, cursor_y - word_h // 2), (cursor_x + word_w, cursor_y - word_h // 2), color, 2, cv2.LINE_AA)
                else:
                    color = (220, 220, 220)
                    cv2.putText(canvas, word, (cursor_x, cursor_y), font_word, font_scale, color, thickness, cv2.LINE_AA)
                    
            cursor_x += word_w + space_w
            
        # 4. Draw wrong heard feedback box inside the overlay at the bottom if present
        if self.reading_last_wrong_heard:
            heard_text = self.reading_last_wrong_heard.get("heard", "")
            expected_text = self.reading_last_wrong_heard.get("expected", "")
            
            box_y0 = H - 85
            box_x0 = 40
            box_x1 = W - 40
            box_y1 = H - 15
            
            # Semi-transparent inner card
            card_roi = canvas[box_y0:box_y1, box_x0:box_x1]
            card_bg = np.zeros_like(card_roi)
            card_bg[:] = (20, 15, 45) # Dark wine/plum
            canvas[box_y0:box_y1, box_x0:box_x1] = cv2.addWeighted(card_roi, 0.4, card_bg, 0.6, 0)
            
            # Inner border
            cv2.rectangle(canvas, (box_x0, box_y0), (box_x1, box_y1), (100, 100, 255), 1, lineType=cv2.LINE_AA)
            
            font_feedback = cv2.FONT_HERSHEY_SIMPLEX
            # Gigi heard: 'heard' vs Try saying: 'expected' side-by-side or on one line
            feedback_str = f"Gigi heard: '{heard_text}'   |   Try saying: '{expected_text}'"
            cv2.putText(canvas, feedback_str, (box_x0 + 20, box_y0 + 45), font_feedback, 0.7, (120, 150, 255), 2, cv2.LINE_AA)

    def draw_reading_fluency_overlay_pygame(self, canvas):
        W, H = self.screen_size
        overlay_h = H // 3
        y0 = H - overlay_h
        
        # 1. Create a semi-transparent surface for the overlay background
        overlay_surf = pygame.Surface((W, overlay_h), pygame.SRCALPHA)
        overlay_surf.fill((15, 11, 31, 204)) # 80% opacity dark slate
        pygame.draw.line(overlay_surf, (100, 200, 255), (0, 0), (W, 0), 2) # border line at top
        canvas.blit(overlay_surf, (0, y0))

        # 1.5 Draw real-time status indicator (pulsing dot + label)
        status = getattr(self, 'reading_status', 'idle')
        if status == 'listening':
            color_dot = (50, 220, 50)  # Green
            status_text = "Listening"
            if int(time.time() * 2) % 2 == 0:
                color_dot = (20, 150, 20)
        elif status == 'transcribing':
            color_dot = (255, 165, 0)  # Orange
            status_text = "Transcribing..."
        else:
            color_dot = (120, 120, 120)  # Gray
            status_text = "Idle"
            
        dot_x = W - 180
        dot_y = y0 + 22
        pygame.draw.circle(canvas, color_dot, (dot_x, dot_y), 6)
        
        font_status = pygame.font.SysFont("Arial", 16, bold=True)
        status_surf = font_status.render(status_text, True, (200, 200, 200))
        canvas.blit(status_surf, (dot_x + 15, dot_y - 8))
        
        # 2. Draw wrapped text
        font_word = pygame.font.SysFont("Arial", 32, bold=False)
        font_word_bold = pygame.font.SysFont("Arial", 32, bold=True)
        
        margin_x = 45
        cursor_x = margin_x
        cursor_y = y0 + 30
        line_spacing = 45
        
        space_w, _ = font_word.size(" ")
        
        for idx, word in enumerate(self.reading_passage_words):
            if word == "\n":
                cursor_x = margin_x
                cursor_y += line_spacing
                continue
            state = self.reading_word_states[idx] if idx < len(self.reading_word_states) else 'unread'
            current_font = font_word_bold if idx == self.reading_current_word_idx else font_word
            word_w, word_h = current_font.size(word)
            
            if cursor_x + word_w > W - margin_x:
                cursor_x = margin_x
                cursor_y += line_spacing
                
            if idx == self.reading_current_word_idx:
                pad = 4
                rect = pygame.Rect(cursor_x - pad, cursor_y - pad, word_w + 2*pad, word_h + 2*pad)
                pygame.draw.rect(canvas, (255, 215, 0), rect, border_radius=4)
                word_surf = current_font.render(word, True, (15, 11, 31))
                canvas.blit(word_surf, (cursor_x, cursor_y))
            else:
                if state == 'correct':
                    color = (50, 220, 50)
                    word_surf = current_font.render(word, True, color)
                    canvas.blit(word_surf, (cursor_x, cursor_y))
                    pygame.draw.line(canvas, color, (cursor_x, cursor_y + word_h + 2), (cursor_x + word_w, cursor_y + word_h + 2), 2)
                elif state == 'wrong':
                    color = (255, 70, 70)
                    word_surf = current_font.render(word, True, color)
                    canvas.blit(word_surf, (cursor_x, cursor_y))
                    pygame.draw.line(canvas, color, (cursor_x, cursor_y + word_h // 2), (cursor_x + word_w, cursor_y + word_h // 2), 2)
                else:
                    color = (200, 200, 200)
                    word_surf = current_font.render(word, True, color)
                    canvas.blit(word_surf, (cursor_x, cursor_y))
                    
            cursor_x += word_w + space_w
            
        # 3. Draw wrong heard feedback box inside the overlay at the bottom if present
        if self.reading_last_wrong_heard:
            heard_text = self.reading_last_wrong_heard.get("heard", "")
            expected_text = self.reading_last_wrong_heard.get("expected", "")
            
            box_y = H - 85
            box_h = 60
            box_w = W - 80
            
            card_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            card_surf.fill((45, 15, 20, 180)) # semi-transparent wine color
            pygame.draw.rect(card_surf, (255, 100, 100), (0, 0, box_w, box_h), 1, border_radius=6)
            canvas.blit(card_surf, (40, box_y))
            
            font_feedback = pygame.font.SysFont("Arial", 20, bold=True)
            feedback_str = f"Gigi heard: '{heard_text}'   |   Try saying: '{expected_text}'"
            feedback_surf = font_feedback.render(feedback_str, True, (120, 150, 255))
            canvas.blit(feedback_surf, (60, box_y + 18))

    def display_text(self, text=None):    
        if text:
            if IMAGE_OPTION == "pygame":
                # Create a blank image with white background and render multiline text
                font = pygame.font.Font(None, 36)  # Default font with size 36
                image_width, image_height = self.screen_size
                background = pygame.Surface((image_width, image_height))
                background.fill((255, 255, 255))  # White background

                lines = text.split("\n")
                surfaces = [font.render(line, True, (0, 0, 0)) for line in lines]
                total_height = sum(surf.get_height() for surf in surfaces) + (len(surfaces) - 1) * 8
                
                # Center the text block vertically on the screen
                current_y = (image_height - total_height) // 2
                for surf in surfaces:
                    text_x = (image_width - surf.get_width()) // 2
                    background.blit(surf, (text_x, current_y))
                    current_y += surf.get_height() + 8

                self.show_face = False
                self.display_face(background)
            elif IMAGE_OPTION == "cv":
                # Create a blank image with white background and render multiline text
                image_width, image_height = self.screen_size
                background = np.ones((image_height, image_width, 3), dtype=np.uint8) * 255  # White background

                # Set font and scale
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 1.5
                font_thickness = 2

                lines = text.split("\n")
                line_sizes = [cv2.getTextSize(line, font, font_scale, font_thickness) for line in lines]
                total_height = sum(size[0][1] for size in line_sizes) + (len(lines) - 1) * 15

                # Center the text block vertically on the screen
                current_y = (image_height - total_height) // 2
                for line, ((w, h), baseline) in zip(lines, line_sizes):
                    text_x = (image_width - w) // 2
                    current_y += h
                    cv2.putText(background, line, (text_x, current_y), font, font_scale, (0, 0, 0), font_thickness, cv2.LINE_AA)
                    current_y += 15 # vertical line spacing

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
            # Force redrawing the default idle face immediately to prevent black screen flash
            idle_face = {part: ("idle", "1") for part in global_parts}
            face_image = self.set_face(idle_face)
            self.display_face(face_image)

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

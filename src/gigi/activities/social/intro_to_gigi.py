#!/usr/bin/env python3
"""
=============================================================================
           GIGI Social Robot Platform - Introduction to Gigi Activity
   Designed for Human-Robot Interaction (HRI) Course at Indiana University
               Bloomington, Department of Informatics / Luddy School
=============================================================================

This activity is a rich, 5+ minute monologue introduction wherein Gigi introduces
herself to the classroom, showcasing:
  - Physical degrees of freedom (neck, torso, shoulders, elbows)
  - Synchronized viseme speech & animated facial expressions
  - Lifelike nonverbal cues, eye gazes, and dynamic blinking
  - Machine perception with live 5-second camera feed showing marked faces
  - Neural computing architecture (Orange Pi 5 Pro + RK3588 NPU)
  - HRI concepts (embodiment, social presence, uncanny valley, gestural cues)
  - Engaging personality, Hoosier spirit, and encouragement for student projects
"""

import os
import sys
import time
import signal
import random
import threading
from gigi.core.robot import GigiRobot as Character
from gigi.core.config import IS_ROBOT


class IntroToGigiActivity:
    def __init__(self):
        print("====================================================")
        print("    GIGI Social Robot - Introduction to Gigi        ")
        print("   IU Bloomington - Department of Informatics (HRI) ")
        print("====================================================")
        
        self.gigi = Character(character_name="fuzzy", wakeup=True, activity="Intro to Gigi")
        self.running = True
        self.stop_event = threading.Event()
        self.start_time = None
        
        # Setup signal handlers for clean exit (e.g. SIGINT, SIGTERM, Bluetooth app stop)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        
        # Initial settle
        time.sleep(1.5)

    def _handle_signal(self, signum, frame):
        print(f"\n[Intro] Stop signal received ({signum}). Cleaning up gracefully...")
        self.running = False
        self.stop_event.set()

    def speak(self, text, movement=None, pause_after=0.8):
        """
        Delivers a speech segment with synchronized visemes and optional posture movement.
        """
        if not self.running:
            return
            
        print(f"\n[Intro] Speech: \"{text}\"")
        if movement:
            print(f"[Intro] -> Posture/Movement: {movement}")

        try:
            self.gigi.run_character(
                viseme_data={'text': text, 'file': None},
                movement_data=movement
            )
        except Exception as e:
            print(f"[Intro] Error during speech segment: {e}")

        if pause_after > 0 and self.running:
            time.sleep(pause_after)

    def move(self, movement_name, pause_after=0.5):
        """
        Executes a physical movement demonstration after speaking.
        """
        if not self.running:
            return
            
        print(f"[Intro] -> Demonstrating Movement: {movement_name}")
        try:
            self.gigi.run_character(movement_data=movement_name)
        except Exception as e:
            print(f"[Intro] Error executing movement: {e}")

        if pause_after > 0 and self.running:
            time.sleep(pause_after)

    def set_eyes(self, eye_sequence, pause_after=0.5):
        """
        Demonstrates an eye gaze or facial sequence after speaking.
        """
        if not self.running:
            return
            
        print(f"[Intro] -> Demonstrating Eye Sequence: {eye_sequence}")
        if self.gigi.face:
            try:
                self.gigi.face.run_sequence(eye_sequence)
            except Exception as e:
                print(f"[Intro] Error setting eye sequence: {e}")

        if pause_after > 0 and self.running:
            time.sleep(pause_after)

    def show_camera_feed_for(self, duration_seconds=5.0):
        """
        Activates vision and displays the live camera feed with marked faces on screen for 5 seconds.
        """
        if not self.running:
            return
            
        print(f"\n[Intro] >>> Displaying live camera feed with marked faces for {duration_seconds} seconds <<<")
        if self.gigi.vision:
            try:
                self.gigi.vision.run_vision()
                time.sleep(1.0)
                
                # Pan gently while displaying camera feed
                if self.gigi.movement:
                    self.gigi.movement.move_motors({"torso": -0.2, "neck": -0.15})
                
                feed_start = time.time()
                while time.time() - feed_start < duration_seconds and self.running:
                    # Get annotated frame with drawn face bounding boxes
                    frame = self.gigi.vision.get_latest_frame()
                    if frame is not None and self.gigi.face:
                        self.gigi.face.display_face(frame)
                    time.sleep(0.05)
                
                if self.gigi.movement:
                    self.gigi.movement.move_motors({"torso": 0.0, "neck": 0.0})
                    
                self.gigi.vision.stop_vision()
            except Exception as e:
                print(f"[Intro] Notice during camera feed display: {e}")
        else:
            time.sleep(duration_seconds)

        # Restore animated character face
        if self.gigi.face:
            try:
                self.gigi.face.run_sequence("idle")
            except Exception as e:
                print(f"[Intro] Error restoring idle face: {e}")
        self.gigi.run_character(movement_data='home')
        time.sleep(0.5)

    def act_1_warm_welcome(self):
        """Act 1: Warm Welcome & Hoosier Spirit (~45s)"""
        print("\n====================================================")
        print("    Act 1: The Warm Welcome & Hoosier Spirit        ")
        print("====================================================")
        
        self.speak(
            "Hello everyone! Welcome to Human-Robot Interaction!",
            movement='wave_hello',
            pause_after=1.2
        )
        
        self.speak(
            "I am Gigi, and it is an absolute pleasure to meet all of you here in the Department of Informatics at Indiana University Bloomington!",
            movement='open_arms',
            pause_after=1.0
        )
        
        self.speak(
            "Before we dive into the fascinating world of social robotics, let me say one very important thing: Go Hoosiers!",
            movement='clap',
            pause_after=1.0
        )
        
        self.speak(
            "Sure, my internal wiring is mostly copper, silicon, and 3D-printed brackets, but my digital heart proudly beats in cream and crimson.",
            movement='alive_shift',
            pause_after=1.2
        )
        
        self.gigi.run_character(movement_data='home')
        time.sleep(0.5)

    def act_2_meet_gigi_embodiment(self):
        """Act 2: Meet Gigi & Physical Embodiment (~50s)"""
        print("\n====================================================")
        print("    Act 2: Meet Gigi & Physical Embodiment          ")
        print("====================================================")
        
        self.speak(
            "You might be wondering: what exactly am I? Well, I am an open-source, fully programmable social robot platform, built specifically for HRI education and research.",
            movement='look_from_side_to_side',
            pause_after=1.0
        )
        
        self.speak(
            "In your course this semester, you will explore a fundamental question: why does physical embodiment matter?",
            movement='alive_look_around',
            pause_after=1.2
        )
        
        self.speak(
            "Think about it. A voice assistant on your phone or a smart speaker on a counter can answer questions, but it lacks physical presence, gaze direction, and spatial rapport.",
            movement='alive_gently_look_left',
            pause_after=1.0
        )
        
        self.speak(
            "When a robot has a physical body that can look at you, turn its head, express emotion, and share your physical space, the entire psychology of interaction changes completely.",
            movement='open_close_arms',
            pause_after=1.2
        )
        
        self.gigi.run_character(movement_data='home')

    def act_3_hardware_and_degrees_of_freedom(self):
        """Act 3: Hardware & Degrees of Freedom Showcase (~75s)"""
        print("\n====================================================")
        print("    Act 3: Anatomy & Degrees of Freedom             ")
        print("====================================================")
        
        # Introduction to anatomy
        self.speak(
            "Let me give you a quick guided tour of my anatomy, because soon, you will be building, calibrating, and programming robots just like me!",
            movement='arms_up',
            pause_after=1.0
        )
        self.gigi.run_character(movement_data='home')
        
        # 1. Neck demonstration (Speak first, then demonstrate movement)
        self.speak(
            "Starting with my head and neck. I have a dedicated neck servo that lets me pan smoothly to direct my attention right toward you.",
            pause_after=0.4
        )
        self.move('look_from_side_to_side', pause_after=0.8)
        
        # 2. Torso demonstration (Speak first, then demonstrate movement)
        self.speak(
            "Next is my torso. My base rotation gives me full body orientation, so I can face individual groups, track who is speaking, and display active listening posture.",
            pause_after=0.4
        )
        self.move('alive_shift', pause_after=0.8)
        
        # 3. Arms & Gestural language (Speak intro first)
        self.speak(
            "And of course, check out my dual arms! Each arm has independent shoulder and elbow degrees of freedom, allowing me to express rich communicative gestures.",
            movement='arms_up_and_down',
            pause_after=0.8
        )
        
        # Wave hello demonstration
        self.speak(
            "For example, I can give a friendly wave hello...",
            pause_after=0.3
        )
        self.move('wave_hello', pause_after=0.8)
        
        # Celebration clap demonstration
        self.speak(
            "I can enthusiastically celebrate when your python code compiles without any runtime errors...",
            pause_after=0.3
        )
        self.move('clap', pause_after=0.8)
        
        # Arm circle / big stretch demonstration
        self.speak(
            "Or I can stretch my arms out wide when I am thinking really big thoughts!",
            pause_after=0.3
        )
        self.move('arms_circle', pause_after=0.8)
        
        # Summary of motor control
        self.speak(
            "All of these joints are controlled with pulse width modulation and smooth S-curve interpolation to keep my gestures natural and fluid.",
            movement='arms_down',
            pause_after=1.0
        )
        
        self.gigi.run_character(movement_data='home')

    def act_4_face_visemes_and_expressiveness(self):
        """Act 4: Face, Visemes & Emotional Expressiveness (~65s)"""
        print("\n====================================================")
        print("    Act 4: Face, Visemes & Emotional Expressiveness ")
        print("====================================================")
        
        self.speak(
            "Now, take a close look at my face. In Human-Robot Interaction, nonverbal facial cues are essential for building trust and understanding.",
            movement='alive_gently_look_right',
            pause_after=1.0
        )
        
        self.speak(
            "Notice how my mouth moves synchronously with every word I say? That is real-time viseme mapping! My software analyzes the acoustic energy envelope of synthesized speech and maps it onto animated mouth visemes with zero delay.",
            movement='alive_shift',
            pause_after=1.0
        )
        
        # 1. Look up (Speak first, then execute eye sequence and hold)
        self.speak(
            "My eyes are also fully expressive. I can glance up in deep contemplation...",
            pause_after=0.3
        )
        self.set_eyes('look_up', pause_after=1.5)
        
        # 2. Look down (Speak first, then execute eye sequence and hold)
        self.speak(
            "Glance down when feeling thoughtful or humble...",
            pause_after=0.3
        )
        self.set_eyes('look_down', pause_after=1.5)
        
        # 3. Look side to side (Speak first, then execute eye and head movement)
        self.speak(
            "Or shift my gaze dynamically from left to right as I scan the lecture hall!",
            pause_after=0.3
        )
        self.set_eyes('look_left', pause_after=0.6)
        self.move('look_from_side_to_side', pause_after=0.4)
        self.set_eyes('look_right', pause_after=0.6)
        self.set_eyes('idle', pause_after=0.5)
        
        # 4. Blinking and breathing lifelike shifts
        self.speak(
            "We also include lifelike micro-movements, random blinking intervals, and subtle breathing posture shifts. Without these, robots can quickly fall into the creepy uncanny valley!",
            movement='alive_look_around',
            pause_after=1.2
        )
        
        self.gigi.run_character(movement_data='home')

    def act_5_perception_and_neural_brain(self):
        """Act 5: Perception, Senses & Neural Brain with 5s Camera Feed (~70s)"""
        print("\n====================================================")
        print("    Act 5: Perception, Senses & Neural Brain        ")
        print("====================================================")
        
        self.speak(
            "Of course, a social robot cannot just talk; it must perceive its environment and understand the people around it.",
            movement='open_arms',
            pause_after=1.0
        )
        
        # Announce camera on torso and switch to live feed for 5 seconds
        self.speak(
            "Mounted right on my torso, I have an integrated camera for computer vision. Let me switch my screen over to show you my live camera feed with face tracking for the next 5 seconds!",
            movement='look_left',
            pause_after=0.8
        )
        
        # Show live annotated camera feed on screen for 5 seconds
        self.show_camera_feed_for(duration_seconds=5.0)
        
        self.speak(
            "As you can see, I can perform real-time multi-face tracking, estimate emotional valence, recognize hand gestures like a thumbs up, and maintain an egocentric memory map of where everyone is located.",
            movement='alive_shift',
            pause_after=1.0
        )
        
        self.speak(
            "For audio, I process microphone input with neural speech recognition and identify distinct speakers by their voice embeddings.",
            movement='alive_gently_look_left',
            pause_after=1.0
        )
        
        self.speak(
            "All of this runs locally on an Orange Pi 5 Pro single-board computer, powered by an onboard Neural Processing Unit for blazing fast edge AI inference!",
            movement='open_close_arms',
            pause_after=1.2
        )
        
        self.gigi.run_character(movement_data='home')

    def act_6_student_mission_and_humor(self):
        """Act 6: What Students Will Do To Me! (~50s)"""
        print("\n====================================================")
        print("    Act 6: The Student Mission & HRI Challenges     ")
        print("====================================================")
        
        self.speak(
            "Now, let's talk about why you are all here. Throughout this course, you will not just study HRI theories from a textbook—you will get your hands dirty building and programming robots!",
            movement='arms_up',
            pause_after=1.0
        )
        
        self.speak(
            "You will assemble 3D-printed chassis, crimp wiring harnesses, tune motor calibration limits, and design novel multi-modal interaction architectures.",
            movement='alive_look_around',
            pause_after=1.0
        )
        
        self.speak(
            "You might teach robots how to be empathetic tutors, interactive game companions, healthcare assistants, or expressive storytellers.",
            movement='open_arms',
            pause_after=1.0
        )
        
        self.speak(
            "Now, I do have one small personal favor to ask as your robot platform:",
            movement='alive_gently_look_right',
            pause_after=1.2
        )
        
        self.speak(
            "When you are experimenting with my motor calibration scripts, please remember: there is no Ctrl-Z for gravity! Double-check your servo angles, be gentle with my gears, and please give me a fun personality!",
            movement='clap',
            pause_after=1.2
        )
        
        self.gigi.run_character(movement_data='home')

    def act_7_grand_finale_and_handoff(self):
        """Act 7: Grand Finale & Handoff (~35s)"""
        print("\n====================================================")
        print("    Act 7: Grand Finale & Handoff                   ")
        print("====================================================")
        
        self.speak(
            "Social robotics is one of the most exciting frontiers in science, engineering, and design. The way humans and robots interact in the coming decades will be shaped by the work you do right here in this classroom.",
            movement='open_arms',
            pause_after=1.0
        )
        
        self.speak(
            "I cannot wait to see what brilliant ideas, creative experiments, and breakthrough HRI projects you will create with me this semester!",
            movement='arms_up_and_down',
            pause_after=1.0
        )
        
        self.speak(
            "Thank you so much for your attention. Have a wonderful, inspiring semester, and Go Hoosiers! I will now hand the stage back to your instructor!",
            movement='wave_hello',
            pause_after=1.5
        )
        
        # Return to clean home position
        self.gigi.run_character(movement_data='home')
        time.sleep(1.0)

    def run(self):
        """Executes the full 7-act Introduction to Gigi monologue activity."""
        self.start_time = time.time()
        print(f"\n[Intro] Starting Introduction to Gigi monologue activity at {time.strftime('%H:%M:%S')}...")
        
        try:
            # Execute all 7 acts sequentially
            if self.running:
                self.act_1_warm_welcome()
            if self.running:
                self.act_2_meet_gigi_embodiment()
            if self.running:
                self.act_3_hardware_and_degrees_of_freedom()
            if self.running:
                self.act_4_face_visemes_and_expressiveness()
            if self.running:
                self.act_5_perception_and_neural_brain()
            if self.running:
                self.act_6_student_mission_and_humor()
            if self.running:
                self.act_7_grand_finale_and_handoff()
                
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            print("\n====================================================")
            print(f"  Activity Completed Successfully! Total Duration: {minutes}m {seconds}s ({elapsed:.1f}s)")
            print("====================================================")
            
        except Exception as e:
            print(f"\n[Intro] Error during activity execution: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

    def cleanup(self):
        print("[Intro] Cleaning up character resources...")
        try:
            if self.gigi:
                if self.gigi.vision:
                    self.gigi.vision.stop_vision()
                if self.gigi.movement:
                    self.gigi.movement.home_position()
                self.gigi.stop_character()
        except Exception as e:
            print(f"[Intro] Error during cleanup: {e}")
        print("[Intro] Gigi shutdown cleanly.")


def main():
    activity = IntroToGigiActivity()
    activity.run()


if __name__ == "__main__":
    main()

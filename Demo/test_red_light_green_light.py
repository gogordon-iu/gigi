import os
import sys
import unittest
import numpy as np
import time

# Add gigi workspace dir and Demo dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir is scratch
workspace_dir = r"c:\Users\gorengor\Goren\IUB\Research\Gigi\Code\gigi"
if workspace_dir not in sys.path:
    sys.path.append(workspace_dir)

from Demo.red_light_green_light import check_for_winner, detect_motion_for_faces

class MockFaceCache:
    def __init__(self):
        self.faces = {}
        
    def get_all_faces(self):
        return self.faces.copy()
        
    def get_face_data(self, fid):
        return self.faces.get(fid, {}).copy()

class MockVision:
    def __init__(self):
        self.running = True
        self.face_cache = MockFaceCache()
        self.frames = []
        self.frame_idx = 0
        
    def get_latest_frame(self):
        if not self.frames:
            return None
        idx = min(self.frame_idx, len(self.frames) - 1)
        self.frame_idx += 1
        return self.frames[idx]

class MockGigi:
    def __init__(self):
        self.vision = MockVision()
        self.face = None
        
    def run_character(self, *args, **kwargs):
        pass

class TestRedLightGreenLight(unittest.TestCase):
    def test_check_for_winner_no_winner(self):
        gigi = MockGigi()
        
        # Face that is far away (small box)
        gigi.vision.face_cache.faces = {
            "0001": {
                "name": "Alice",
                "box": (100, 100, 150, 150),  # 50x50 box in 640x480 frame
                "x": 125,
                "y": 125,
                "last_seen": time.time()
            }
        }
        
        # Mock frame: 640x480
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        gigi.vision.frames = [frame]
        
        winner = check_for_winner(gigi)
        self.assertIsNone(winner)
        
    def test_check_for_winner_wins_by_area(self):
        gigi = MockGigi()
        
        # Face that fills a large portion of the frame
        # Area = 300 * 300 = 90000. Frame area = 640 * 480 = 307200. Ratio = 29.3% (> 0.25)
        # Width = 300. Frame width = 640. Ratio = 46.8% (> 0.45)
        gigi.vision.face_cache.faces = {
            "0001": {
                "name": "Alice",
                "box": (100, 100, 400, 400),
                "x": 250,
                "y": 250,
                "last_seen": time.time()
            }
        }
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        gigi.vision.frames = [frame]
        
        winner = check_for_winner(gigi)
        self.assertEqual(winner, "Alice")
        
    def test_detect_motion_associated_with_correct_face(self):
        gigi = MockGigi()
        
        # Two players active
        gigi.vision.face_cache.faces = {
            "0001": {
                "name": "Alice",
                "x": 100,  # Centered at x=100
                "y": 150,
                "last_seen": time.time()
            },
            "0002": {
                "name": "Bob",
                "x": 500,  # Centered at x=500
                "y": 150,
                "last_seen": time.time()
            }
        }
        
        # We will simulate 10 frames of motion
        # Frame 0 (base): empty black frame
        # Frame 1-9: draw a large white square (motion blob) around x=100 (near Alice)
        frames = []
        base = np.zeros((480, 640, 3), dtype=np.uint8)
        frames.append(base)
        
        for i in range(15):
            current = np.zeros((480, 640, 3), dtype=np.uint8)
            # Draw a motion square near Alice (x=80 to x=120)
            current[100:200, 80:120] = 255
            frames.append(current)
            
        gigi.vision.frames = frames
        
        # Detect motion for 1.0 second with a low threshold for testing
        moved = detect_motion_for_faces(gigi, duration=1.0, motion_threshold=200, max_x_diff_ratio=0.15)
        
        # Alice should be in the set of moved players, Bob should not be
        self.assertIn("Alice", moved)
        self.assertNotIn("Bob", moved)

if __name__ == "__main__":
    unittest.main()

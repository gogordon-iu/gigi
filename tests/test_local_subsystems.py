"""
Comprehensive local subsystem functional tests for Gigi Robot.
Tests all software modules, mockable hardware, perception logic,
interaction planning, and web API endpoints without physical robot hardware.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np


class TestCoreSubsystems(unittest.TestCase):
    """Tests for gigi.core configuration, paths, logger, and conversation."""

    def test_config_paths(self):
        from gigi.core import config

        self.assertIsInstance(config.PROJECT_ROOT, Path)
        self.assertTrue(config.PROJECT_ROOT.exists(), f"PROJECT_ROOT does not exist: {config.PROJECT_ROOT}")
        self.assertTrue(config.ASSETS_DIR.exists(), f"ASSETS_DIR does not exist: {config.ASSETS_DIR}")
        self.assertTrue(config.RESOURCES_DIR.exists(), f"RESOURCES_DIR does not exist: {config.RESOURCES_DIR}")

    def test_config_hardware_flags(self):
        from gigi.core import config

        if sys.platform.startswith("win") or sys.platform == "darwin":
            self.assertFalse(config.IS_ROBOT, "IS_ROBOT should be False on non-Linux workstations")

    def test_interaction_logger(self):
        from gigi.core.logger import InteractionLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_dir = Path(tmpdir) / "test_data"
            logger = InteractionLogger(base_dir=test_log_dir)
            logger.initialize_session(user_name="TestUser", script_name="test_script")
            logger.log_conversation("user", "Hello Gigi!")
            logger.log_conversation("robot", "Hello friend!")
            self.assertTrue(logger.is_initialized)
            self.assertEqual(logger.user_name, "TestUser")


class TestHardwareSubsystems(unittest.TestCase):
    """Tests for gigi.hardware calibration, motor simulation, and camera helpers."""

    def test_motor_calibration_loader(self):
        from gigi.hardware.calibration import load_motor_calibration

        calibration = load_motor_calibration()
        self.assertIsInstance(calibration, dict)
        required_joints = ["neck", "torso", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow"]
        for joint in required_joints:
            self.assertIn(joint, calibration, f"Missing joint '{joint}' in calibration")
            self.assertIn("channel", calibration[joint])
            self.assertIn("min", calibration[joint])
            self.assertIn("max", calibration[joint])
            self.assertIn("center", calibration[joint])

    def test_motor_calibration_save_roundtrip(self):
        from gigi.hardware.calibration import load_motor_calibration, save_motor_calibration

        original_data = load_motor_calibration()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_path = Path(tf.name)
        try:
            save_motor_calibration(original_data, custom_path=temp_path)
            self.assertTrue(temp_path.exists())
            with open(temp_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["neck"]["channel"], original_data["neck"]["channel"])
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_motor_calibration_example_template(self):
        from gigi.core.config import PROJECT_ROOT
        example_template = PROJECT_ROOT / "motorData_calibrated.example.json"
        self.assertTrue(example_template.exists(), "motorData_calibrated.example.json must exist as tracked template")
        with open(example_template, "r", encoding="utf-8") as f:
            data = json.load(f)
        for joint in ["neck", "torso", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow"]:
            self.assertIn(joint, data)
            self.assertIn("channel", data[joint])
            self.assertIn("min", data[joint])
            self.assertIn("max", data[joint])
            self.assertIn("center", data[joint])

    def test_motor_calibration_init_fallback(self):
        from gigi.hardware.calibration import init_local_motor_calibration
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            fake_root = Path(td)
            example = fake_root / "motorData_calibrated.example.json"
            with open(example, "w", encoding="utf-8") as f:
                json.dump({"neck": {"channel": 0, "min": 200, "max": 400, "center": 300, "calibrated": True}}, f)
            with patch("gigi.hardware.calibration.PROJECT_ROOT", fake_root):
                created = init_local_motor_calibration()
                self.assertTrue(created.exists())
                with open(created, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertIn("neck", loaded)

    def test_motor_controller_simulation(self):
        from gigi.hardware.motors import PCA9685Controller

        controller = PCA9685Controller()
        # On workstation, hardware should not be opened
        self.assertFalse(controller.is_hardware_available)

        # In simulation mode, PWM calls execute safely as no-ops
        controller.set_pwm(1, 0, 275)
        controller.set_all_pwm(0, 0)


class TestPerceptionSubsystems(unittest.TestCase):
    """Tests for speaker identification, audio processing, and vision helpers."""

    def test_speaker_database(self):
        from gigi.perception.speaker_id import SpeakerDatabase

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tf:
            temp_path = Path(tf.name)
        try:
            db = SpeakerDatabase(db_path=temp_path)
            np.random.seed(42)
            emb_alice = np.random.randn(256).astype(np.float32)
            emb_alice /= np.linalg.norm(emb_alice)

            emb_bob = np.random.randn(256).astype(np.float32)
            emb_bob /= np.linalg.norm(emb_bob)

            db.add_speaker("Alice", emb_alice)
            db.add_speaker("Bob", emb_bob)
            db.add_transcription_record("Alice", "I love reading books.")

            name, similarity = db.identify_speaker(emb_alice, threshold=0.7)
            self.assertEqual(name, "Alice")
            self.assertGreaterEqual(similarity, 0.95)

            db_reloaded = SpeakerDatabase(db_path=temp_path)
            self.assertIn("Alice", db_reloaded.speaker_data)
            self.assertIn("Bob", db_reloaded.speaker_data)
            self.assertIn("Alice", db_reloaded.transcription_records)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_audio_resample(self):
        from gigi.perception.hearing import resample_audio

        sample_rate_orig = 48000
        target_rate = 16000
        duration = 0.5
        num_samples = int(sample_rate_orig * duration)
        raw_audio = (np.sin(np.linspace(0, 440 * 2 * np.pi * duration, num_samples)) * 32767).astype(np.int16)

        resampled = resample_audio(raw_audio, sample_rate_orig, target_rate)
        expected_len = int(num_samples * (target_rate / sample_rate_orig))
        self.assertAlmostEqual(len(resampled), expected_len, delta=50)

    def test_vision_geometry_utils(self):
        from gigi.perception.vision_helper import GeometryUtils

        box1 = (0, 0, 10, 10)
        box2 = (0, 0, 10, 10)
        iou_exact = GeometryUtils.calculate_iou(box1, box2)
        self.assertAlmostEqual(iou_exact, 1.0)

        box_disjoint = (20, 20, 30, 30)
        iou_disjoint = GeometryUtils.calculate_iou(box1, box_disjoint)
        self.assertAlmostEqual(iou_disjoint, 0.0)


class TestExpressionSubsystems(unittest.TestCase):
    """Tests for face definitions, gestures, and movement."""

    def test_face_definitions(self):
        from gigi.expression.face_definitions import CHARACTERS, BASIC_SEQUENCES

        self.assertIn("fuzzy", CHARACTERS)
        self.assertIn("idle", BASIC_SEQUENCES)
        self.assertIn("smile", BASIC_SEQUENCES)
        self.assertIn("blink", BASIC_SEQUENCES)
        self.assertIn("look_right", BASIC_SEQUENCES)
        self.assertIn("look_left", BASIC_SEQUENCES)

    def test_gesture_definitions(self):
        from gigi.expression.gesture_definitions import BASIC_GESTURES

        self.assertIn("home", BASIC_GESTURES)
        self.assertIn("wave_hello", BASIC_GESTURES)
        self.assertIn("clap", BASIC_GESTURES)
        self.assertIn("open_arms", BASIC_GESTURES)

        for gesture_name, steps in BASIC_GESTURES.items():
            self.assertIsInstance(steps, list, f"Gesture {gesture_name} should be a list of steps")
            for step in steps:
                self.assertIn("time", step)
                self.assertIn("motors", step)

    def test_movement_simulation(self):
        from gigi.expression.movement import Movement

        movement = Movement()
        # Test smooth sequence generation
        seq = movement.smooth_sequence({"neck": 0.5}, duration=0.1, number_steps=5)
        self.assertEqual(len(seq), 5)
        self.assertIn("neck", seq[-1]["motors"])
        # Home position executes safely
        movement.home_position(duration=0.01)


class TestInteractionSubsystems(unittest.TestCase):
    """Tests for pedagogical strategies, safety filtering, activity planner, and web API."""

    def test_strategy_catalog(self):
        from gigi.interaction.strategies import StrategyCatalog

        catalog = StrategyCatalog()
        strategies = catalog.get_all_strategies()
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)

        first_strategy = strategies[0]
        retrieved = catalog.get_strategy_by_id(first_strategy.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, first_strategy.id)

    def test_safety_filter(self):
        from gigi.interaction.safety_filter import check_behavior

        safe_res = check_behavior("Let's read a story and learn together!")
        self.assertIsNone(safe_res, "Clean text should return None")

        bad_res = check_behavior("I hate you and you are stupid")
        self.assertIsNotNone(bad_res, "Bullying text should return canned response")

    def test_web_app_flask_routes(self):
        from gigi.interaction.web.app import app

        app.config["TESTING"] = True
        client = app.test_client()

        res = client.get("/")
        self.assertEqual(res.status_code, 200)

        res_api = client.get("/api/strategies")
        self.assertEqual(res_api.status_code, 200)
        data = res_api.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)


class TestActivitiesSubsystems(unittest.TestCase):
    """Tests for scripted lessons, name extraction, and activity discovery."""

    def test_script_discovery(self):
        from gigi.activities.scripted.script_assets import get_scripts

        scripts = get_scripts()
        self.assertIsInstance(scripts, dict)
        self.assertGreater(len(scripts), 0)
        discovered_names = list(scripts.keys())
        self.assertTrue(any("lego" in n.lower() or "ferris" in n.lower() or "halloween" in n.lower() for n in discovered_names))

    def test_name_extraction(self):
        from gigi.activities.common.utils import extract_name

        test_cases = [
            ("My name is John", "John"),
            ("I'm Samantha", "Samantha"),
            ("Call me David", "David"),
            ("Hello, my name is Alice.", "Alice"),
        ]
        for sentence, expected in test_cases:
            result = extract_name(sentence)
            self.assertEqual(result.lower(), expected.lower(), f"Failed to extract '{expected}' from '{sentence}', got '{result}'")


class TestVerificationCLI(unittest.TestCase):
    """Tests for gigi.verification CLI subsystem dispatcher."""

    def test_verification_subsystems(self):
        from gigi.verification.cli import VERIFIERS, test_motors

        self.assertIn("motors", VERIFIERS)
        self.assertIn("camera", VERIFIERS)
        self.assertIn("gestures", VERIFIERS)
        # Test motors verifier in simulation mode
        self.assertTrue(test_motors())


if __name__ == "__main__":
    unittest.main(verbosity=2)

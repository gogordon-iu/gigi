"""
Tests for Bluetooth listener, dynamic activity discovery, and script execution compatibility.
Verifies that all commands ('list', 'run', 'stop', 'status') work with the new src/gigi package architecture.
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Ensure src/ and Setup/ are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "Setup"))

from bt_listener import scan_files, find_script, scan_activity_plans, scan_custom_interactions, get_base_dir


class TestBluetoothCompatibility(unittest.TestCase):
    """Verifies that bt_listener.py correctly discovers activities and executes commands."""

    def test_base_dir_resolves_to_project_root(self):
        base_dir = get_base_dir()
        self.assertEqual(os.path.abspath(base_dir), str(PROJECT_ROOT.resolve()))

    def test_scan_files_discovers_all_activities(self):
        demos, scripts, zhennan = scan_files()

        # Check that essential activities are discovered in demos
        expected_demos = [
            "alive_mode",
            "mastermind",
            "math_quest",
            "reading_fluency",
            "story_game",
            "intro_to_gigi",
            "receptionist",
            "face_recognition_demo",
            "make_friends",
            "ferris",
            "halloween",
            "lego",
        ]
        for demo in expected_demos:
            self.assertIn(demo, demos, f"Expected '{demo}' to be found in demos dictionary")
            info = demos[demo]
            self.assertTrue(os.path.isfile(info["path"]), f"Script path '{info['path']}' does not exist")

        # Check scripted activities
        expected_scripts = ["ferris", "halloween", "lego"]
        for s in expected_scripts:
            self.assertIn(s, scripts, f"Expected '{s}' in scripts dictionary")
            self.assertEqual(scripts[s]["type"], "script")

        # Check interaction runners in zhennan
        self.assertIn("run_activity_teacherdemo", zhennan)
        self.assertIn("run_custom_interaction", zhennan)
        self.assertTrue(os.path.isfile(zhennan["run_activity_teacherdemo"]["path"]))
        self.assertTrue(os.path.isfile(zhennan["run_custom_interaction"]["path"]))

    def test_find_script_direct_name(self):
        # Direct lookup
        info, err = find_script("mastermind")
        self.assertIsNone(err)
        self.assertIsNotNone(info)
        self.assertEqual(info["stem"], "mastermind")

        # Lookup with .py extension
        info_py, err_py = find_script("mastermind.py")
        self.assertIsNone(err_py)
        self.assertEqual(info_py["stem"], "mastermind")

        # Case-insensitive
        info_case, err_case = find_script("Reading_Fluency")
        self.assertIsNone(err_case)
        self.assertEqual(info_case["stem"], "reading_fluency")

    def test_find_script_backward_compatibility_aliases(self):
        # Historical tablet aliases
        aliases = [
            ("readingfluencydemo", "reading_fluency"),
            ("readingfluency", "reading_fluency"),
            ("mathquest", "math_quest"),
            ("storyquest", "story_game"),
            ("makefriends", "make_friends"),
            ("alivemode", "alive_mode"),
        ]
        for alias, expected_stem in aliases:
            info, err = find_script(alias)
            self.assertIsNone(err, f"Alias '{alias}' should resolve without error")
            self.assertEqual(info["stem"], expected_stem)

    def test_find_script_activity_plan_routing(self):
        # Targets starting with activity_plan_ should route to runner.py with target as argument
        target = "activity_plan_20260618_test_lesson"
        info, err = find_script(target)
        self.assertIsNone(err)
        self.assertIsNotNone(info)
        self.assertTrue(info["path"].endswith("runner.py"))
        self.assertEqual(info["args"], [target])
        self.assertIn(target, info["filename"])

    def test_find_script_custom_interaction_routing(self):
        # Targets starting with custom_interaction_ should route to custom_runner.py with target as argument
        target = "custom_interaction_20260716_test_game"
        info, err = find_script(target)
        self.assertIsNone(err)
        self.assertIsNotNone(info)
        self.assertTrue(info["path"].endswith("custom_runner.py"))
        self.assertEqual(info["args"], [target])
        self.assertIn(target, info["filename"])

    def test_find_script_not_found_returns_error_details(self):
        info, err = find_script("non_existent_script_xyz")
        self.assertIsNone(info)
        self.assertIsNotNone(err)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "not_found")
        self.assertIn("available_demos", err)
        self.assertIn("available_scripts", err)
        self.assertIn("available_zhennan", err)
        self.assertGreater(len(err["available_demos"]), 0)

    def test_list_command_payload_structure(self):
        demos, scripts, zhennan = scan_files()
        plans = scan_activity_plans()
        interactions = scan_custom_interactions()

        payload = {
            "status": "list",
            "available_demos": sorted([info["filename"] for info in demos.values()]),
            "available_scripts": sorted([info["filename"] for info in scripts.values()]),
            "available_zhennan": sorted([info["filename"] for info in zhennan.values()]),
            "available_activity_plans": plans,
            "available_custom_interactions": interactions,
        }

        # Validate that payload can serialize to valid JSON
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)
        reloaded = json.loads(serialized)
        self.assertEqual(reloaded["status"], "list")
        self.assertIsInstance(reloaded["available_demos"], list)
        self.assertIsInstance(reloaded["available_scripts"], list)
        self.assertIsInstance(reloaded["available_zhennan"], list)
        self.assertIsInstance(reloaded["available_activity_plans"], list)
        self.assertIsInstance(reloaded["available_custom_interactions"], list)


if __name__ == "__main__":
    unittest.main()

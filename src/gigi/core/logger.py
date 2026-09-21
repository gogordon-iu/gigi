"""
Interaction and telemetry logger for Gigi robot.
"""

import os
import time
import json
import re
import uuid
import tempfile
from typing import Optional, Any, Dict
from pathlib import Path

from gigi.core.config import DATA_DIR


class InteractionLogger:
    """
    Manages session-based interaction logging for Gigi robot.
    Buffering is used until the user is recognized (face recognized),
    at which point a dedicated session folder is initialized and all
    logs are flushed to disk.
    """

    def __init__(self, character=None, base_dir: Optional[Path] = None):
        self.character = character
        self.user_name: Optional[str] = None
        self.user_id: Optional[str] = None
        self.script_name: Optional[str] = None
        self.session_dir: Optional[str] = None
        self.is_initialized: bool = False

        # Buffers for early logs
        self.conversation_buffer = []  # List of tuples (timestamp, speaker, text)
        self.visuals_buffer = []       # List of tuples (timestamp, type, event)
        self.variables_buffer: Dict[str, Any] = {}

        # Track state transitions to avoid visual event spamming
        self.last_logged_emotion: Optional[str] = None
        self.last_logged_gesture: Optional[str] = None

        self.data_dir = Path(base_dir) if base_dir else DATA_DIR

    def initialize_session(self, user_name: str, script_name: Optional[str] = None) -> None:
        """
        Initializes a user folder and script session directory.
        Flushes any buffered logs in memory.
        """
        if self.is_initialized:
            return

        print(f"[Logger] Initializing logging session for user '{user_name}' and script '{script_name}'...")
        self.user_name = user_name
        self.script_name = script_name

        users_root = self.data_dir / "users"
        try:
            users_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[Logger] Warning: Could not create Users root directory '{users_root}': {e}")

        # Load or create user mappings
        mapping_path = users_root / "user_mapping.json"
        mapping: Dict[str, str] = {}
        if mapping_path.exists():
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception as e:
                print(f"[Logger] Warning loading user mapping: {e}")

        clean_name = user_name.strip() if user_name else "Friend"
        if not clean_name:
            clean_name = "Friend"

        if clean_name not in mapping:
            if re.match(r"^face_\d{4}$", clean_name):
                suffix = clean_name.split("_")[1]
                uid = f"guest_{suffix}"
            elif clean_name.lower() in ["unknown", "friend"]:
                uid = f"guest_{str(uuid.uuid4())[:8]}"
            else:
                uid = f"user_{clean_name}_{str(uuid.uuid4())[:8]}"
            mapping[clean_name] = uid
            try:
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, indent=4)
            except Exception as e:
                print(f"[Logger] Warning: Error writing user mapping: {e}")

        self.user_id = mapping.get(clean_name, f"guest_{clean_name}")

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        safe_script_name = re.sub(r"[^\w\-]", "_", script_name or "None")

        primary_dir = str(users_root / self.user_id / f"{timestamp}_{safe_script_name}")
        fallback_paths = [
            primary_dir,
            os.path.join(os.path.expanduser("~"), ".gigi", "users", self.user_id, f"{timestamp}_{safe_script_name}"),
            os.path.join(tempfile.gettempdir(), "gigi_logs", self.user_id, f"{timestamp}_{safe_script_name}"),
        ]

        success = False
        for target_dir in fallback_paths:
            try:
                os.makedirs(target_dir, exist_ok=True)
                test_file = os.path.join(target_dir, ".write_test")
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("test")
                os.remove(test_file)

                self.session_dir = target_dir
                success = True
                break
            except Exception as e:
                print(f"[Logger] Warning: Target directory '{target_dir}' is not writable: {e}")

        if success:
            self.is_initialized = True
            print(f"[Logger] Session folder initialized: {self.session_dir}")
            self._flush_buffers()
        else:
            print("[Logger] Critical Error: Could not initialize any writable session folder.")

    def _flush_buffers(self) -> None:
        """Flushes in-memory buffers to disk."""
        if not self.is_initialized or not self.session_dir:
            return

        if self.conversation_buffer:
            conversation_file = os.path.join(self.session_dir, "conversation.txt")
            try:
                with open(conversation_file, "a", encoding="utf-8") as f:
                    for ts, speaker, text in self.conversation_buffer:
                        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
                        f.write(f"[{time_str}] {speaker}: {text}\n")
                self.conversation_buffer.clear()
            except Exception as e:
                print(f"[Logger] Error flushing conversation buffer: {e}")

        if self.visuals_buffer:
            visuals_file = os.path.join(self.session_dir, "visuals.txt")
            try:
                with open(visuals_file, "a", encoding="utf-8") as f:
                    for ts, event_type, val in self.visuals_buffer:
                        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
                        f.write(f"[{time_str}] {event_type}: {val}\n")
                self.visuals_buffer.clear()
            except Exception as e:
                print(f"[Logger] Error flushing visuals buffer: {e}")

        if self.variables_buffer:
            variables_file = os.path.join(self.session_dir, "variables.json")
            try:
                existing = {}
                if os.path.exists(variables_file):
                    with open(variables_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing.update(self.variables_buffer)
                with open(variables_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=4)
                self.variables_buffer.clear()
            except Exception as e:
                print(f"[Logger] Error flushing variables buffer: {e}")

    def log_conversation(self, speaker: str, text: str) -> None:
        """Logs a conversation turn."""
        text = text.strip()
        if not text:
            return

        ts = time.time()
        if not self.is_initialized:
            self.conversation_buffer.append((ts, speaker, text))
        else:
            conversation_file = os.path.join(self.session_dir, "conversation.txt")
            try:
                with open(conversation_file, "a", encoding="utf-8") as f:
                    time_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    f.write(f"[{time_str}] {speaker}: {text}\n")
            except Exception as e:
                print(f"[Logger] Error writing conversation log: {e}")

    def log_visuals(self, emotion: Optional[str] = None, gesture: Optional[str] = None) -> None:
        """Logs visual state changes (to prevent duplicate spamming)."""
        ts = time.time()
        log_entries = []

        if emotion is not None and emotion != self.last_logged_emotion and emotion != "Unknown":
            self.last_logged_emotion = emotion
            log_entries.append(("Emotion", emotion))

        if gesture is not None and gesture != self.last_logged_gesture and gesture != "Unknown":
            self.last_logged_gesture = gesture
            log_entries.append(("Gesture", gesture))

        if not log_entries:
            return

        if not self.is_initialized:
            for event_type, val in log_entries:
                self.visuals_buffer.append((ts, event_type, val))
        else:
            visuals_file = os.path.join(self.session_dir, "visuals.txt")
            try:
                with open(visuals_file, "a", encoding="utf-8") as f:
                    time_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    for event_type, val in log_entries:
                        f.write(f"[{time_str}] {event_type}: {val}\n")
            except Exception as e:
                print(f"[Logger] Error writing visuals log: {e}")

    def log_variable(self, name: str, value: Any) -> None:
        """Logs an interaction-specific variable."""
        if not self.is_initialized:
            self.variables_buffer[name] = value
        else:
            variables_file = os.path.join(self.session_dir, "variables.json")
            try:
                existing = {}
                if os.path.exists(variables_file):
                    with open(variables_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing[name] = value
                with open(variables_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=4)
            except Exception as e:
                print(f"[Logger] Error writing variable log: {e}")

    def log_interaction_variables(self, dict_vars: Dict[str, Any]) -> None:
        """Logs multiple variables at once."""
        for name, value in dict_vars.items():
            self.log_variable(name, value)

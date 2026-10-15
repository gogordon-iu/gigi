# Project Bug Log

This file tracks all bugs encountered and resolved within this project. Each entry contains a single-sentence bug description and a single-sentence solution.

---

### [BUG-261001-01] 2026-10-01 | `/lib/systemd/system/ssh.service` & `Setup/prepare_factory_image.sh`
- **Bug**: SSH service failed on first boot following robot disk sanitization because scrubbing `/etc/ssh/ssh_host_*` keys caused `ExecStartPre=/usr/sbin/sshd -t` to exit with failure before keys were regenerated.
- **Solution**: Configured a systemd drop-in override (`/etc/systemd/system/ssh.service.d/override.conf`) running `ExecStartPre=/usr/bin/ssh-keygen -A` to guarantee unique host keys are always automatically synthesized prior to sshd validation.

### [BUG-261001-02] 2026-10-01 | `/etc/systemd/system/gigi-bluetooth.service` & `Setup/clone_and_sanitize_emmc.sh`
- **Bug**: Gigi Bluetooth hub and expressive face failed to start on cloned eMMC images because `/etc/systemd/system/gigi-bluetooth.service` was corrupted with null bytes during live disk capture, and `check-new-release-gtk` threw desktop crash popups on offline boot.
- **Solution**: Restored the complete `gigi-bluetooth.service` unit file, permanently disabled Ubuntu desktop update popups via `Prompt=never` and removing `update-notifier.desktop`, and provisioned local network profiles for headless access.

### [BUG-261002-01] 2026-10-02 | `/etc/systemd/system/gigi-bluetooth.service` & `src/gigi/core/daemon.py`
- **Bug**: Gigi failed to start and greet at boot because having `After=graphical.target` on a service wanted by `multi-user.target` caused systemd to skip the service entirely due to a circular ordering cycle, and root execution inherited a stale `/root/.Xauthority` cookie that failed X11 authentication.
- **Solution**: Removed `graphical.target` from `After=` in `gigi-bluetooth.service` to resolve the systemd cycle, and configured `daemon.py` and `start_bluetooth_hub.sh` to explicitly resolve `/home/orangepi/.Xauthority` with dynamic polling for display server readiness.

### [BUG-261002-02] 2026-10-02 | `/home/orangepi/Code/gigi/.venv` & `Setup/bt_agent.py`
- **Bug**: Newly cloned eMMC failed to start Gigi or accept Bluetooth connections because unflushed live filesystem buffers left 4,259 files in `.venv` filled with null bytes (crashing `hashlib`, `flask`, and `bt_listener` on import), while unhandled prompt patterns in `bluetoothctl` blocked incoming device pairings.
- **Solution**: Repaired the ext4 filesystem structure with `e2fsck`, cleanly replaced the corrupted `.venv` and desktop configurations from verified source trees, and upgraded `bt_agent.py` to automatically authorize all interactive confirmation prompts.

### [BUG-261007-01] 2026-10-07 | `src/gigi/core/robot.py`
- **Bug**: Core gaze tracking methods `follow_face` and `lookat_behavior` crashed with an unhandled `NameError` because `global_parts` was referenced without being imported from the face definitions module.
- **Solution**: Imported `global_parts` directly from `gigi.expression.face_definitions` in `src/gigi/core/robot.py` to restore facial part coordinate lookups.

### [BUG-261007-02] 2026-10-07 | `src/gigi/perception/vision.py`
- **Bug**: Object gaze directing via `Character.lookat_something()` crashed with `ModuleNotFoundError` during Story Game and Math Quest activities due to an obsolete `from faceDefinitions import global_parts` import statement.
- **Solution**: Replaced the invalid module reference with an absolute import from `gigi.expression.face_definitions`.

### [BUG-261007-03] 2026-10-07 | `src/gigi/perception/hearing.py`
- **Bug**: Instantiating pronunciation assessment in `Hearing` failed with `ModuleNotFoundError` because `CitrinetGOP` was imported from a nonexistent `citrinet_gop` module after modifying `sys.path`.
- **Solution**: Updated the import to reference `gigi.perception.pronunciation.CitrinetGOP` and removed redundant runtime `sys.path` manipulation.

### [BUG-261007-04] 2026-10-07 | `src/gigi/core/daemon.py`
- **Bug**: WebSocket clients were prematurely disconnected upon completing the HTTP handshake because `ConnectionWrapper.recv()` returned an empty byte string treated as EOF, and subsequent reconnection attempts were permanently blocked when the `exit` command failed to clear `active_client`.
- **Solution**: Refactored `ConnectionWrapper.recv()` to loop and buffer incoming frames after handshake completion and ensured `active_client` is reset to `None` under the active client lock upon handling the exit command.

### [BUG-261007-05] 2026-10-07 | `src/gigi/perception/vision.py`
- **Bug**: Launching vision processing with window display enabled halted the robot's main execution flow because `Vision.run_vision()` executed the GUI frame display loop synchronously on the calling thread.
- **Solution**: Defaulted `show_window` to `False` and offloaded the OpenCV display loop into a dedicated daemon thread managed by `stop_vision()`.

### [BUG-261007-06] 2026-10-07 | `pyproject.toml`
- **Bug**: Runtime execution of conversation embeddings, microphone streaming, script graph execution, and serial motor control failed on fresh environments because undeclared core dependencies `scikit-learn`, `sounddevice`, `soundfile`, `networkx`, and `pyserial` were missing from the package specification.
- **Solution**: Added all five required packages with minimum version constraints to the `dependencies` list in `pyproject.toml`.

### [BUG-261007-07] 2026-10-07 | `src/gigi/core/robot.py`
- **Bug**: `Character.run_character()` risked freezing the robot in an unrecoverable busy-wait loop if the audio playback thread terminated prematurely before assigning the start time container.
- **Solution**: Added audio worker thread liveness checks and a 3.0-second safety timeout to prevent infinite spin-waiting.

### [BUG-261007-08] 2026-10-07 | `src/gigi/interaction/manager.py`
- **Bug**: `InteractionManager.generate_turn()` retrieved tutoring strategies from `StrategyCatalog` but omitted them from the system prompt, causing pedagogical strategies to be ignored during LLM response generation.
- **Solution**: Interpolated the serialized strategy catalog string directly into the system prompt's instructions.

### [BUG-261007-09] 2026-10-07 | `src/gigi/core/logger.py`
- **Bug**: `InteractionLogger.initialize_session()` permanently rejected subsequent session initialization attempts after the first participant, causing all subsequent user data and dialogue to be written into the first user's directory.
- **Solution**: Added a `close_session()` cleanup method and updated `initialize_session()` to flush and transition directories whenever the participant name or script changes.

### [BUG-261007-10] 2026-10-07 | `src/gigi/expression/movement.py`
- **Bug**: `Movement.get_angle()` and `Movement.calc_normalized_angle()` assumed motor centers were the exact midpoint between PWM limits, causing physical posture and gestures to be biased away from calibrated neutral positions.
- **Solution**: Implemented piecewise linear interpolation using each servo's calibrated center PWM value.

### [BUG-261007-11] 2026-10-07 | `src/gigi/activities/mastermind/mastermind.py` & `src/gigi/activities/social/make_friends.py`
- **Bug**: Turn parsing in Mastermind and verbal verification in Make Friends used string inclusion checks that generated false positive matches on words containing substrings like "i" or "no".
- **Solution**: Replaced substring inclusion checks with regular expression word-boundary pattern matching in both activities.

### [BUG-261007-12] 2026-10-07 | `src/gigi/core/daemon.py`
- **Bug**: Preempting an active script in `ExecutionManager` triggered a race condition where the terminating process executed the new script's completion callback and prematurely resumed ambient alive mode.
- **Solution**: Flagged preempted processes to suppress unwanted ambient restarts and bound completion callbacks directly to each script's lifecycle monitor thread.

### [BUG-261007-13] 2026-10-07 | `src/gigi/expression/speech.py`
- **Bug**: Child voice pitch shifting in `Speech.save_audio_file()` relied on a fragile relative path that raised `FileNotFoundError` whenever the application was executed outside `src/gigi/expression/`.
- **Solution**: Replaced the relative path with an atomic temporary file created in the target directory and added cleanup error handling.

### [BUG-261007-14] 2026-10-07 | `src/gigi/core/robot.py` & `src/gigi/hardware/calibration.py`
- **Bug**: Ambient alive mode crashed on boot with an unhandled `JSONDecodeError` during `Character.__init__` if `lookat_calibrated.json` was corrupted or empty, halting the entire startup sequence before face or speech initialization.
- **Solution**: Refactored `load_lookat_calibration()` to safely validate candidate file contents with graceful exception handling and updated `robot.py` to use this safe accessor.

### [BUG-261007-15] 2026-10-07 | `src/gigi/core/daemon.py`
- **Bug**: `ambient_bootstrap()` gave up waiting for display `:0` after 30 seconds and launched `alive_mode.py` prematurely causing OpenCV/Pygame display initialization crashes, while direct RFCOMM socket listening reported an error when channel 1 was already bound by `rfcomm watch`.
- **Solution**: Extended X11 display polling to wait until the display server is actually active before starting ambient mode, and gracefully recognized kernel RFCOMM ownership of channel 1.

### [BUG-261007-16] 2026-10-07 | `src/gigi/expression/face_display.py` & `src/gigi/core/robot.py`
- **Bug**: Method `Face.combine_seuqences` contained a spelling typo that caused `AttributeError` when called using the standard spelling `combine_sequences`.
- **Solution**: Renamed the method to `combine_sequences`, updated calling code, and provided `combine_seuqences` as a backwards-compatibility alias.

### [BUG-261007-17] 2026-10-07 | `src/gigi/core/robot.py`
- **Bug**: `Character` redefined a duplicate 40-line `VoiceEncoderRKNN` class that shadowed the canonical implementation already imported from `gigi.perception.speaker_id`.
- **Solution**: Removed the redundant duplicate class definition from `robot.py` in favor of the imported canonical implementation.

### [BUG-261007-18] 2026-10-07 | `src/gigi/activities/reading_fluency/reading_fluency.py`
- **Bug**: `reading_fluency.py` reimplemented a duplicate 30-line `BackgroundFaceTracker` class rather than importing the shared utility from `gigi.activities.common`.
- **Solution**: Replaced the duplicate local class with an import of `BackgroundFaceTracker` from `gigi.activities.common`.

### [BUG-261007-19] 2026-10-07 | `src/gigi/verification/cli.py`
- **Bug**: `gigi-verify` CLI advertised `stt` and `tts` subcommands but failed with an invalid argument error because neither test function was registered in the argument parser choices or verifier dispatch table.
- **Solution**: Implemented `test_stt()` and `test_tts()` and registered both in `VERIFIERS` and the argument parser choices.

### [BUG-261007-20] 2026-10-07 | `src/gigi/activities/scripted/engine.py` & `script_assets.py`
- **Bug**: Dynamic loading of scripted story activities used unqualified `__import__()` calls that crashed with `ModuleNotFoundError` when scripts were loaded within the package hierarchy.
- **Solution**: Replaced `__import__()` with `importlib.import_module()` using package-qualified fallback resolution.

### [BUG-261007-21] 2026-10-07 | `src/gigi/expression/speech.py`
- **Bug**: Opening `recorded_speech_filename` without context managers left dangling file handles on Windows that risked `PermissionError` file locking during speech recording.
- **Solution**: Wrapped all file loading and saving in `Speech` with `with open(..., encoding="utf-8") as f:` context managers.

### [BUG-261007-22] 2026-10-07 | `src/gigi/activities/base.py` & `src/gigi/activities/__init__.py`
- **Bug**: Abstract class `BaseActivity` was completely unused with zero activities implementing its lifecycle contract.
- **Solution**: Subclassed `BaseActivity` across `MastermindActivity`, `MathQuestActivity`, `StoryGameActivity`, and `MakeFriendsActivity` and exported them in `gigi.activities`.

### [BUG-261007-23] 2026-10-07 | `src/gigi/interaction/robot_interface.py` & `src/gigi/core/conversation.py`
- **Bug**: Activities directly accessed private `Conversation._call_npu()` and `RobotInterface` re-instantiated perception pipelines rather than reusing existing `Character` instances.
- **Solution**: Exposed a public `Conversation.chat()` method and added optional `character` injection to `RobotInterface.__init__()`.

### [BUG-261007-24] 2026-10-07 | `pyproject.toml`
- **Bug**: Optional tool dependencies `pyzbar` and `resemblyzer` were undeclared in the project package configuration.
- **Solution**: Added `verification` and `speaker_recognition` optional dependency groups to `pyproject.toml`.
### [BUG-261007-25] 2026-10-07 | `Setup/bt_agent.py`
- **Bug**: Bluetooth auto-pairing failed with smartphones during Secure Simple Pairing (SSP) because the agent declared capability `KeyboardOnly`, causing phones to generate and display a random 6-digit passkey while `bt_agent.py` blindly submitted the hardcoded PIN `198420`.
- **Solution**: Changed agent capability to `NoInputNoOutput` so BlueZ negotiates headless "Just Works" pairing without passkey entry mismatches.

### [BUG-261007-26] 2026-10-07 | `/boot/orangepiEnv.txt` & `emmc/flash_emmc.py`
- **Bug**: Freshly flashed eMMC failed to boot on Orange Pi 5 Pro with a blank screen because `/boot/orangepiEnv.txt` contained null bytes that prevented U-Boot from resolving the Device Tree (`fdtfile`) and root partition UUID, while loose mezzanine connector pin contact dropped disk communication into `No Media`.
- **Solution**: Restored the clean U-Boot configuration with valid DTB path and root filesystem UUID, and diagnosed the high-density mezzanine connector seating requirement.

### [BUG-261009-01] 2026-10-09 | `src/gigi/core/robot.py`
- **Bug**: `Character.__init__` defined a mutable default argument `languages=['en']` that caused mutated language configurations to inadvertently persist across subsequent robot instances.
- **Solution**: Defaulted `languages=None` and initialized `self.languages = list(languages) if languages is not None else ['en']`.

### [BUG-261009-02] 2026-10-09 | `src/gigi/perception/vision.py`
- **Bug**: Submodule import `from gigi.perception import vision_helper as vh` failed when `vision.py` was imported without prior package attribute binding.
- **Solution**: Replaced fragile import with canonical `import gigi.perception.vision_helper as vh` and replaced bare `except:` blocks with `except Exception:`.

### [BUG-261009-03] 2026-10-09 | `src/gigi/perception/hearing.py` & `src/gigi/expression/speech.py`
- **Bug**: Multiple bare `except:` statements caught `BaseException` including `KeyboardInterrupt` and `SystemExit`, preventing clean thread shutdown and signal handling.
- **Solution**: Replaced bare `except:` statements with specific exception types (`queue.Empty`, `queue.Full`, `Exception`).

### [BUG-261009-04] 2026-10-09 | `src/gigi/activities/math_quest/math_quest.py`, `mastermind.py`, & `story_game.py`
- **Bug**: Activities crashed with `AttributeError` on headless systems or whenever `HAS_FACE = False` due to unguarded `gigi.face` method calls, and activity adapter classes could not inject pre-existing robot instances.
- **Solution**: Guarded all `gigi.face` access with `if gigi.face:` checks, added `gigi_instance=None` injection, and ensured `gigi.movement.release()` is called in `finally:` blocks.

### [BUG-261009-05] 2026-10-09 | `src/gigi/core/daemon.py`
- **Bug**: X11 authentication hardcoded `/home/orangepi/.Xauthority`, failing under other user accounts, while `active_client` was accessed with inconsistent locking and a nested `global` declaration in the command processor.
- **Solution**: Implemented dynamic `get_xauthority_path()` resolving `XAUTHORITY`, `~/.Xauthority`, and `/home/orangepi/.Xauthority`, and encapsulated active client lifecycle with thread-safe lock helpers.

### [BUG-261009-06] 2026-10-09 | `src/gigi/interaction/web/app.py`
- **Bug**: Activity planner web service saved generated plans to `'activity_plan.json'` in the active process working directory rather than the configured project data path.
- **Solution**: Resolved save directory to `DATA_DIR / "activity_plan.json"` with auto-creation of parent directories and returned the absolute path.

### [BUG-261009-07] 2026-10-09 | `src/gigi/verification/hardware/verify_motors.py`
- **Bug**: Module imported `time` twice consecutively.
- **Solution**: Removed the redundant duplicate `import time` statement.

### [BUG-261009-08] 2026-10-09 | `src/gigi/perception/whisper_helper.py`, `hearing.py`, & `speech.py`
- **Bug**: Linear interpolation audio resampling imposed high CPU overhead on the RK3588 and introduced high-frequency aliasing during speech recognition and synthesis.
- **Solution**: Upgraded audio resampling across all perception and expression pipelines to polyphase FIR filtering via `scipy.signal.resample_poly` with GCD rational factor calculation.

### [BUG-261009-09] 2026-10-09 | `src/gigi/activities/base.py`
- **Bug**: Activities lacked a standardized context manager lifecycle protocol, risking motors remaining energized with hold current and OpenCV capture loops leaking on unhandled exits.
- **Solution**: Implemented `__enter__` and `__exit__` context manager protocol on `BaseActivity` with guaranteed `cleanup_hardware()` releasing motors and sensors.

### [BUG-261009-10] 2026-10-09 | `src/gigi/core/conversation.py`
- **Bug**: Blocking synchronous HTTP requests to the LLM backend created 1.5–3.0s conversation pauses where the robot froze waiting for complete response generation before speaking.
- **Solution**: Implemented non-blocking token streaming (`stream_chat` and `stream_response`) that chunks incoming tokens into sentences on punctuation boundaries for immediate TTS viseme pre-buffering.

### [BUG-261009-11] 2026-10-09 | `src/gigi/perception/vision_helper.py`
- **Bug**: `ImprovedFaceCache` tracked faces without capacity limits or time-to-live expiration, risking unbounded memory growth during multi-hour deployment sessions.
- **Solution**: Added LRU capacity bounding (`max_faces=50`) and time-to-live eviction (`ttl_seconds=30.0`) to evict stale faces automatically.

### [BUG-261009-12] 2026-10-09 | `src/gigi/expression/speech.py`
- **Bug**: `_init_pygame_mixer()` crashed with `AttributeError` when `pygame` was absent or failed to load in headless/testing environments.
- **Solution**: Guarded mixer initialization with `if pygame is None or mixer is None:` and safely initialized `self.pygame_lock = threading.Lock()`.

### [BUG-261009-13] 2026-10-09 | `src/gigi/expression/speech.py`
- **Bug**: `Speech.__init__` unconditionally called `torch.hub.load()` when `TTS_MODEL == 'silero'` and `not IS_ROBOT` even when PyTorch was uninstalled.
- **Solution**: Guarded PyTorch Hub model loading with `if torch is not None and hasattr(torch, 'hub'):`, falling back gracefully to `self.model = None`.

### [BUG-261009-14] 2026-10-09 | `src/gigi/perception/hearing.py`
- **Bug**: `Hearing.__init__` raised `AttributeError: 'NoneType' object has no attribute 'Vad'` whenever the optional `webrtcvad` package was not installed.
- **Solution**: Guarded `self.vad` instantiation with `webrtcvad is not None` checks and added fallback energy-based thresholding in `is_speech()`.

### [BUG-261009-15] 2026-10-09 | `src/gigi/activities/scripted/script_assets.py`
- **Bug**: Script discovery scanned framework infrastructure files and failed to extract activity declarations formatted with Python type annotations.
- **Solution**: Excluded framework scripts (`engine.py`, `script_graph.py`, `script_assets.py`) from story scanning and upgraded discovery to regex matching.

### [BUG-261013-01] 2026-10-13 | `src/gigi/activities/common/utils.py` & `src/gigi/activities/reading_fluency/reading_fluency.py`
- **Bug**: `reading_fluency.py` called `extract_name(heard_text, gigi=gigi)` with a `gigi=` keyword argument while `extract_name()` only accepted `robot=`, raising a `TypeError` whenever a learner spoke their name.
- **Solution**: Updated `extract_name()` to accept both `robot` and `gigi` keyword arguments as aliases for the robot instance.

### [BUG-261013-02] 2026-10-13 | `src/gigi/hardware/camera.py`
- **Bug**: Camera auto-discovery on Orange Pi 5 Pro (RK3588) locked onto non-capture V4L2 ISP/metadata `/dev/video*` nodes because it only checked `cap.isOpened()` without verifying frame capture or scanning past index 4.
- **Solution**: Used `cv2.CAP_V4L2` on Linux, extended port scanning up to 12 device nodes, and required `cap.read()` to return a non-empty frame during auto-detection.

### [BUG-261013-03] 2026-10-13 | `src/gigi/hardware/npu.py`, `src/gigi/perception/pronunciation.py`, & `src/gigi/perception/hearing.py`
- **Bug**: Importing `rknnlite.api.RKNNLite` mutated Python's global `logging` level tables (`_nameToLevel` and `_levelToName`), and failed `load_rknn()` or `init_runtime()` calls leaked native RK3588 NPU contexts.
- **Solution**: Snapshotted and restored global `logging` level mappings around `RKNNLite` imports, released native `rknn` contexts on initialization failures, and serialized NPU inference with a thread lock.

### [BUG-261013-04] 2026-10-13 | `src/gigi/hardware/motors.py`
- **Bug**: `MotorController.set_pwm()` accepted out-of-range PCA9685 channels and un-clamped 12-bit tick counts that could write to unintended I2C registers or wrap PWM duty cycles.
- **Solution**: Added channel bounds validation (`0 <= channel <= 15`), clamped `on`/`off` ticks to `[0, 4096]`, guarded non-positive PWM frequencies, and serialized I2C register access with a reentrant lock.

### [BUG-261013-05] 2026-10-13 | `src/gigi/expression/movement.py`
- **Bug**: Invoking `python -m gigi.expression.movement release` drove all physical servos to home position for 1.5 seconds inside `Movement.__init__()` before releasing PWM hold current, and `interpolate_sequence()` failed to look up integer channel keys stored as strings.
- **Solution**: Added `auto_home: bool = True` to `Movement.__init__()` (passing `auto_home=False` for `release`/`stop`/`home` CLI commands), normalized integer channel string lookups, and held final keyframe positions across multi-joint trajectories.

### [BUG-261013-06] 2026-10-13 | `src/gigi/expression/visemes.py`
- **Bug**: `Visemes.run_viseme()` spun indefinitely in `while start_time_container[0] is None:` if the speech thread failed before setting the timestamp, and `set_viseme()` did not clamp out-of-range audio envelope samples.
- **Solution**: Clamped envelope samples to `[0.0, 1.0]` in `set_viseme()` and added a `speech_thread.is_alive()` check and 3.0-second startup timeout to `run_viseme()`.

### [BUG-261013-07] 2026-10-13 | `src/gigi/expression/speech.py`
- **Bug**: `Speech.update_audio_objects()` left a `pass` statement in the `sounddevice` branch when loading pre-recorded audio files (`KeyError` on playback), failed to update `samplerate` after resampling, and overwrote source asset WAV files in-place during sample-rate conversion.
- **Solution**: Populated `self.audio_objects[audio_file]` for `sounddevice`, updated `samplerate` to `self.speaker_sample_rate` after resampling, and wrote resampled audio to the destination path instead of mutating source assets.

### [BUG-261013-08] 2026-10-13 | `src/gigi/perception/vision.py` & `src/gigi/perception/vision_helper.py`
- **Bug**: Face cache cleanup in `Vision.run_vision()` checked `current_time % 30 == 0` on a `time.time()` float (which never evaluated to zero), `stop_vision()` left `active_workers` flags set to `True` preventing worker restarts, and `timestamped_data` grew without bound.
- **Solution**: Replaced float modulo with elapsed-time tracking (`_last_cache_cleanup`), reset `active_workers` and closed MediaPipe graphs on shutdown, and bounded `timestamped_data` to 300 entries while pruning stale `last_data` keys.

### [BUG-261013-09] 2026-10-13 | `src/gigi/perception/hearing.py` & `src/gigi/perception/whisper_helper.py`
- **Bug**: `SenseVoiceRKNNTranscriber` reloaded the SentencePiece BPE model from eMMC on every 2-second audio chunk, `listen_fluid()` mutated `self.silence_duration` permanently, and `resample_audio()` cast float filter outputs to `int16` without clipping overflow peaks.
- **Solution**: Cached `SentencePieceProcessor` in `SenseVoiceRKNNTranscriber.__init__()`, restored `silence_duration` in a `finally` block, resolved model paths via `RESOURCES_DIR`, and clipped resampled audio to `[-32768, 32767]` before `int16` conversion.

### [BUG-261013-10] 2026-10-13 | `src/gigi/activities/scripted/engine.py` & `src/gigi/activities/scripted/lego.py`
- **Bug**: `engine.py` crashed with `IndexError` on empty `listen`/`look` nodes, omitted `gigi.stop_character()` on exit, and `lego.py` contained node type typos (`'speka'`, `'speaker'`, `'puase'`) on nodes lacking speech or pause payloads.
- **Solution**: Guarded empty `listen`/`look` transitions in `engine.py`, called `gigi.stop_character()` and `gigi.movement.release()` on exit, and corrected the malformed node `type` lists in `lego.py`.

### [BUG-261013-11] 2026-10-13 | `src/gigi/core/robot.py`
- **Bug**: `Character.stop_character()` did not release servo PWM channels, `lookat_coordinate()` re-solved `scipy.interpolate.Rbf` matrices on every 20 Hz tracking frame, and `update_egocentric_locations()` rewrote `egocentric_locations.json` to eMMC on every frame even when face angles had not changed.
- **Solution**: Released movement servos inside `stop_character()`, cached compiled `Rbf` interpolators on `self._rbf_cache`, cancelled timeout `threading.Timer` objects in `finally` blocks, and restricted egocentric JSON writes to atomic updates when angles change by more than 0.05 radians.

### [BUG-261013-12] 2026-10-13 | `src/gigi/core/daemon.py`
- **Bug**: `daemon.py` sent `{"status": "ready"}` before completing the WebSocket HTTP 101 handshake, ignored WebSocket Ping frames, spawned `rfcomm show` 10 times per second during polling, and split `nmcli -t` output on the first colon which broke SSIDs containing colons.
- **Solution**: Completed the WebSocket handshake before sending ready status, handled Ping (`0x9`) and Pong (`0xA`) frames with a 10 MB buffer cap and send lock, cached `is_rfcomm_connected()` for 1.0s, sanitized `find_script()` against path traversal, and parsed `nmcli` lines via `rsplit(":", 2)`.

### [BUG-261013-13] 2026-10-13 | `src/gigi/core/logger.py` & `src/gigi/core/config.py`
- **Bug**: `InteractionLogger` lacked thread synchronization across concurrent vision/speech threads and allowed unsanitized learner names in session directory paths, while `config.py` crashed at import time if `GIGI_TCP_PORT` or `GIGI_RFCOMM_CHANNEL` contained non-integer strings.
- **Solution**: Synchronized `InteractionLogger` methods with a `threading.RLock()`, sanitized user names with `re.sub(r"[^\w\-]", "_", ...)`, and parsed integer environment variables through a fault-tolerant `_env_int()` helper.

### [BUG-261013-14] 2026-10-13 | `src/gigi/interaction/custom_runner.py`, `src/gigi/interaction/runner.py`, & `src/gigi/interaction/web/app.py`
- **Bug**: `custom_runner.py` exposed unrestricted Python builtins to `eval`/`exec`, `runner.py` exited without calling `gigi.stop_character()`, and `web/app.py` ran with `debug=True` hardcoded while crashing with `AttributeError` on non-dict JSON bodies.
- **Solution**: Restricted `eval`/`exec` globals to `SAFE_BUILTINS`, added `try/except`-isolated `gigi.stop_character()` cleanup in `runner.py` and `custom_runner.py`, validated `request.get_json(silent=True)` as a `dict`, and defaulted Flask debug mode to `False`.

### [BUG-261014-01] 2026-10-14 | `Setup/start_bluetooth_hub.sh`, `Setup/clone_and_sanitize_emmc.sh`, & `Setup/sanitize_external_emmc.sh`
- **Bug**: Desktop autostart of `blueman-applet` and persisted `systemd-rfkill` state soft-blocked `bt_default` on boot (pulling Orange Pi 5 Pro GPIO 29 low and wiping uploaded `BCM4345C5.hcd` RAM firmware), while `/var/crash/_usr_bin_bluetoothctl.0.crash` triggered Ubuntu's "System program problem detected" modal popup via `update-notifier`/`apport` and X11 DPMS blanked the screen after 600 seconds.
- **Solution**: Disabled `blueman.desktop`, `update-notifier.desktop`, `xscreensaver.desktop`, `apport`, and X11 DPMS standby, purged `/var/crash/*`, forced `/var/lib/systemd/rfkill/*bluetooth*` to `0`, and added automatic `brcm_patchram_plus` firmware reload when Bluetooth was soft-blocked or missing a default controller.

### [BUG-261014-02] 2026-10-14 | `Setup/bt_agent.py`
- **Bug**: `bluetoothctl` 5.64 auto-registered a default `DisplayYesNo` agent at launch causing a subsequent interactive `agent NoInputNoOutput` command to fail with `Agent is already registered`, paired phones remained `Trusted: no` which blocked incoming RFCOMM Channel 1 connections, and writing `trust <MAC>` to `bluetoothctl` stdin on `[NEW] Device` collided with active `[agent]` PIN/passkey prompts.
- **Solution**: Passed `--agent NoInputNoOutput` directly on the `bluetoothctl` command line at process launch and spawned a separate `bluetoothctl trust <MAC>` subprocess only upon completed `Paired: yes` events so `process.stdin` remains dedicated to answering agent prompts.

### [BUG-261014-03] 2026-10-14 | `Setup/start_bluetooth_hub.sh` & `Setup/bt_agent.py`
- **Bug**: After sanitizing `/var/lib/bluetooth/*` and reloading `BCM4345C5.hcd` firmware via `brcm_patchram_plus`, the Bluetooth controller advertised its hardware firmware default name (`BCM4345C5 Ampak_CL1...`) instead of `orangepi5pro`.
- **Solution**: Added `hciconfig hci0 name orangepi5pro` in `start_bluetooth_hub.sh` and `system-alias orangepi5pro` in `bt_agent.py` during adapter initialization.



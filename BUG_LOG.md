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


"""
Robot kinematics, trajectory smoothing, and motor execution for Gigi.
Translates normalized motor commands [-1.0, 1.0] into hardware PWM values.
"""

import sys
import time
import math
import logging
import threading
from copy import deepcopy
from typing import Dict, List, Union, Optional, Any

from gigi.hardware.motors import PCA9685Controller
from gigi.hardware.calibration import load_motor_calibration
from gigi.expression.gesture_definitions import BASIC_GESTURES

logger = logging.getLogger(__name__)


class Movement:
    """
    Manages motor positioning, trajectory interpolation, and gesture execution.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.motors = PCA9685Controller()
        self.motor_map = load_motor_calibration()
        self.current_positions: Dict[str, int] = {
            m: self.motor_map[m]["center"]
            for m in self.motor_map
            if self.motor_map[m].get("calibrated", False)
        }
        self.home_position()

    def move_single_motor(self, motor: str, angle: Union[int, float]) -> bool:
        """Moves a single motor to target angle."""
        if motor in self.motor_map:
            channel = self.motor_map[motor]["channel"]
            raw_angle = self.get_angle(angle, motor)
            clip_angle = max(min(raw_angle, self.motor_map[motor]["max"]), self.motor_map[motor]["min"])
            self.current_positions[motor] = clip_angle
            self.motors.set_pwm(channel, 0, clip_angle)
            return True
        return False

    def get_angle(self, angle: Union[int, float], motor: str) -> int:
        """Translates normalized angle [-1.0, 1.0] or raw PWM into bounds-checked raw PWM."""
        if motor not in self.motor_map:
            return int(angle)
        m_min = self.motor_map[motor]["min"]
        m_max = self.motor_map[motor]["max"]

        if isinstance(angle, int) and (angle > 10 or angle < -10):
            # Raw PWM value
            return max(min(angle, m_max), m_min)
        else:
            # Normalized float in [-1.0, 1.0]
            clamped = max(min(float(angle), 0.95), -0.95)
            raw = int(((clamped + 1.0) / 2.0) * (m_max - m_min) + m_min)
            return raw

    def calc_normalized_angle(self, motor: str) -> float:
        """Returns the normalized angle [-1.0, 1.0] of current position."""
        if motor not in self.motor_map:
            return 0.0
        angle = self.current_positions.get(motor, self.motor_map[motor]["center"])
        m_min = self.motor_map[motor]["min"]
        m_max = self.motor_map[motor]["max"]
        if m_max == m_min:
            return 0.0
        return float(2.0 * (angle - m_min) / (m_max - m_min) - 1.0)

    def move_motors(self, motors_: Dict[Union[str, int], Union[float, int]]) -> None:
        """Sets multiple motors simultaneously."""
        for motor, angle in motors_.items():
            if isinstance(motor, int):
                self.current_positions[str(motor)] = int(angle)
                self.motors.set_pwm(motor, 0, int(angle))
            elif isinstance(motor, str):
                raw_angle = self.get_angle(angle, motor)
                self.current_positions[motor] = raw_angle
                if self.verbose:
                    logger.debug(f"Moving {motor} (ch {self.motor_map[motor]['channel']}) to {raw_angle}")
                self.motors.set_pwm(self.motor_map[motor]["channel"], 0, raw_angle)

    def smooth_sequence(
        self, motors_: Dict[str, float], duration: float = 2.0, number_steps: int = 60
    ) -> List[Dict[str, Any]]:
        """Generates a smooth cosine-eased trajectory from current positions to targets."""
        current_motors = self.current_positions
        seq = []
        delta_t = duration / max(number_steps - 1, 1)

        for t in range(number_steps):
            ratio = t / (number_steps - 1) if number_steps > 1 else 1.0
            mu2 = (1.0 - math.cos(ratio * math.pi)) / 2.0
            seq_step = {"time": delta_t * t, "motors": {}}

            for motor, angle in motors_.items():
                if motor == "duration":
                    continue
                target_raw = self.get_angle(angle, motor)
                start_raw = current_motors.get(
                    motor,
                    self.motor_map.get(motor, {}).get("center", 0),
                )
                val = start_raw * (1.0 - mu2) + target_raw * mu2
                seq_step["motors"][motor] = int(round(val))
            seq.append(deepcopy(seq_step))

        return seq

    def is_sparse_sequence(self, motor_seq: List[Dict[str, Any]]) -> bool:
        """Checks if keyframes in sequence are sparse and require interpolation."""
        if not isinstance(motor_seq, list) or len(motor_seq) == 0:
            return False
        if len(motor_seq) == 1:
            return True
        for i in range(len(motor_seq) - 1):
            if motor_seq[i + 1]["time"] - motor_seq[i]["time"] > 0.15:
                return True
        return False

    def interpolate_sequence(
        self, motor_seq: List[Dict[str, Any]], steps_per_second: int = 30
    ) -> List[Dict[str, Any]]:
        """Dense cosine interpolation across multi-keyframe gesture sequences."""
        if not isinstance(motor_seq, list) or not motor_seq:
            return motor_seq

        animated_motors = set()
        for kf in motor_seq:
            if isinstance(kf, dict) and "motors" in kf:
                for m in kf["motors"].keys():
                    if isinstance(m, str) and m in self.motor_map:
                        animated_motors.add(m)
                    elif isinstance(m, int):
                        animated_motors.add(m)

        if not animated_motors:
            return motor_seq

        times = [kf["time"] for kf in motor_seq if isinstance(kf, dict) and "time" in kf]
        if not times:
            return motor_seq
        end_time = max(times)
        if end_time <= 0:
            return motor_seq

        control_points = {}
        for motor in animated_motors:
            curr_val = self.current_positions.get(
                motor, self.motor_map.get(motor, {}).get("center", 0)
            )
            pts = [(0.0, curr_val)]

            for kf in motor_seq:
                if isinstance(kf, dict) and "motors" in kf and motor in kf["motors"]:
                    target_val = kf["motors"][motor]
                    raw_target = self.get_angle(target_val, motor) if isinstance(motor, str) else target_val
                    pts.append((kf["time"], raw_target))

            pts.sort(key=lambda x: x[0])
            cleaned_pts = []
            for t, val in pts:
                if cleaned_pts and abs(cleaned_pts[-1][0] - t) < 1e-5:
                    cleaned_pts[-1] = (t, val)
                else:
                    cleaned_pts.append((t, val))
            control_points[motor] = cleaned_pts

        total_steps = max(int(end_time * steps_per_second) + 1, 2)
        dense_seq = []
        for i in range(total_steps):
            t = (i / (total_steps - 1)) * end_time
            step = {"time": round(t, 4), "motors": {}}
            for motor, pts in control_points.items():
                t_prev, val_prev = pts[0]
                t_next, val_next = pts[-1]
                for j in range(len(pts) - 1):
                    if pts[j][0] <= t <= pts[j + 1][0]:
                        t_prev, val_prev = pts[j]
                        t_next, val_next = pts[j + 1]
                        break

                if t_next > t_prev:
                    ratio = (t - t_prev) / (t_next - t_prev)
                    mu2 = (1.0 - math.cos(ratio * math.pi)) / 2.0
                    val = val_prev * (1.0 - mu2) + val_next * mu2
                else:
                    val = val_next
                step["motors"][motor] = int(round(val))
            dense_seq.append(step)

        return dense_seq

    def move_sequence(self, motor_seq: List[Dict[str, Any]], stop_event: Optional[threading.Event] = None) -> None:
        """Executes timed motor steps in sequence."""
        if self.is_sparse_sequence(motor_seq):
            motor_seq = self.interpolate_sequence(motor_seq)
        start_time = time.time()
        for seq in motor_seq:
            if stop_event and stop_event.is_set():
                break
            current_time = time.time() - start_time
            delay = seq["time"] - current_time
            if delay > 0:
                time.sleep(delay)
            self.move_motors(seq["motors"])

    def generate_movement(
        self,
        motor_seq: List[Dict[str, Any]],
        stop_event: threading.Event,
        stop_condition: Optional[Any] = None,
    ) -> None:
        """Worker function for threaded movement execution."""
        self.move_sequence(motor_seq, stop_event=stop_event)
        if isinstance(stop_condition, list) and "movement" in stop_condition:
            stop_event.set()

    def movement_thread(
        self,
        motor_data: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        stop_condition: Optional[Any] = None,
    ) -> threading.Thread:
        """Returns a thread that executes the given gesture or trajectory."""
        if isinstance(motor_data, list):
            motor_seq = motor_data
        elif isinstance(motor_data, str):
            motor_seq = BASIC_GESTURES.get(motor_data, [])
        elif isinstance(motor_data, dict):
            duration = motor_data.get("duration", 2.0)
            motor_seq = self.smooth_sequence(motors_=motor_data, duration=duration)
        else:
            motor_seq = []

        stop_event = threading.Event()
        t = threading.Thread(
            target=self.generate_movement,
            args=(motor_seq, stop_event, stop_condition),
            daemon=True,
        )
        return t

    def home_position(self, duration: float = 1.5) -> None:
        """Gently moves all calibrated motors to their neutral 0.0 center position."""
        home = {m: 0.0 for m in self.motor_map if self.motor_map[m].get("calibrated", False)}
        if not home:
            return
        home_seq = self.smooth_sequence(motors_=home, duration=duration)
        self.move_sequence(home_seq)

    def release(self) -> None:
        """Releases all PWM signals to prevent motor heating."""
        for v in self.motor_map.values():
            self.motors.set_pwm(v["channel"], 0, 4096)

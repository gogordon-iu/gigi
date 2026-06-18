from motorDefinitions import *
from movementDefinition import *
import time
import json
from copy import deepcopy
from os.path import exists
import threading


class Movement:
    def __init__(self, verbose=False):
        print("Initializing motors ...")
        self.verbose = verbose
        self.motors = Motors()
        if exists(CHARACTER_FOLDER + "motorData_calibrated.json"):
            self.motor_map = json.load(open(CHARACTER_FOLDER + "motorData_calibrated.json"))
            self.current_positions = {m: self.motor_map[m]['center'] for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        elif exists(CHARACTER_FOLDER + "motorData.json"):
            self.motor_map = json.load(open(CHARACTER_FOLDER + "motorData.json"))
            self.current_positions = {m: self.motor_map[m]['center'] for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        else:
            self.motor_map = {}
        self.home_position()

    def move_single_motor(self, motor, angle):
        if motor in self.motor_map.keys():
            channel = self.motor_map[motor]["channel"]
            clip_angle = max(min(angle, self.motor_map[motor]["max"]), self.motor_map[motor]["min"])
            self.motors.set_pwm(channel, 0, clip_angle)
            return True
        return False
    
    def get_angle(self, angle, motor):
        if isinstance(angle, int):  # the angle is the raw angle for the motor
            angle = max(min(angle, self.motor_map[motor]["max"]), self.motor_map[motor]["min"])
        else:                       # the angle is absolute in [min, max]
            angle = max(min(angle, 0.9), -0.9)
            angle = (int)(((angle + 1.0) / 2.0) * (self.motor_map[motor]["max"] - self.motor_map[motor]["min"]) + self.motor_map[motor]["min"])
        return angle
    
    def calc_normalized_angle(self, motor):
        angle = self.current_positions[motor]
        normalized_angle = (float)(2.0 * (angle - self.motor_map[motor]["min"]) / (self.motor_map[motor]["max"] - self.motor_map[motor]["min"]) - 1.0)
        return normalized_angle

    def move_motors(self, motors_):
        for motor, angle in motors_.items():
            if isinstance(motor, int):      # the motor is given by its channel, no safeguarding the angle
                self.current_positions[motor] = angle
                self.motors.set_pwm(motor, 0, angle)
            elif isinstance(motor, str):    # the motor is given by its name, clip the angle
                angle = self.get_angle(angle, motor)
                self.current_positions[motor] = angle
                if self.verbose:
                    print("Moving ", motor, self.motor_map[motor]["channel"], angle)
                self.motors.set_pwm(self.motor_map[motor]["channel"], 0, angle)
            else:
                if self.verbose:
                    print("Motor is not an int(chanel) nor a string(name). Did nothing.")

    def smooth_sequence(self, motors_, duration=2.0, number_steps=100):
        import math
        current_motors = self.current_positions
        seq = []
        start_time = 0.0
        end_time = duration
        delta_t = (end_time - start_time) / (number_steps - 1)
        for t in range(number_steps):
            seq_step = {
                "time": start_time + delta_t * t,
                "motors": {}
            }
            ratio = t / (number_steps - 1) if number_steps > 1 else 1.0
            mu2 = (1.0 - math.cos(ratio * math.pi)) / 2.0
            for motor, angle in motors_.items():
                if motor == "duration":
                    continue
                angle = self.get_angle(angle, motor)
                start_angle = current_motors.get(motor, self.motor_map[motor]["center"] if isinstance(motor, str) and motor in self.motor_map else 0.0)
                val = start_angle * (1.0 - mu2) + angle * mu2
                seq_step["motors"][motor] = int(round(val))
            seq.append(deepcopy(seq_step))
            
        return seq

    def is_sparse_sequence(self, motor_seq):
        if not isinstance(motor_seq, list) or len(motor_seq) == 0:
            return False
        if len(motor_seq) == 1:
            return True
        for i in range(len(motor_seq) - 1):
            if motor_seq[i+1]["time"] - motor_seq[i]["time"] > 0.15:
                return True
        return False

    def interpolate_sequence(self, motor_seq, steps_per_second=30):
        import math
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
            if isinstance(motor, str):
                curr_val = self.current_positions.get(motor, self.motor_map[motor]["center"])
            else:
                curr_val = self.current_positions.get(motor, 0.0)
            pts = [(0.0, curr_val)]

            for kf in motor_seq:
                if isinstance(kf, dict) and "motors" in kf and motor in kf["motors"]:
                    target_val = kf["motors"][motor]
                    if isinstance(motor, str):
                        raw_target = self.get_angle(target_val, motor)
                    else:
                        raw_target = target_val
                    pts.append((kf["time"], raw_target))

            pts.sort(key=lambda x: x[0])

            cleaned_pts = []
            for t, val in pts:
                if cleaned_pts and abs(cleaned_pts[-1][0] - t) < 1e-5:
                    cleaned_pts[-1] = (t, val)
                else:
                    cleaned_pts.append((t, val))
            control_points[motor] = cleaned_pts

        total_steps = int(end_time * steps_per_second) + 1
        if total_steps < 2:
            total_steps = 2
        dense_seq = []
        for i in range(total_steps):
            t = (i / (total_steps - 1)) * end_time
            step = {"time": round(t, 4), "motors": {}}
            for motor, pts in control_points.items():
                t_prev, val_prev = pts[0]
                t_next, val_next = pts[-1]
                for j in range(len(pts) - 1):
                    if pts[j][0] <= t <= pts[j+1][0]:
                        t_prev, val_prev = pts[j]
                        t_next, val_next = pts[j+1]
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

    def move_sequence(self, motor_seq):
        if self.is_sparse_sequence(motor_seq):
            motor_seq = self.interpolate_sequence(motor_seq)
        start_time = time.time()
        for seq in motor_seq:
            current_time = time.time() - start_time
            delay = seq['time'] - current_time
            if delay > 0:
                time.sleep(delay)
            self.move_motors(seq['motors'])

    def generate_movement(self, motor_seq, stop_event, stop_condition):
        start_time = time.time()
        for seq in motor_seq:
            current_time = time.time() - start_time
            delay = seq['time'] - current_time
            if delay > 0:
                time.sleep(delay)
            self.move_motors(seq['motors'])
            
            if stop_event.is_set():
                break
        if isinstance(stop_condition, list):
            if "movement" in stop_condition:
                stop_event.set()

    def movement_thread(self, motor_data, stop_condition=None):
        if isinstance(motor_data, list):     # this is a motor sequence
            motor_seq = motor_data
        elif isinstance(motor_data, str):       # this is the name of the sequence
            if motor_data in basic_sequences:
                motor_seq = basic_sequences[motor_data]
        elif isinstance(motor_data, dict):    # this is a single motors position
            if "duration" in motor_data:
                duration = motor_data["duration"]
                motor_seq = self.smooth_sequence(motors_=motor_data, duration=duration)
            else:
                motor_seq = self.smooth_sequence(motors_=motor_data)
        
        if self.is_sparse_sequence(motor_seq):
            motor_seq = self.interpolate_sequence(motor_seq)
            
        stop_event = threading.Event()
        t = threading.Thread(target=self.generate_movement, args=(motor_seq, stop_event, stop_condition))
        return t


    def home_position(self, duration=2.0):
        home = {m: 0.0 for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        if not home:
            return
        home_seq = self.smooth_sequence(motors_=home, duration=duration)
        self.move_sequence(home_seq)

    def release(self):
        for k, v in self.motor_map.items():
            self.motors.set_pwm(v["channel"], 0, -1)        

if __name__ == "__main__":
    movement = Movement(verbose=True)
    if len(sys.argv) > 1:
        move = sys.argv[1]
        if move == "home":
            movement.home_position()
            # movement.release()
        elif move == "release":
            movement.release()
        elif move in basic_sequences:
            movement_thread = movement.movement_thread(motor_data=move)
            movement_thread.start()
            movement_thread.join()
            movement.release()
    else:
        movement.home_position()

        movement_thread = movement.movement_thread(motor_data={"neck": 0.4})
        movement_thread.start()
        movement_thread.join()
        movement.release()
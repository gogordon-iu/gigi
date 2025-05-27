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
        if exists(CHARACTER_FOLDER + "motorData.json"):
            self.motor_map = json.load(open(CHARACTER_FOLDER + "motorData.json"))
            self.current_positions = {m: self.motor_map[m]['center'] for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        else:
            self.motor_map = {}

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
            for motor, angle in motors_.items():
                angle = self.get_angle(angle, motor)
                seq_step["motors"][motor] = ((t / (number_steps - 1)) * (angle - current_motors[motor]) + current_motors[motor])
                if isinstance(angle, int):
                    seq_step["motors"][motor] = (int)(seq_step["motors"][motor])
            seq.append(deepcopy(seq_step))
            
        return seq

    def move_sequence(self, motor_seq):
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
        stop_event = threading.Event()
        t = threading.Thread(target=self.generate_movement, args=(motor_seq, stop_event, stop_condition))
        return t


    def home_position(self):
        home = {m: 0.0 for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        # home = {"neck": 0.0}
        self.move_motors(motors_=home)

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
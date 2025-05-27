from motorDefinitions import *
import time
import json
from copy import deepcopy


class Movement:
    def __init__(self, verbose=False):
        print("Initializing motors ...")
        self.verbose = verbose
        self.motors = Motors()
        self.motor_map = json.load(open(CHARACTER_FOLDER + "motorData.json"))
        self.current_positions = {m: self.motor_map[m]['center'] for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}

    def move_single_motor(self, motor, angle):
        if motor in self.motor_map.keys():
            channel = self.motor_map[motor]["channel"]
            clip_angle = max(min(angle, self.motor_map[motor]["max"]), self.motor_map[motor]["min"])
            self.motors.set_pwm(channel, 0, clip_angle)
            return True
        return False
    
    def move_motors(self, motors_):
        for motor, angle in motors_.items():
            if isinstance(motor, int):      # the motor is given by its channel, no safeguarding the angle
                self.motors.set_pwm(motor, 0, angle)
            elif isinstance(motor, str):    # the motor is given by its name, clip the angle
                if isinstance(angle, int):  # the angle is the raw angle for the motor
                    angle = max(min(angle, self.motor_map[motor]["max"]), self.motor_map[motor]["min"])
                    self.current_positions[motor] = angle
                    self.motors.set_pwm(self.motor_map[motor]["channel"], 0, angle)
                else:                       # the angle is absolute in [min, max]
                    angle = max(min(angle, 0.9), -0.9)
                    angle = (int)(((angle + 1.0) / 2.0) * (self.motor_map[motor]["max"] - self.motor_map[motor]["min"]) + self.motor_map[motor]["min"])
                    print("Moving ", motor, self.motor_map[motor]["channel"], angle)
                    self.current_positions[motor] = angle
                    self.motors.set_pwm(self.motor_map[motor]["channel"], 0, angle)
            else:
                if self.verbose:
                    print("Motor is not an int(chanel) nor a string(name). Did nothing.")

    def smooth_sequence(self, motors_, duration, number_steps=10):
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

    def movement_thread(self, motor_seq, stop_event, stop_condition):
        start_time = time.time()
        for seq in motor_seq:
            current_time = time.time() - start_time
            delay = seq['time'] - current_time
            if delay > 0:
                time.sleep(delay)
            self.move_motors(seq['motors'])
            
            if stop_event.is_set():
                break
        if "movement" in stop_condition:
            stop_event.set()

    def home_position(self):
        home = {m: 0.0 for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        self.move_motors(motors_=home)

    def release(self):
        release = {m: -1 for m in self.motor_map.keys() if self.motor_map[m]['calibrated']}
        self.move_motors(motors_=release)
        

if __name__ == "__main__":
    move = sys.argv[1]
    if move == "home":
        movement = Movement()
        movement.home_position()
        movement.release()
    elif move == "release":
        movement = Movement()
        movement.release()
import math
import random

basic_sequences = {}

basic_sequences['home'] = [
    {
        "time": 1.0,
        "motors": {
            "neck": 0.0,
            "right_shoulder": 0.0,
            "left_shoulder": 0.0,
            "right_elbow": 0.0,
            "left_elbow": 0.0,
            "torso": 0.0
        }
    }
]

# wave hello
# raise right shoulder
# back and forth twice with right elbow
# lower right shoulder
basic_sequences["wave_hello"] = [
    {
        "time": 1.0,
        "motors": {
            "right_shoulder": 0.8,
            "right_elbow": 0.0
        }
    },
    {
        "time": 1.2,
        "motors": {
            "right_elbow": -0.8
        }
    },
    {
        "time": 1.4,
        "motors": {
            "right_elbow": 0.8
        }
    },
    {
        "time": 1.6,
        "motors": {
            "right_elbow": -0.8
        }
    },
    {
        "time": 1.8,
        "motors": {
            "right_elbow": 0.8
        }
    },
    {
        "time": 2.0,
        "motors": {
            "right_elbow": -0.8
        }
    },
    {
        "time": 3.0,
        "motors": {
            "right_shoulder": -0.8,
            "right_elbow": 0.0
        }
    }
]

basic_sequences["wave_right"] = basic_sequences["wave_hello"]

basic_sequences["wave_left"] = []
for s in basic_sequences["wave_right"]:
    new_s = {"time": s["time"], "motors": {}}
    for k, v in s["motors"].items():
        new_s["motors"][k.replace("right", "left")] = -v
    basic_sequences["wave_left"].append(new_s)

# Open arms
basic_sequences["open_arms"] = [
    {
        "time": 1.0,
        "motors": {
            "right_shoulder": 0.8,
            "left_shoulder": -0.8,
            "right_elbow": 0.0,
            "left_elbow": 0.0
        }
    },
    {
        "time": 1.5,
        "motors": {
            "right_elbow": 0.8,
            "left_elbow": -0.8
        }
    },
    {
        "time": 2.0,
        "motors": {
            "neck": 0.8
        }
    },
    {
        "time": 2.5,
        "motors": {
            "neck": -0.8
        }
    },
    {
        "time": 3.0,
        "motors": {
            "neck": 0.0,
            "right_shoulder": -0.8,
            "left_shoulder": 0.8,
            "right_elbow": 0.0,
            "left_elbow": 0.0
        }
    }
]

# Head movements
basic_sequences["look_from_side_to_side"] = [
    {'time': 1,
     'motors': {'neck': -0.8}},
    {'time': 2,
     'motors': {'neck': 0.8}},
    {'time': 3,
     'motors': {'neck': 0.0}}
]

basic_sequences['arms_down'] = [
    {'time': 1,
     'motors': {'right_elbow': 0.8,
                'left_elbow': -0.8,
                'right_shoulder': -0.8,
                'left_shoulder': 0.8}
                },
                ]

basic_sequences['arms_up'] = [
    {'time': 1,
     'motors': {'right_elbow': 0.0,
                'left_elbow': 0.0,
                'right_shoulder': 0.8,
                'left_shoulder': -0.8}},
                ]

basic_sequences['arms_up_and_down'] = [
    {'time': 1,
     'motors': {'right_elbow': 0.0,
                'left_elbow': 0.0,
                'right_shoulder': 0.8,
                'left_shoulder': 0.8}},
    {'time': 3,
     'motors': {'right_shoulder': -0.8,
                'left_shoulder': -0.8}},
    {'time': 4,
     'motors': {'right_shoulder': 0.0,
                'left_shoulder': 0.0}}
                ]

basic_sequences["clap"] = [
    {
        "time": 1.0,
        "motors": {'right_elbow': 0.8,
                'left_elbow': -0.8,
                'right_shoulder': 0.0,
                'left_shoulder': 0.0}
                },
    {
        "time": 1.2,
        "motors": {
            "right_elbow": -0.8,
            "left_elbow": 0.8,
        }
    },
    {
        "time": 1.4,
        "motors": {
            "right_elbow": 0.8,
            "left_elbow": -0.8,
        }
    },
    {
        "time": 1.6,
        "motors": {
            "right_elbow": -0.8,
            "left_elbow": 0.8,
        }
    },
    {
        "time": 1.8,
        "motors": {
            "right_elbow": 0.8,
            "left_elbow": -0.8,
        }
    },
    {
        "time": 2.0,
        "motors": {
            "right_shoulder": -0.8,
            "left_shoulder": 0.8
        }
    }
]

basic_sequences["arms_circle"] = [
    {
        "time": 0.2,
        "motors": {
            'right_elbow': 0.0,
            'left_elbow': 0.0,
            'right_shoulder': 0.8,
            'left_shoulder': -0.8
        }
    },
    {
        "time": 0.4,
        "motors": {
            'right_elbow': 0.8,
            'left_elbow': -0.8,
            'right_shoulder': 0.0,
            'left_shoulder': 0.0
        }
    },
    {
        "time": 0.6,
        "motors": {
            'right_elbow': 0.0,
            'left_elbow': 0.0,
            'right_shoulder': -0.8,
            'left_shoulder': 0.8
        }
    },
    {
        "time": 0.8,
        "motors": {
            'right_elbow': -0.8,
            'left_elbow': 0.8,
            'right_shoulder': 0.0,
            'left_shoulder': 0.0
        }
    },
    {
        "time": 1.0,
        "motors": {
            'right_elbow': 0.0,
            'left_elbow': 0.0,
            'right_shoulder': 0.8,
            'left_shoulder': -0.8
        }
    },
    {
        "time": 1.2,
        "motors": {
            'right_elbow': 0.8,
            'left_elbow': -0.8,
            'right_shoulder': 0.0,
            'left_shoulder': 0.0
        }
    },
    {
        "time": 1.4,
        "motors": {
            'right_elbow': 0.0,
            'left_elbow': 0.0,
            'right_shoulder': -0.8,
            'left_shoulder': 0.8
        }
    },
    {
        "time": 1.6,
        "motors": {
            'right_elbow': -0.8,
            'left_elbow': 0.8,
            'right_shoulder': 0.0,
            'left_shoulder': 0.0
        }
    },
]

basic_sequences['scare'] = [
    {'time': 0,
     'motors': {'right_elbow': 0.0,
                'left_elbow': 0.0,
                'right_shoulder': 0.8,
                'left_shoulder': -0.8,
                "torso": 0.2}},
    {'time': 3,
     'motors': {"neck": 0.0,
            "right_shoulder": 0.0,
            "left_shoulder": 0.0,
            "right_elbow": 0.0,
            "left_elbow": 0.0,
            "torso": 0.0}}
]

basic_sequences["look_left"] = [
    {'time': 1,
     'motors': {'neck': 0.8}}
]

basic_sequences["look_right"] = [
    {'time': 1,
     'motors': {'neck': -0.8}}
]

basic_sequences["jorge_yellow_dance"] = [
    {
        "time": 3.0,
        'motors': {'right_elbow': 0.0,
                'left_elbow': 0.0,
                'right_shoulder': 1.0,
                'left_shoulder': -1.0},
    },
    {
        "time": 8,
        "motors": {
            "torso": 1.0,
        }
    },
    {
        "time": 12,
        "motors": {
            "torso": 0.0
        }
    },
    {
        "time": 16,
        "motors": {
            "torso": 1.0
        }
    },
    {
        "time": 19,
        "motors": {
            "torso": 0.0
        }
    },
    {
        "time": 22,
        "motors": {
            "torso": 1.0
        }
    },
    {
        "time": 30,
        "motors": {
            'right_shoulder': -1.0,
            'left_shoulder': 0.5,
        }
    },
    {
        "time": 31,
        "motors": {
            'right_shoulder': -0.6,
            'left_shoulder': 1.0,
        }
    },
    {
        "time": 35,
        "motors": {
            'right_shoulder': 1.0,
            'left_shoulder': -0.5,
        }
    },
    {
        "time": 36,
        "motors": {
            'right_shoulder': 0.6,
            'left_shoulder': -1.0,
        }
    },
    {
        "time": 38,
        "motors": {
            'right_shoulder': -0.7,
            'left_shoulder': 0.0,
        }
    },
    {
        "time": 39,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': 0.7,
        }
    },
        {
        "time": 40,
        "motors": {
            'right_shoulder': 0.7,
            'left_shoulder': -1.0,
        }
    },
    {
        "time": 41,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': -0.7,
        }
    },
    {
        "time": 42,
        "motors": {
            'right_shoulder': -1.0,
        }
    },
    {
        "time": 43,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': 0.0,
        }
    },
    {
        "time": 44,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': 0.2,
            'torso': 0.6
        }
    },
    {
        "time": 46,
        "motors": {
            'torso': 0.0,
            'right_elbow': 0.2,
            'left_elbow': -0.2,
        }
    },
    {
        "time": 48,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': 0.0,
            'right_elbow': 1.0,
            'left_elbow': -1.0,
        }
    },
    {
        "time": 53,
        "motors": {
            'neck': 1.0,
        }
    },
    {
        "time": 55,
        "motors": {
            'neck': 0.0,
        }
    },
    {
        "time": 58,
        "motors": {
            'neck': 1.0,
        }
    },
    {
        "time": 60,
        "motors": {
            'neck': 0.0,
        }
    },
    {
        "time": 63,
        "motors": {
            'neck': 1.0,
        }
    },
    {
        "time": 66,
        "motors": {
            'right_shoulder': -1.0,
            'left_shoulder': -1.0,
        }
    },
    {
        "time": 69,
        "motors": {
            'left_shoulder': 0.0,
        }
    },
    {
        "time": 70,
        "motors": {
            'right_shoulder': 1.0,
        }
    },
    {
        "time": 72,
        "motors": {
            'right_shoulder': 0.0,
        }
    },
    {
        "time": 74,
        "motors": {
            'right_shoulder': 1.0,
        }
    },
    {
        "time": 75,
        "motors": {
            'right_elbow': -1.0,
        }
    },
    {
        "time": 76,
        "motors": {
            'right_shoulder': 0.0,
        }
    },
    {
        "time": 77,
        "motors": {
            'right_elbow': 1.0,
        }
    },
    {
        "time": 79,
        "motors": {
            'right_shoulder': 1.0,
        }
    },
    {
        "time": 80,
        "motors": {
            'right_elbow': -1.0,
        }
    },
    {
        "time": 82,
        "motors": {
            'right_shoulder': 0.0,
        }
    },
    {
        "time": 82.5,
        "motors": {
            'right_elbow': 1.0,
        }
    },
    {
        "time": 83,
        "motors": {
            'right_shoulder': 1.0,
        }
    },
    {
        "time": 85,
        "motors": {
            'right_elbow': -1.0,
            'left_elbow': 0.4,
        }
    },
    {
        "time": 87,
        "motors": {
            'right_shoulder': -0.2,
            'left_shoulder': 0.2,
        }
    },
    {
        "time": 88,
        "motors": {
            'left_elbow': 1.0,
            'right_shoulder': -1.0,
        }
    },
    {
        "time": 90,
        "motors": {
            'right_shoulder': 0.0,
            'left_shoulder': 0.0,
            'right_elbow': 0.4,
            'left_elbow': -0.4,
        }
    },
    {
        "time": 92,
        "motors": {
            'right_shoulder': 1.0,
            'left_shoulder': -1.0,
            'right_elbow': 1.0,
            'left_elbow': -1.0,
        }
    },
    {
        "time": 96,
        "motors": {
            'right_shoulder': -0.2,
            'left_shoulder': 0.2,
            'right_elbow': -1.0,
            'left_elbow': 1.0,
        }
    },
    {
        "time": 99,
        "motors": {
            'neck': 0.0,
        }
    },
    {
        "time": 102,
        "motors": {
            'right_shoulder': -1.0,
            'left_shoulder': 1.0,
        }
    },
    {
        "time": 105,
        "motors": {
            'right_elbow': 1.0,
            'left_elbow': -1.0,
        }
    },
    

]


def generate_rave_sequence(duration=120, dt=0.1):
    sequence = []
    steps = int(duration / dt)
    
    # Random offset for torso updates
    next_torso_update = 0
    current_torso_pos = 0.0

    for i in range(steps):
        t = i * dt
        
        # Hand 1 (Right): Quick up and down (Fast Sine Wave)
        # Period approx 0.5s -> f = 2Hz -> 2*pi*f*t = 4*pi*t
        # Amplitude 0.8 to -0.8
        right_shoulder = 0.8 * math.sin(4 * math.pi * t)
        right_elbow = 0.5 * math.cos(4 * math.pi * t) # Slightly different phase
        
        # Neck: Slow side to side (Slow Sine Wave)
        # Period approx 4s -> f = 0.25Hz -> 2*pi*f*t = 0.5*pi*t
        neck = 0.8 * math.sin(0.5 * math.pi * t)
        
        # Hand 2 (Left): "Own thing"
        # Combine two waves for a more complex/independent look
        left_shoulder = 0.6 * math.sin(2 * math.pi * t + 1.5) + 0.2 * math.sin(5 * math.pi * t)
        left_elbow = 0.6 * math.cos(1.5 * math.pi * t)
        
        # Torso: Sporadic
        if t >= next_torso_update:
            current_torso_pos = random.uniform(-0.5, 0.5) # Assuming range -1 to 1 but kept moderate
            # Sporadic interval between 1s and 4s
            next_torso_update = t + random.uniform(1.0, 4.0)
            
        step_data = {
            "time": round(t, 2),
            "motors": {
                "right_shoulder": round(right_shoulder, 3),
                "right_elbow": round(right_elbow, 3),
                "neck": round(neck, 3),
                "left_shoulder": round(left_shoulder, 3),
                "left_elbow": round(left_elbow, 3),
                "torso": round(current_torso_pos, 3)
            }
        }
        sequence.append(step_data)
        
    return sequence

basic_sequences["rave"] = generate_rave_sequence()



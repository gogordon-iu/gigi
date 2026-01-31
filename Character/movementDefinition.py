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
                'right_shoulder': 0.8,
                'left_shoulder': -0.8},
    },
    {
        "time": 8,
        "motors": {
            "torso": 0.8,
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
            "torso": 0.8
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
            "torso": 0.8
        }
    },
    {
        "time": 30,
        "motors": {
            'right_shoulder': -0.8,
            'left_shoulder': 0.5,
        }
    },
    {
        "time": 31,
        "motors": {
            'right_shoulder': -0.6,
            'left_shoulder': 0.8,
        }
    },
    {
        "time": 35,
        "motors": {
            'right_shoulder': 0.8,
            'left_shoulder': -0.5,
        }
    },
    {
        "time": 36,
        "motors": {
            'right_shoulder': 0.6,
            'left_shoulder': -0.8,
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
            'left_shoulder': -0.8,
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
            'right_shoulder': -0.8,
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
            'right_elbow': 0.8,
            'left_elbow': -0.8,
        }
    },
    {
        "time": 53,
        "motors": {
            'neck': 0.8,
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
            'neck': 0.8,
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
            'neck': 0.8,
        }
    },
    {
        "time": 66,
        "motors": {
            'right_shoulder': -0.8,
            'left_shoulder': -0.8,
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
            'right_shoulder': 0.8,
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
            'right_shoulder': 0.8,
        }
    },
    {
        "time": 75,
        "motors": {
            'right_elbow': -0.8,
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
            'right_elbow': 0.8,
        }
    },
    {
        "time": 79,
        "motors": {
            'right_shoulder': 0.8,
        }
    },
    {
        "time": 80,
        "motors": {
            'right_elbow': -0.8,
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
            'right_elbow': 0.8,
        }
    },
    {
        "time": 83,
        "motors": {
            'right_shoulder': 0.8,
        }
    },
    {
        "time": 85,
        "motors": {
            'right_elbow': -0.8,
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
            'left_elbow': 0.8,
            'right_shoulder': -0.8,
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
            'right_shoulder': 0.8,
            'left_shoulder': -0.8,
            'right_elbow': 0.8,
            'left_elbow': -0.8,
        }
    },
    {
        "time": 96,
        "motors": {
            'right_shoulder': -0.2,
            'left_shoulder': 0.2,
            'right_elbow': -0.8,
            'left_elbow': 0.8,
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
            'right_shoulder': -0.8,
            'left_shoulder': 0.8,
        }
    },
    {
        "time": 105,
        "motors": {
            'right_elbow': 0.8,
            'left_elbow': -0.8,
        }
    },
    

]



basic_sequences = {}

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
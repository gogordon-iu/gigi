# Path to the directory containing the images
image_folder_path = '../Assets/face/'

global_parts = ["Eyes", "Nose", "Mouth"]

characters = {
        'gigi': {
            "name": "gigi",
            "base_image_name": "robot face.00",
            "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
            "part_sequence": {
                "Eyes": [("idle", [1]), ("blink", [i for i in range(1,8)])], 
                "Mouth": [("idle", [1]), ("talk", [i for i in range(1,5)])], 
                "Nose": [("idle", [1])]}
        },
        'fuzzy': {
            "name": "fuzzy",
            "base_image_name": "fuzzy face.",
            "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
            "part_sequence": {
                "Eyes": [("idle", [1]), ("blink", [i for i in range(1,8)]), 
                         ("look_right", [10, 11]), ("look_left", [12, 13]), 
                         ("look_down", [15]), ("look_up", [14])], 
                "Mouth": [("idle", [1]), ("talk", [i for i in range(1,5)]), ("smile", [8, 9])], 
                "Nose": [("idle", [1])]}
        },
        'tutti': {
            "name": "tutti",
            "base_image_name": "tutti face.00",
            "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
            "part_sequence": {
                "Eyes": [("idle", [1]), ("blink", [i for i in range(1,8)])], 
                "Mouth": [("idle", [1]), ("talk", [i for i in range(1,5)])], 
                "Nose": [("idle", [1])]}
        }
    }

basic_sequences = {}
for part, part_sequence in characters["fuzzy"]["part_sequence"].items():
    for seq in part_sequence:
        basic_sequences[seq[0]] = {
            part: (seq[0], [str(i) for i in seq[1]])
        }
# print(basic_sequences)
# basic_sequences = {
#     "blink": {
#         "Eyes": ("blink", [str(i) for i in range(1,8)])
#     },
#     "look_right": {
#         "Eyes": ("blink", [str(i) for i in range(1,8)])
#     }
# }    

# print(basic_sequences)

import os
from character import *


# Read a text file line by line and store each line in a list
def read_file_to_list(file_path):
    lines = []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return lines

# Parse each line into a dictionary with tags as keys and substrings as values
def parse_lines_to_dict(lines):
    parsed_list = []
    added_code = {}
    fun_name = None
    add_code = False
    for line in lines:
        if '*/' in line:
            add_code = False
        if add_code:
            if 'def' in line:
                fun_name = line.split('def')[1].split('(')[0].strip()
                added_code[fun_name] = []
            if fun_name:
                added_code[fun_name].append(line)
        if '/*' in line:
            add_code = True
        if not add_code:
            parsed_dict = {}
            if '[' not in line:
                continue
            parts = line.strip().split('[')
            for part in parts[1:]:
                tag, value = part.split(']', 1)
                parsed_dict[tag] = value.strip()
            parsed_list.append(parsed_dict)
    return parsed_list, added_code

script_header = """import sys
sys.path.append('../Character')
import json
import sys
import argparse
from character import Character
from script import *
from scriptGraph import ScriptGraph
import shutil
from characterDefinitions import CHARACTER_FOLDER"""

# Include the script header in the beginning of the generated Python files
def create_files_with_header(parsed_lines, added_code, output_dir, header, child=False, languages=['en']):

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    file_name = None
    the_name = None
    file_path = None
    for parsed_line in parsed_lines:
        if "name" in parsed_line:
            activity_name = parsed_line['name'].replace(" ", "_").replace("-", "_")
            file_name = f"{activity_name}.py"
            file_path = os.path.join(output_dir, file_name)
            the_name = activity_name
            break
    for parsed_line in parsed_lines:
        if "Character" in parsed_line:
            if 'Child' in parsed_line['Character']:
                child = True
            else:
                child = False
            if 'female' in parsed_line['Character']:
                the_gender = 'female'
            elif 'male' in parsed_line['Character']:
                the_gender = 'male'
            else:
                the_gender = 'female'
            break

    if file_name:
        class_name = the_name.replace(" ", "_").replace("-", "_")
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(header + "\n\n")  # Write the script header
            file.write("# Auto-generated file\n")
            file.write(f"# Name: {the_name}\n")
            for key, value in parsed_line.items():
                file.write(f"# {key}: {value}\n")
            file.write(f"activity_name = '{the_name}'\n")

            class_header = f"""class {class_name}(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):
"""
            script_footer = f"""if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{{args.offset}}"
    sg = {class_name}()
    sg.init_graph()"""
            for fun_name in added_code:
                script_footer += f"""
    sg.add_function("{fun_name}", sg.{fun_name})               
"""
            script_footer += f"""        

    fuzzy = Character(child={child}, gender='{the_gender}', activity='{the_name}', languages={languages})
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)"""

            file.write(class_header + "\n\n")  # Write the script header

            node_counter = 1
            first = True
            for ipl, parsed_line in enumerate(parsed_lines):
                parsed_line = {k.lower(): v for k, v in parsed_line.items()}
                if "name" in parsed_line:
                    continue
                if first:
                    node_label = f"start"
                    first = False
                else:
                    node_label = f"Node_{node_counter}"
                node_type = list(parsed_line.keys())

                node_string = f"        self.graph.add_node('{node_label}', type={node_type}, "
                node_string = node_string.replace("timeout", "").replace("data", "").replace("pause", "")
                node_string = node_string.replace("edge", "").replace("goto", "")
                node_string = node_string.replace(", ''", "").replace("''", "").replace("[, ", "[")

                print("----------------------------")
                print("DEBUG: ", parsed_line)
                for key, value in parsed_line.items():
                    if key == "speak":
                        node_string += f"text='{value}', "
                    elif key == "move": 
                        node_string += f"motors='{value.strip()}', "
                    elif key == "show": 
                        show_str = value.split(":")
                        show_type = show_str[0].strip().lower()
                        if show_type == "caption":
                            node_string += f"caption='{show_str[1].strip()}', "
                        elif show_type == "video":
                            video_filename = show_str[1].strip()
                            if not os.path.exists(video_filename):
                                video_filename = f"../Assets/{class_name}/{video_filename}.mp4"
                            node_string += f"video='{video_filename}', "
                        elif show_type == "image":
                            image_filename = show_str[1].strip()
                            # check if the file exists, if not, check in the Assets folder
                            if not os.path.exists(image_filename):
                                image_filename = f"../Assets/{class_name}/face/{image_filename}"
                            # if still not exists, try adding .jpg
                            if not os.path.exists(image_filename):
                                image_filename = image_filename + ".jpg"
                            # if still not exists, try adding .png
                            if not os.path.exists(image_filename):
                                image_filename = image_filename[:-4] + ".png"
                            node_string += f"{show_str[0].strip()}='{image_filename}', "
                    elif key == "find":
                        find_str = value.split(":")
                        node_string += f"{find_str[0].strip()}='{find_str[1].strip()}', "
                        if 'timeout' in parsed_line:
                            node_string += f"timeout={parsed_line['timeout']}, "
                        if 'data' in parsed_line:
                            data_list = [f"'{item.strip()}'" for item in parsed_line['data'].split(',')]
                            node_string += f"data=[{', '.join(data_list)}], "
                        split_node = node_label
                    elif key == "hear":
                        hear_str = value.split(":")
                        hear_type = hear_str[0].strip()
                        if hear_type == "words":
                            words = [f"'{word.strip()}'" for word in hear_str[1].split(",")]
                            hear_string = f"{hear_str[0].strip()}='["
                            for w in words:
                                hear_string += ('"%s", ' % w).replace("'", "")
                            hear_string = hear_string.rstrip(", ") + ", \"[unk]\"]', "
                        elif hear_type == "silence":
                            hear_string = f"timeout={hear_str[1].strip()}, "
                        elif hear_type == 'conversation':
                            hear_string = f"conversation=\"{hear_str[1].strip()}\", "
                        node_string += hear_string

                        if 'timeout' in parsed_line:
                            node_string += f"timeout={parsed_line['timeout']}, "
                        split_node = node_label
                    elif key == "pause":
                        if ":" not in value:
                            node_string += f"pause={{'after': {int(value.strip())}}}, "
                        else:
                            pause_str = value.split(":")
                            node_string += f"pause={{'{pause_str[0].strip()}': {int(pause_str[1].strip())}}}, "
                    elif key == "audio":
                        node_string += f"audio='{value.strip()}.wav', "
                    elif key == "face":
                        if ':' in value:
                            face_data = value.split(':')
                            node_string += f"face={{'{face_data[0].strip()}': '{face_data[1].strip()}'}}, "
                        else:
                            node_string += f"face=basic_sequences['{value.strip()}'], "
                    elif key == "hear":
                        node_string += f"words=[{', '.join([f'\'{word.strip()}\'' for word in value.split(',')])}], "
                    elif key == "data" or key == "timeout" or key == "edge" or key == "goto" or key == "end":
                        pass
                    else:
                        print(key, value)
                        if ':' in value:
                            params = value.split(':')
                            node_string += f"{params[0].strip()}='{params[1].strip()}', "
                node_string = node_string.rstrip(", ") + ")\n"
                if 'edge' in parsed_line:
                    node_string += f"        self.graph.add_edge('{split_node}', 'Node_{node_counter}', label='{parsed_line['edge']}')\n"
                    if 'goto' in parsed_line:
                        node_string += f"        self.graph.add_edge('Node_{node_counter}', 'Node_{node_counter + int(parsed_line['goto'])}', label='Node_{node_counter}_{node_counter + int(parsed_line['goto'])}')\n"
                    else:
                        # check for the next non-edge node
                        found_next_node = False
                        for next_node in range(1,4):
                            if ipl + next_node < len(parsed_lines):
                                if 'edge' not in parsed_lines[ipl + next_node]:
                                    node_string += f"        self.graph.add_edge('Node_{node_counter}', 'Node_{node_counter + next_node}', label='Node_{node_counter}_{node_counter + next_node}')\n"
                                    found_next_node = True
                                    break
                        if not found_next_node:
                            node_string += f"        self.graph.add_edge('Node_{node_counter}', 'Node_{node_counter + 1}', label='Node_{node_counter}_{node_counter + 1}')\n"
                elif 'find' in parsed_line or 'end' in parsed_line:
                    pass
                elif 'hear' in parsed_line and 'words' in parsed_line:
                    pass
                else:
                    found_next_node = False
                    for next_node in range(1,4):
                        if ipl + next_node < len(parsed_lines):
                            if 'edge' not in parsed_lines[ipl + next_node]:
                                node_string += f"        self.graph.add_edge('{node_label}', 'Node_{node_counter + next_node}', label='{node_label}_{node_counter + next_node}')\n"
                                found_next_node = True
                                break
                    if not found_next_node:
                        node_string += f"        self.graph.add_edge('{node_label}', 'Node_{node_counter + 1}', label='{node_label}_{node_counter + 1}')\n"
                node_string = node_string.replace("’", "`")
                file.write(node_string)
                node_counter += 1

            file.write("\n\n")
            for fun_name, fun_code in added_code.items():
                for code_lines in fun_code:
                    file.write(code_lines)
            file.write(script_footer)
            file.write("\n\n")
    return file_path, activity_name


# Example usage
# file_path = '../Scripts/Source/Monolingual_Ferris.txt'  # Replace with your file path
# languages = ['en']

# file_path = '../Scripts/Source/Bilingual_Lego.txt'  # Replace with your file path
# languages = ['en', 'es']

# file_path = '../Scripts/Source/demo.txt'  # Replace with your file path
# languages = ['en']

# file_path = '../Scripts/Source/Game_Multiplication.txt'  # Replace with your file path
# languages = ['en']

# file_path = '../Scripts/Source/test.txt'  # Replace with your file path
# languages = ['en', 'es']

file_path = '../Scripts/Source/jorge_blue.txt'  # Replace with your file path
languages = ['en']


FORCE_GENERATE_AUDIO = True

lines_list = read_file_to_list(file_path)
print('=== lines list ===')
print(lines_list)

parsed_lines, added_code = parse_lines_to_dict(lines_list)
print('=== parsed lines ===')
print(parsed_lines)
print('=== Added Code ===')
print(added_code)

output_directory = '../Scripts'  # Replace with your desired output directory
activity_file, activity_name = create_files_with_header(parsed_lines, added_code, output_directory, header=script_header, languages=languages)

# FORCE generating audio
if FORCE_GENERATE_AUDIO:
    fuzzy = Character(activity=activity_name)
    # remove all references to recorded audio
    fuzzy.speech.recorded_audio[activity_name] = {}
    fuzzy.speech.save_recorded_audio()

    # remove all audio files from the activity assets folder
    speech_folder = f"../Assets/{activity_name}/speech"
    if os.path.exists(speech_folder):
        for filename in os.listdir(speech_folder):
            file_path = os.path.join(speech_folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    fuzzy.stop_character()

# Run the generated Python file
if activity_file:
    os.system(f"python {activity_file}")

import os
from script import Script
from character import Character

def get_scripts():
    scripts_folder = os.path.join(os.path.dirname(__file__), "../Scripts")
    list_of_scripts_ = {}
    for file_name in os.listdir(scripts_folder):
        if file_name.endswith(".py") and file_name != "__init__.py":
            script_name = os.path.splitext(file_name)[0]
            print("Script name:", script_name)
            file_path = os.path.join(scripts_folder, file_name)
            with open(file_path, "r", encoding='utf-8') as script_file:
                activity_name = None
                class_name = None
                for line in script_file:
                    if line.strip().startswith("activity_name ="):
                        activity_name = line.split("=")[1].strip().strip('"').strip("'")
                    if line.strip().startswith("class "):
                        class_name = line.split()[1].split("(")[0]
                    if activity_name and class_name:
                        list_of_scripts_[activity_name] = {
                            "package_name": script_name,
                            "class_name": class_name,
                        }
                        break
    return list_of_scripts_

if __name__ == "__main__":
    list_of_scripts = get_scripts()

    for script_name, script_info in list_of_scripts.items():
        print("Script name:", script_name)
        scriptGraph_package = __import__(script_info['package_name'])
        scriptGraph_instance = getattr(scriptGraph_package, script_info['class_name'])()
        scriptGraph_instance.init_graph()

        fuzzy = Character()
        script_instance = Script(graph=scriptGraph_instance, character=fuzzy)
        script_instance.generateAllSpeech()
        script_instance.check_assets()
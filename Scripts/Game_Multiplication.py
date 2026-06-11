import sys
sys.path.append('../Character')
import json
import sys
import argparse
from character import Character
from script import *
from scriptGraph import ScriptGraph
import shutil
from characterDefinitions import CHARACTER_FOLDER

# Auto-generated file
# Name: Game_Multiplication
# Character: female
activity_name = 'Game_Multiplication'
class Game_Multiplication(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'move'], text='Let us start with an easy one', motors='home')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['generate'], level='easy')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['speak', 'show'], text='% text', caption='% exercise')
        self.graph.add_edge('Node_4', 'Node_5', label='Node_4_5')
        self.graph.add_node('Node_5', type=['hear'], conversation="% check_prompt")
        self.graph.add_edge('Node_5', 'Node_8', label='Node_5_8')
        self.graph.add_node('Node_6', type=['speak'], text='Nice try, Hadar. Let us try again.')
        self.graph.add_edge('Node_5', 'Node_6', label='NO')
        self.graph.add_edge('Node_6', 'Node_4', label='Node_6_4')
        self.graph.add_node('Node_7', type=['speak'], text='That was great.')
        self.graph.add_edge('Node_5', 'Node_7', label='YES')
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak', 'show'], text='% text_answer', caption='% exercise_answer')
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')
        self.graph.add_node('Node_9', type=['speak'], text='Now another one.')
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['generate'], level='medium')
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')
        self.graph.add_node('Node_11', type=['speak', 'show'], text='% text', caption='% exercise')
        self.graph.add_edge('Node_11', 'Node_12', label='Node_11_12')
        self.graph.add_node('Node_12', type=['hear'], conversation="% check_prompt")
        self.graph.add_edge('Node_12', 'Node_15', label='Node_12_15')
        self.graph.add_node('Node_13', type=['speak'], text='Nice try, Hadar. Let us try again.')
        self.graph.add_edge('Node_12', 'Node_13', label='NO')
        self.graph.add_edge('Node_13', 'Node_11', label='Node_13_11')
        self.graph.add_node('Node_14', type=['speak'], text='That was great.')
        self.graph.add_edge('Node_12', 'Node_14', label='YES')
        self.graph.add_edge('Node_14', 'Node_15', label='Node_14_15')
        self.graph.add_node('Node_15', type=['speak', 'show'], text='% text_answer', caption='% exercise_answer')
        self.graph.add_edge('Node_15', 'Node_16', label='Node_15_16')
        self.graph.add_node('Node_16', type=['speak'], text='Now another one.')
        self.graph.add_edge('Node_16', 'Node_17', label='Node_16_17')
        self.graph.add_node('Node_17', type=['generate'], level='hard')
        self.graph.add_edge('Node_17', 'Node_18', label='Node_17_18')
        self.graph.add_node('Node_18', type=['speak', 'show'], text='% text', caption='% exercise')
        self.graph.add_edge('Node_18', 'Node_19', label='Node_18_19')
        self.graph.add_node('Node_19', type=['hear'], conversation="% check_prompt")
        self.graph.add_edge('Node_19', 'Node_22', label='Node_19_22')
        self.graph.add_node('Node_20', type=['speak'], text='Nice try, Hadar. Let us try again.')
        self.graph.add_edge('Node_19', 'Node_20', label='NO')
        self.graph.add_edge('Node_20', 'Node_18', label='Node_20_18')
        self.graph.add_node('Node_21', type=['speak'], text='That was great.')
        self.graph.add_edge('Node_19', 'Node_21', label='YES')
        self.graph.add_edge('Node_21', 'Node_22', label='Node_21_22')
        self.graph.add_node('Node_22', type=['speak', 'show'], text='% text_answer', caption='% exercise_answer')
        self.graph.add_edge('Node_22', 'Node_23', label='Node_22_23')
        self.graph.add_node('Node_23', type=['speak'], text='That is it for today.')
        self.graph.add_edge('Node_23', 'Node_24', label='Node_23_24')


    def generate(self, current_node, current_data, data_):
        from random import choice
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]

        numbers = [1,2,3,4,5,6,7,8,9]
        if 'level' in current_data:
            if 'easy' in current_data['level']:
                numbers = [1, 2, 3]
            elif 'medium' in current_data['level']:
                numbers = [2,3,4,5,6]
            else:
                numbers = [2,3,4,5,6,7,8,9]

        first_number = choice(numbers)
        second_number = choice(numbers)
        answer = first_number * second_number

        self.data['types']['text'] = f"How much is {first_number} times {second_number}?"
        self.data['types']['exercise'] = f"{first_number} x {second_number} = ?"
        self.data['types']['answer'] = f"[{answer}]"
        self.data['types']['the_answer'] = f"{answer}"
        self.data['types']['text_answer'] = f"{first_number} times {second_number} is equal to {answer}"
        self.data['types']['exercise_answer'] = f"{first_number} x {second_number} = {answer}"
        self.data['types']['check_prompt'] = f"You asked the user what is the answer to the math question whose correct answer is {answer}. The user said RESPONSE. Is the user correct? Answer only in YES or NO."
        return next_node
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Game_Multiplication()
    sg.init_graph()
    sg.add_function("generate", sg.generate)               
        

    import threading

    fuzzy = Character(child=False, gender='female', activity='Game_Multiplication', languages=['en'])
    
    # Start background face tracking thread to look at the child and drive face recognition/logging
    stop_event = threading.Event()
    tracker_thread = None
    if fuzzy.vision:
        print("[Game_Multiplication] Starting background face follow tracking...")
        tracker_thread = threading.Thread(
            target=fuzzy.follow_face,
            kwargs={'stop_event': stop_event},
            daemon=True
        )
        tracker_thread.start()
        
    try:
        script = Script(graph=sg, character=fuzzy)
        script.generateAllSpeech()
        script.check_assets()
        script.run(start_node=start_node)
    finally:
        if tracker_thread:
            print("[Game_Multiplication] Stopping background face follow tracking...")
            stop_event.set()
            tracker_thread.join(timeout=1.5)


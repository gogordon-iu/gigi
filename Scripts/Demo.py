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
# Name: Demo
# Character: female
activity_name = 'Demo'
class Demo(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'move'], text='Hi, it is Gigi again.', motors='wave_hello')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['speak', 'move'], text='Great to see you again, Gaia', motors='look_left')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['speak', 'move'], text='Emma', motors='look_right.')
        self.graph.add_edge('Node_4', 'Node_5', label='Node_4_5')
        self.graph.add_node('Node_5', type=['speak'], text='Last time we learned about robots in general.')
        self.graph.add_edge('Node_5', 'Node_6', label='Node_5_6')
        self.graph.add_node('Node_6', type=['speak'], text='Today we are going to learn about co-bots.')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['speak', 'show'], text='Short of Collaborative Robots.', caption='Collaborative Robots')
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak', 'move'], text='What do you think co-bots are?', motors='arms_up_and_down')
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')
        self.graph.add_node('Node_9', type=['hear'], timeout=10)
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['speak'], text='That is a great explanation, Gaia, thank you for sharing.')
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')
        self.graph.add_node('Node_11', type=['speak', 'move'], text='Emma, do you want to share your thoughts?', motors='look_right')
        self.graph.add_edge('Node_11', 'Node_12', label='Node_11_12')
        self.graph.add_node('Node_12', type=['hear'], timeout=10)
        self.graph.add_edge('Node_12', 'Node_13', label='Node_12_13')
        self.graph.add_node('Node_13', type=['speak'], text='That was a great idea, Emma, I love it.')
        self.graph.add_edge('Node_13', 'Node_14', label='Node_13_14')
        self.graph.add_node('Node_14', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_14', 'Node_15', label='Node_14_15')
        self.graph.add_node('Node_15', type=['speak', 'show'], text='Collaborative robots, or co-bots, are robots designed to work safely alongside people, helping them with tasks instead of replacing them.', image='../Assets/Demo/face/techman.jpg')
        self.graph.add_edge('Node_15', 'Node_16', label='Node_15_16')
        self.graph.add_node('Node_16', type=['hear'], timeout=10)
        self.graph.add_edge('Node_16', 'Node_17', label='Node_16_17')
        self.graph.add_node('Node_17', type=['speak'], text='That is a great question, Gaia, I also love to learn new things.')
        self.graph.add_edge('Node_17', 'Node_18', label='Node_17_18')
        self.graph.add_node('Node_18', type=['speak', 'show'], text='They can sense and respond to human actions, making teamwork between humans and machines easier and safer.', image='../Assets/Demo/face/cobot.jpg', pause={'after': 3})
        self.graph.add_edge('Node_18', 'Node_19', label='Node_18_19')
        self.graph.add_node('Node_19', type=['speak'], text='Let us do an activity to better understand what are co-bots.')
        self.graph.add_edge('Node_19', 'Node_20', label='Node_19_20')
        self.graph.add_node('Node_20', type=['speak', 'face', 'move'], text='In front of you are a pencil and pencil sharpener', face=basic_sequences['look_down'], motors='arms_down')
        self.graph.add_edge('Node_20', 'Node_21', label='Node_20_21')
        self.graph.add_node('Node_21', type=['speak', 'move'], text='You need to sharpen the pencil', motors='home')
        self.graph.add_edge('Node_21', 'Node_22', label='Node_21_22')
        self.graph.add_node('Node_22', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_22', 'Node_23', label='Node_22_23')
        self.graph.add_node('Node_23', type=['speak', 'move'], text='But one of you holds the pencil with one arm', motors='look_left')
        self.graph.add_edge('Node_23', 'Node_24', label='Node_23_24')
        self.graph.add_node('Node_24', type=['speak', 'move'], text='And the other holds the sharpener with one arm', motors='look_right', pause={'after': 1})
        self.graph.add_edge('Node_24', 'Node_25', label='Node_24_25')
        self.graph.add_node('Node_25', type=['speak'], text='Think you can do it? Try', pause={'after': 10})
        self.graph.add_edge('Node_25', 'Node_26', label='Node_25_26')
        self.graph.add_node('Node_26', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_26', 'Node_27', label='Node_26_27')
        self.graph.add_node('Node_27', type=['speak'], text='That was fun.', pause={'after': 1})
        self.graph.add_edge('Node_27', 'Node_28', label='Node_27_28')
        self.graph.add_node('Node_28', type=['speak'], text='Now let us simulate a co-bot.')
        self.graph.add_edge('Node_28', 'Node_29', label='Node_28_29')
        self.graph.add_node('Node_29', type=['speak', 'move'], text='Gaia, you are the co-bot', motors='look_left')
        self.graph.add_edge('Node_29', 'Node_30', label='Node_29_30')
        self.graph.add_node('Node_30', type=['speak', 'move'], text='Emma, you need to tell Gaia exactly what to do, since you are the programmer and she is the co-bot', motors='look_right')
        self.graph.add_edge('Node_30', 'Node_31', label='Node_30_31')
        self.graph.add_node('Node_31', type=['speak', 'move'], text='Gaia, only do what Emma tells you. Do not act on your own.', motors='look_left', pause={'after': 15})
        self.graph.add_edge('Node_31', 'Node_32', label='Node_31_32')
        self.graph.add_node('Node_32', type=['speak', 'move'], text='That was great.', motors='arms_up')
        self.graph.add_edge('Node_32', 'Node_33', label='Node_32_33')
        self.graph.add_node('Node_33', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_33', 'Node_34', label='Node_33_34')
        self.graph.add_node('Node_34', type=['speak', 'move'], text='Emma, you are an excellent co-bot operator', motors='look_right', pause={'after': 2})
        self.graph.add_edge('Node_34', 'Node_35', label='Node_34_35')
        self.graph.add_node('Node_35', type=['speak', 'move'], text='That is it for today. See you next time, Gaia and Emma.', motors='wave_hello')
        self.graph.add_edge('Node_35', 'Node_36', label='Node_35_36')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Demo()
    sg.init_graph()

    fuzzy = Character(child=False, gender='female', activity='Demo', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)


import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER

# Auto-generated file
# Name: Monolingual_Ferris
# Character: female Child
activity_name = 'Monolingual_Ferris'
class Monolingual_Ferris(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'move'], text='Hello friends! It is Gigi the robot again!', motors='wave_hello')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['speak'], text='Let us continue from where we stopped.')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['speak', 'show'], text='Like the light, find the motor, attach green pins to it.', image='../Assets/Monolingual_Ferris/ferris_step_11.png', pause={'after': 5})
        self.graph.add_edge('Node_4', 'Node_5', label='Node_4_5')
        self.graph.add_node('Node_5', type=['speak'], text='Then attach the motor to the tower.')
        self.graph.add_edge('Node_5', 'Node_6', label='Node_5_6')
        self.graph.add_node('Node_6', type=['speak', 'show'], text='When it is attached, raise your card.', image='../Assets/Monolingual_Ferris/ferris_step_12.png')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['find'], what='qr', timeout=60, data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_8', type=['speak', 'show'], text='Let me know when it is attached. I will wait!', image='../Assets/Monolingual_Ferris/ferris_step_12.png')
        self.graph.add_edge('Node_7', 'Node_8', label='no')
        self.graph.add_edge('Node_8', 'Node_7', label='Node_8_7')
        self.graph.add_node('Node_9', type=['speak'], text='That was great teamwork!')
        self.graph.add_edge('Node_7', 'Node_9', label='yes')
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['speak'], text='You figures need a way to reach the ferris wheel. How about building stairs?')
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')
        self.graph.add_node('Node_11', type=['speak', 'show'], text='Find and connect the yellow brick and the blue tiles.', image='../Assets/Monolingual_Ferris/ferris_step_13.png', pause={'after': 5})
        self.graph.add_edge('Node_11', 'Node_12', label='Node_11_12')
        self.graph.add_node('Node_12', type=['speak'], text='Then connect two more blue tiles.')
        self.graph.add_edge('Node_12', 'Node_13', label='Node_12_13')
        self.graph.add_node('Node_13', type=['speak', 'show'], text='When they`re all connected, raise your card.', image='../Assets/Monolingual_Ferris/ferris_step_14.png')
        self.graph.add_edge('Node_13', 'Node_14', label='Node_13_14')
        self.graph.add_node('Node_14', type=['find'], what='qr', timeout=60, data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_15', type=['speak', 'show'], text='Still snapping them in? I will wait until you are done.', image='../Assets/Monolingual_Ferris/ferris_step_14.png')
        self.graph.add_edge('Node_14', 'Node_15', label='no')
        self.graph.add_edge('Node_15', 'Node_14', label='Node_15_14')
        self.graph.add_node('Node_16', type=['speak'], text='You built stairs! What a super team!')
        self.graph.add_edge('Node_14', 'Node_16', label='yes')
        self.graph.add_edge('Node_16', 'Node_17', label='Node_16_17')
        self.graph.add_node('Node_17', type=['speak', 'show'], text='find the rod and put it in the motor. That will make the ferris wheel turn.', image='../Assets/Monolingual_Ferris/ferris_step_15.png', pause={'after': 15})
        self.graph.add_edge('Node_17', 'Node_18', label='Node_17_18')
        self.graph.add_node('Node_18', type=['speak', 'show'], text='Now we build the arms of the ferris wheel. First, start with the main straucture.', image='../Assets/Monolingual_Ferris/ferris_step_16.png', pause={'after': 15})
        self.graph.add_edge('Node_18', 'Node_19', label='Node_18_19')
        self.graph.add_node('Node_19', type=['speak', 'show'], text='Then connect the green pieces to the round wheel center to form an X. Take turns holding the wheel while your partner adds the arms. Then switch.', image='../Assets/Monolingual_Ferris/ferris_step_17.png')
        self.graph.add_edge('Node_19', 'Node_20', label='Node_19_20')
        self.graph.add_node('Node_20', type=['speak', 'show'], text='When they`re all connected, raise your card.', image='../Assets/Monolingual_Ferris/ferris_step_17.png')
        self.graph.add_edge('Node_20', 'Node_21', label='Node_20_21')
        self.graph.add_node('Node_21', type=['find'], what='qr', timeout=60, data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_22', type=['speak', 'show'], text='Still snapping them in? I will wait until you are done.', image='../Assets/Monolingual_Ferris/ferris_step_17.png')
        self.graph.add_edge('Node_21', 'Node_22', label='no')
        self.graph.add_edge('Node_22', 'Node_21', label='Node_22_21')
        self.graph.add_node('Node_23', type=['speak'], text='You made an X! What a super team!')
        self.graph.add_edge('Node_21', 'Node_23', label='yes')
        self.graph.add_edge('Node_23', 'Node_24', label='Node_23_24')
        self.graph.add_node('Node_24', type=['speak'], text='Now for the final pieces of the wheel.')
        self.graph.add_edge('Node_24', 'Node_25', label='Node_24_25')
        self.graph.add_node('Node_25', type=['speak', 'show'], text='Put one more purple circle.', image='../Assets/Monolingual_Ferris/ferris_step_18.png', pause={'after': 10})
        self.graph.add_edge('Node_25', 'Node_26', label='Node_25_26')
        self.graph.add_node('Node_26', type=['speak', 'show'], text='Then four white pieces. Work together.', image='../Assets/Monolingual_Ferris/ferris_step_19.png', pause={'after': 10})
        self.graph.add_edge('Node_26', 'Node_27', label='Node_26_27')
        self.graph.add_node('Node_27', type=['speak', 'show'], text='Then a green round piece.', image='../Assets/Monolingual_Ferris/ferris_step_20.png', pause={'after': 5})
        self.graph.add_edge('Node_27', 'Node_28', label='Node_27_28')
        self.graph.add_node('Node_28', type=['speak', 'show'], text='And an orange cone.', image='../Assets/Monolingual_Ferris/ferris_step_21.png', pause={'after': 10})
        self.graph.add_edge('Node_28', 'Node_29', label='Node_28_29')
        self.graph.add_node('Node_29', type=['speak'], text='The seats are next. You need to build four seat, one on each arm of the wheel. work together.')
        self.graph.add_edge('Node_29', 'Node_30', label='Node_29_30')
        self.graph.add_node('Node_30', type=['speak', 'show'], text='Let me know when you are done.', image='../Assets/Monolingual_Ferris/ferris_step_22.png')
        self.graph.add_edge('Node_30', 'Node_31', label='Node_30_31')
        self.graph.add_node('Node_31', type=['find'], what='qr', timeout=60, data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_32', type=['speak', 'show'], text='Still finalizing those seats? I will wait until you are done.', image='../Assets/Monolingual_Ferris/ferris_step_22.png')
        self.graph.add_edge('Node_31', 'Node_32', label='no')
        self.graph.add_edge('Node_32', 'Node_31', label='Node_32_31')
        self.graph.add_node('Node_33', type=['speak'], text='You have the wheel! What a great team!')
        self.graph.add_edge('Node_31', 'Node_33', label='yes')
        self.graph.add_edge('Node_33', 'Node_34', label='Node_33_34')
        self.graph.add_node('Node_34', type=['speak', 'show'], text='Now gently slide the wheel onto the axle. Be very careful!. One of you can hold the axle, while the other pushes the wheel.', image='../Assets/Monolingual_Ferris/ferris_step_23.png', pause={'after': 10})
        self.graph.add_edge('Node_34', 'Node_35', label='Node_34_35')
        self.graph.add_node('Node_35', type=['speak'], text='Now, Lets test it!  If it spins nicely, raise your card.')
        self.graph.add_edge('Node_35', 'Node_36', label='Node_35_36')
        self.graph.add_node('Node_36', type=['find'], what='qr', timeout=60, data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_37', type=['speak'], text='Try again and raise your card when the wheel is spinning well.')
        self.graph.add_edge('Node_36', 'Node_37', label='no')
        self.graph.add_edge('Node_37', 'Node_36', label='Node_37_36')
        self.graph.add_node('Node_38', type=['speak', 'move'], text='You did it! Our Ferris Wheel is standing tall and spinning around! You built it together. high five your friend and give a big smile!', motors='clap')
        self.graph.add_edge('Node_36', 'Node_38', label='yes')
        self.graph.add_edge('Node_38', 'Node_39', label='Node_38_39')


if __name__ == "__main__":
    sg = Monolingual_Ferris()
    sg.init_graph()

    fuzzy = Character(child=True, gender='female', activity='Monolingual_Ferris', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run()


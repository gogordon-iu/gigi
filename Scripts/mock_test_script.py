import sys
sys.path.append('../Character')
from scriptGraph import ScriptGraph

activity_name = "mock_test_script"

class MockTestScript(ScriptGraph):
    def __init__(self):
        super().__init__()

    def init_graph(self):
        self.graph.add_node("start", type="speak", text="I am executing the mock test script successfully.")
        self.graph.add_edge("start", "The End", label="finished")
        self.graph.add_node("The End", type="end")

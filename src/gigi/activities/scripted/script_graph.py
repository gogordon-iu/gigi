import networkx as nx


class ScriptGraph:

    def __init__(self):
        self.graph = nx.DiGraph()
        self.data = {
            'types': {},
            'output': {},
            'done_fun': self.done
        }

    def done(self):
        pass

    def add_function(self, name, fun):
        self.data['types'][name] = fun

    def add_done(self, done=None):
        self.data['done_fun'] = done

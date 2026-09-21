"""
Unit tests for activity algorithms and logic:
- Mastermind guess evaluation and candidate filtering
- Math Quest spoken number parsing and question generation
- Story Game response cleaning and confirmation parsing
- Scripted activity graph structures
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


class TestMastermindLogic(unittest.TestCase):
    """Tests for Mastermind codebreaker game algorithms."""

    def test_check_guess_exact(self):
        from gigi.activities.mastermind.mastermind import check_guess

        black, white = check_guess("1234", "1234")
        self.assertEqual(black, 4)
        self.assertEqual(white, 0)

    def test_check_guess_permutation(self):
        from gigi.activities.mastermind.mastermind import check_guess

        black, white = check_guess("1234", "4321")
        self.assertEqual(black, 0)
        self.assertEqual(white, 4)

    def test_check_guess_partial(self):
        from gigi.activities.mastermind.mastermind import check_guess

        black, white = check_guess("1234", "1256")
        self.assertEqual(black, 2)
        self.assertEqual(white, 0)

    def test_candidate_filtering(self):
        from gigi.activities.mastermind.mastermind import get_all_candidates, filter_candidates

        candidates = get_all_candidates()
        self.assertEqual(len(candidates), 5040)  # 10 * 9 * 8 * 7 permutations
        # Filter with guess "0123", feedback: 4 blacks
        remaining = filter_candidates(candidates, "0123", 4, 0)
        self.assertEqual(remaining, ["0123"])


class TestMathQuestLogic(unittest.TestCase):
    """Tests for Math Quest spoken number parsing and question generation."""

    def test_parse_spoken_number_single_digit(self):
        from gigi.activities.math_quest.math_quest import parse_spoken_number

        self.assertEqual(parse_spoken_number("seven"), 7)
        self.assertEqual(parse_spoken_number("zero"), 0)
        self.assertEqual(parse_spoken_number("nine"), 9)

    def test_parse_spoken_number_compound(self):
        from gigi.activities.math_quest.math_quest import parse_spoken_number

        self.assertEqual(parse_spoken_number("twenty five"), 25)
        self.assertEqual(parse_spoken_number("forty two"), 42)
        self.assertEqual(parse_spoken_number("ninety nine"), 99)
        self.assertEqual(parse_spoken_number("the answer is sixteen"), 16)

    def test_parse_spoken_digits(self):
        from gigi.activities.math_quest.math_quest import parse_spoken_number

        self.assertEqual(parse_spoken_number("5"), 5)
        self.assertEqual(parse_spoken_number("I think it is 23"), 23)

    def test_generate_questions(self):
        from gigi.activities.math_quest.math_quest import generate_questions

        easy_questions = generate_questions("easy", count=4)
        self.assertEqual(len(easy_questions), 4)
        for f1, f2 in easy_questions:
            self.assertIsInstance(f1, int)
            self.assertIsInstance(f2, int)
            self.assertGreaterEqual(f1, 0)
            self.assertGreaterEqual(f2, 0)


class TestStoryGameLogic(unittest.TestCase):
    """Tests for Story Game response normalization and confirmation parsing."""

    def test_clean_response(self):
        from gigi.activities.story_game.story_game import clean_response

        cleaned = clean_response("Gigi: Look at this exciting toy!\nStudent: That's a robot!")
        self.assertEqual(cleaned, "Look at this exciting toy!")

    def test_parse_confirmation(self):
        from gigi.activities.story_game.story_game import parse_confirmation

        self.assertTrue(parse_confirmation("yes of course"))
        self.assertTrue(parse_confirmation("sure let's do it"))
        self.assertTrue(parse_confirmation("yeah"))
        self.assertFalse(parse_confirmation("no, I want to stop"))
        self.assertFalse(parse_confirmation("nope"))


class TestScriptedActivities(unittest.TestCase):
    """Tests for scripted activity graph data structures."""

    def test_lego_script_graph(self):
        import networkx as nx
        from gigi.activities.scripted.lego import Bilingual_Lego

        lego = Bilingual_Lego()
        lego.init_graph()
        self.assertTrue(hasattr(lego, "graph"))
        self.assertIsInstance(lego.graph, nx.DiGraph)
        self.assertGreater(len(lego.graph.nodes), 0)

    def test_ferris_script_graph(self):
        import networkx as nx
        from gigi.activities.scripted.ferris import Monolingual_Ferris

        ferris = Monolingual_Ferris()
        ferris.init_graph()
        self.assertTrue(hasattr(ferris, "graph"))
        self.assertIsInstance(ferris.graph, nx.DiGraph)
        self.assertGreater(len(ferris.graph.nodes), 0)

    def test_halloween_script_graph(self):
        import networkx as nx
        from gigi.activities.scripted.halloween import Halloween

        halloween = Halloween()
        halloween.init_graph()
        self.assertTrue(hasattr(halloween, "graph"))
        self.assertIsInstance(halloween.graph, nx.DiGraph)
        self.assertGreater(len(halloween.graph.nodes), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

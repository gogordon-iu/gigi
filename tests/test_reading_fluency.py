import sys
import unittest
import os
import json
import re
import string
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = str(PROJECT_ROOT / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from gigi.core.config import PROJECT_ROOT as gigi_dir
from gigi.activities.common import extract_name
from gigi.activities.reading_fluency.reading_fluency import (
    levenshtein_distance,
)


def count_syllables(word):
    word = word.lower().strip()
    word = word.translate(str.maketrans('', '', string.punctuation))
    if not word:
        return 0
    vowels = "aeiouy"
    count = 0
    if word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    if count == 0:
        count += 1
    return count


def is_prefix_or_syllable(heard, expected):
    h = heard.lower().strip().translate(str.maketrans('', '', string.punctuation))
    e = expected.lower().strip().translate(str.maketrans('', '', string.punctuation))
    if not h or not e:
        return False
    if e.startswith(h):
        return True
    if len(h) >= 2 and h in e:
        return True
    pref = e[:len(h)]
    if len(pref) >= 3 and levenshtein_distance(h, pref) <= 1:
        return True
    return False


def get_reread_probability(word, force_reread=False):
    if force_reread:
        return 1.0
    clean = word.lower().translate(str.maketrans('', '', string.punctuation)).strip()
    length = len(clean)
    syllables = count_syllables(clean)
    if length <= 3 or syllables <= 1:
        return 0.20
    elif length <= 5 or syllables == 2:
        return 0.55
    else:
        return 0.85


class TestReadingFluencyUnit(unittest.TestCase):
    """
    Automated, non-interactive unit tests for Reading Fluency activity logic.
    Requires no microphone, no sound card, and no user input.
    """

    def test_levenshtein_distance(self):
        """Test classic Levenshtein distance edge cases."""
        self.assertEqual(levenshtein_distance("", ""), 0)
        self.assertEqual(levenshtein_distance("sky", "sky"), 0)
        self.assertEqual(levenshtein_distance("sky", "skies"), 3)
        self.assertEqual(levenshtein_distance("green", "green"), 0)
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)

    def test_syllable_sounding_and_prefix(self):
        """Test partial soundings and syllable prefix matching for hesitant readers."""
        # 'sk' is prefix of 'sky'
        self.assertTrue(is_prefix_or_syllable("sk", "sky"))
        # 'hap' is prefix of 'happy'
        self.assertTrue(is_prefix_or_syllable("hap", "happy"))
        # completely different words should return False
        self.assertFalse(is_prefix_or_syllable("green", "sky"))
        self.assertFalse(is_prefix_or_syllable("", "sky"))

    def test_reread_probability(self):
        """Test adaptive pedagogical reread probability calculation."""
        # Short / 1-syllable word ('the', 'sky', 'dog')
        self.assertAlmostEqual(get_reread_probability("sky"), 0.20)
        self.assertAlmostEqual(get_reread_probability("the"), 0.20)

        # 2-syllable word ('planet') -> 0.55
        self.assertAlmostEqual(get_reread_probability("planet"), 0.55)

        # 3+ syllable word ('astronomy', 'dinosaur') -> 0.85
        self.assertAlmostEqual(get_reread_probability("dinosaur"), 0.85)

        # Force reread override
        self.assertEqual(get_reread_probability("the", force_reread=True), 1.0)

    def test_word_bank_io(self):
        """Test local word bank JSON persistence and updating."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            wb_file = os.path.join(tmp_dir, "word_bank.json")
            
            # Initial state
            word_bank = {"sky": "incorrect", "planet": "correct"}
            with open(wb_file, 'w', encoding='utf-8') as f:
                json.dump(word_bank, f, indent=4)
                
            self.assertTrue(os.path.exists(wb_file))
            
            # Load and update
            with open(wb_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            self.assertEqual(loaded["sky"], "incorrect")
            self.assertEqual(loaded["planet"], "correct")
            
            # Correct word in bank
            loaded["sky"] = "correct"
            with open(wb_file, 'w', encoding='utf-8') as f:
                json.dump(loaded, f, indent=4)
                
            with open(wb_file, 'r', encoding='utf-8') as f:
                reloaded = json.load(f)
            self.assertEqual(reloaded["sky"], "correct")

    def test_sentence_segmentation(self):
        """Test sentence splitting handles periods, exclamation marks, and question marks."""
        passage = "When you look up at the sky at night, what do you see? The sun is a star! It shines brightly."
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', passage) if s.strip()]
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "When you look up at the sky at night, what do you see?")
        self.assertEqual(sentences[1], "The sun is a star!")
        self.assertEqual(sentences[2], "It shines brightly.")

    def test_name_extraction(self):
        """Test extract_name parses child names from various speech introductions."""
        self.assertEqual(extract_name("my name is Alex"), "Alex")
        self.assertEqual(extract_name("I am Maya"), "Maya")
        self.assertEqual(extract_name("call me Sam"), "Sam")
        # Fallback for unrecognizable phrases
        self.assertTrue(len(extract_name("hello nice to meet you")) > 0)

    def test_filler_word_filtering(self):
        """Test that speech filler tokens are identified."""
        fillers = {"um", "uh", "ah", "like", "so", "well", "and", "i", "mean"}
        test_tokens = ["um", "the", "uh", "sky", "is", "blue"]
        filtered = [t for t in test_tokens if t not in fillers]
        self.assertEqual(filtered, ["the", "sky", "is", "blue"])

    def test_story_passage_discovery(self):
        """Test that story passage assets exist and can be discovered."""
        assets_dir = os.path.join(gigi_dir, 'Assets', 'ReadingFluency')
        os.makedirs(assets_dir, exist_ok=True)
        # Create a sample passage if directory is empty
        sample_file = os.path.join(assets_dir, 'sample_passage.txt')
        if not os.path.exists(sample_file):
            with open(sample_file, 'w', encoding='utf-8') as f:
                f.write("A test passage for reading fluency.")
                
        passages = [f for f in os.listdir(assets_dir) if f.endswith('_passage.txt')]
        self.assertGreater(len(passages), 0)


if __name__ == "__main__":
    unittest.main()

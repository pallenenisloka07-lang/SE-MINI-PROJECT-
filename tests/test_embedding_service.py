import unittest

from src.services.embedding_service import split_into_passages


class TestPassageSplitting(unittest.TestCase):

    def test_empty_text_returns_no_passages(self):
        self.assertEqual(split_into_passages(""), [])

    def test_short_text_returns_one_passage(self):
        text = "These are five simple words."
        self.assertEqual(split_into_passages(text), [text])

    def test_passages_have_30_word_overlap(self):
        words = [f"word{i}" for i in range(270)]

        passages = split_into_passages(" ".join(words))

        self.assertEqual(len(passages), 2)

        first_words = passages[0].split()
        second_words = passages[1].split()

        self.assertEqual(len(first_words), 150)
        self.assertEqual(len(second_words), 150)
        self.assertEqual(first_words[-30:], second_words[:30])

    def test_passage_count_is_capped(self):
        text = " ".join(f"word{i}" for i in range(20000))

        passages = split_into_passages(text)

        self.assertLessEqual(len(passages), 100)

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            split_into_passages("some text", max_words=0)

        with self.assertRaises(ValueError):
            split_into_passages("some text", max_words=10, overlap=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
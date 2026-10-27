import os
import unittest
from unittest.mock import patch

import numpy as np

from src.services.content_analyzer import (
    analyze_document_text,
    _candidate_phrases,
)


SAMPLE_TEXT = """
Artificial intelligence systems analyze medical images.
Neural networks learn visual patterns from training data.
Machine learning models classify images using algorithms.
Computer vision extracts features for scientific research.
Data analysis evaluates predictions and model performance.
"""


def fake_embeddings(texts):
    """Generate deterministic embeddings without downloading a model."""
    if texts and texts[0].startswith("Technology:"):
        return [[1.0, 0.0] for _ in texts]

    if texts and texts[0].startswith("Unrelated:"):
        return [[0.0, 1.0] for _ in texts]

    vectors = []

    for index, _ in enumerate(texts):
        angle = index * 0.37
        vectors.append([
            float(np.cos(angle)),
            float(np.sin(angle)),
        ])

    return vectors


class TestContentAnalyzer(unittest.TestCase):

    def test_empty_text_returns_empty_analysis(self):
        result = analyze_document_text("")

        self.assertEqual(result["category"], "Uncategorized")
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["keywords"], [])
        self.assertEqual(result["topics"], [])

    def test_technology_category_is_selected(self):
        categories = [
            {
                "name": "Technology",
                "description": (
                    "Technology: artificial intelligence, "
                    "computers and machine learning."
                ),
            }
        ]

        with patch(
            "src.services.content_analyzer.encode_passages",
            side_effect=fake_embeddings,
        ):
            result = analyze_document_text(
                SAMPLE_TEXT,
                passage_embeddings=[[1.0, 0.0]],
                categories=categories,
            )

        self.assertEqual(result["category"], "Technology")
        self.assertGreater(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_low_similarity_returns_uncategorized(self):
        categories = [
            {
                "name": "Unrelated",
                "description": (
                    "Unrelated: unrelated category description."
                ),
            }
        ]

        with (
            patch(
                "src.services.content_analyzer.encode_passages",
                side_effect=fake_embeddings,
            ),
            patch.dict(
                os.environ,
                {"CATEGORY_CONFIDENCE_THRESHOLD": "0.20"},
            ),
        ):
            result = analyze_document_text(
                SAMPLE_TEXT,
                passage_embeddings=[[1.0, 0.0]],
                categories=categories,
            )

        self.assertEqual(result["category"], "Uncategorized")

    def test_keywords_and_topics_respect_limits(self):
        with patch(
            "src.services.content_analyzer.encode_passages",
            side_effect=fake_embeddings,
        ):
            result = analyze_document_text(
                SAMPLE_TEXT,
                passage_embeddings=[[1.0, 0.0]],
                categories=[],
            )

        keywords = result["keywords"]
        topics = result["topics"]

        self.assertGreaterEqual(len(keywords), 1)
        self.assertLessEqual(len(keywords), 10)

        self.assertGreaterEqual(len(topics), 1)
        self.assertLessEqual(len(topics), 3)

        for keyword in keywords:
            self.assertTrue(keyword.strip())
            self.assertNotIn(keyword.lower(), {
                "the", "and", "for", "with", "from", "into"
            })

        # Every topic must be a phrase taken from the document's
        # candidate phrases, not an unrelated generated label.
        candidates = set(_candidate_phrases(SAMPLE_TEXT))

        for topic in topics:
            self.assertIn(topic, candidates)

    def test_no_categories_returns_uncategorized(self):
        with patch(
            "src.services.content_analyzer.encode_passages",
            side_effect=fake_embeddings,
        ):
            result = analyze_document_text(
                SAMPLE_TEXT,
                passage_embeddings=[[1.0, 0.0]],
                categories=[],
            )

        self.assertEqual(result["category"], "Uncategorized")
        self.assertLessEqual(len(result["keywords"]), 10)
        self.assertLessEqual(len(result["topics"]), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
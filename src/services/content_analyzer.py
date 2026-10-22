import os
import re
from collections import Counter


# These names must match the six default categories in admin_repository.py.
CATEGORY_PROFILES = {
    "Technology": {
        "technology", "software", "computer", "programming",
        "algorithm", "data", "database", "artificial",
        "intelligence", "machine", "learning", "network",
        "security", "cloud", "code", "api", "digital",
        "cybersecurity",
    },
    "Business and Finance": {
        "business", "company", "companies", "customer",
        "marketing", "sales", "strategy", "revenue",
        "product", "management", "market", "leadership",
        "finance", "financial", "bank", "investment",
        "budget", "accounting", "money", "tax", "credit",
        "profit", "transaction", "commerce",
    },
    "Education": {
        "education", "student", "school", "university",
        "teacher", "course", "curriculum", "academic",
        "assignment", "classroom", "exam", "study",
        "teaching", "learning", "assessment",
    },
    "Health and Medicine": {
        "health", "healthcare", "medical", "patient",
        "doctor", "disease", "treatment", "hospital",
        "clinical", "diagnosis", "medicine", "therapy",
    },
    "Law and Government": {
        "legal", "law", "court", "contract", "regulation",
        "compliance", "lawyer", "rights", "litigation",
        "agreement", "policy", "statute", "government",
        "legislation", "regulatory",
    },
    "Science and Research": {
        "science", "scientific", "research", "experiment",
        "physics", "chemistry", "biology", "hypothesis",
        "laboratory", "scientist", "observation", "evidence",
    },
}


STOPWORDS = set("""
a an and are as at be been being by can could did do does
for from had has have he her hers him his how i if in into
is it its may me might more most must my no not of on or our
ours she should so than that the their theirs them then there
these they this those through to too under up us very was we
were what when where which while who why will with would you
your yours also document documents using use used based
""".split())


def extract_keywords(text, limit=10):
    """Extract up to 10 informative words, ranked by frequency."""
    words = re.findall(
        r"[a-zA-Z][a-zA-Z0-9'-]*",
        (text or "").lower(),
    )

    counts = Counter()

    for word in words:
        word = word.strip("-'")

        if (
            len(word) >= 3
            and word not in STOPWORDS
            and not word.isdigit()
        ):
            counts[word] += 1

    ranked = sorted(
        counts,
        key=lambda word: (-counts[word], word),
    )

    return ranked[:max(1, min(limit, 10))]


def categorize_text(text):
    """Return an SRS category and a heuristic confidence score."""
    words = set(
        re.findall(
            r"[a-zA-Z][a-zA-Z0-9'-]*",
            (text or "").lower(),
        )
    )

    scores = {
        category: len(words.intersection(profile))
        for category, profile in CATEGORY_PROFILES.items()
    }

    if not words or max(scores.values(), default=0) == 0:
        return "Uncategorized", 0.0

    best_category = max(
        scores,
        key=lambda category: scores[category],
    )

    # This is a heuristic score, not a calibrated ML probability.
    confidence = min(1.0, scores[best_category] / 3.0)

    try:
        threshold = float(
            os.getenv("CATEGORY_CONFIDENCE_THRESHOLD", "0.20")
        )
    except ValueError:
        threshold = 0.20

    threshold = max(0.0, min(1.0, threshold))

    if confidence < threshold:
        return "Uncategorized", confidence

    return best_category, confidence


def analyze_document_text(text):
    """Return category, confidence, keywords and topic labels."""
    keywords = extract_keywords(text)

    category, confidence = categorize_text(text)

    # Starter topic extraction: select the leading keywords.
    # Semantic grouping into topics remains a future improvement.
    topics = keywords[:3]

    return {
        "category": category,
        "confidence": confidence,
        "keywords": keywords,
        "topics": topics,
    }
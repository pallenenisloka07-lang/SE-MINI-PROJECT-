import os
import re
from collections import Counter

# Starter category profiles.
# Replace these with your team's agreed six categories if different.
CATEGORY_PROFILES = {
    "Technology": {
        "technology", "software", "computer", "programming",
        "algorithm", "data", "database", "artificial",
        "intelligence", "machine", "learning", "network",
        "security", "cloud", "code", "api", "document",
        "processing", "system", "digital",
    },
    "Education": {
        "education", "student", "school", "university",
        "teacher", "course", "curriculum", "academic",
        "assignment", "classroom", "exam", "study",
    },
    "Business": {
        "business", "company", "customer", "marketing",
        "sales", "strategy", "revenue", "product",
        "management", "market", "organization", "leadership",
    },
    "Finance": {
        "finance", "financial", "bank", "investment",
        "budget", "accounting", "money", "tax", "payment",
        "loan", "credit", "profit", "transaction",
    },
    "Health": {
        "health", "healthcare", "medical", "patient",
        "doctor", "disease", "treatment", "hospital",
        "clinical", "diagnosis", "medicine", "therapy",
    },
    "Legal": {
        "legal", "law", "court", "contract", "regulation",
        "compliance", "lawyer", "rights", "litigation",
        "agreement", "policy", "statute",
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
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", text.lower())

    counts = Counter(
        word.strip("-'")
        for word in words
        if len(word.strip("-'")) >= 3
        and word.strip("-'") not in STOPWORDS
        and not word.strip("-'").isdigit()
    )

    ranked = sorted(
        counts,
        key=lambda word: (-counts[word], word),
    )

    return ranked[:max(1, min(limit, 10))]


def categorize_text(text):
    """Choose the strongest category or Uncategorized."""
    words = set(
        re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", text.lower())
    )

    scores = {
        category: len(words.intersection(profile))
        for category, profile in CATEGORY_PROFILES.items()
    }

    if not scores or max(scores.values(), default=0) == 0:
        return "Uncategorized", 0.0

    best_category = max(
        scores,
        key=lambda category: scores[category],
    )

    # Simple heuristic confidence, not a calibrated ML probability.
    confidence = min(1.0, scores[best_category] / 3.0)

    threshold = float(
        os.getenv("CATEGORY_CONFIDENCE_THRESHOLD", "0.20")
    )
    threshold = max(0.0, min(1.0, threshold))

    if confidence < threshold:
        return "Uncategorized", confidence

    return best_category, confidence


def analyze_document_text(text):
    """Produce category, confidence, keywords, and topic labels."""
    keywords = extract_keywords(text)
    category, confidence = categorize_text(text)

    # Each topic is selected from the extracted key terms.
    topics = keywords[:3]

    return {
        "category": category,
        "confidence": confidence,
        "keywords": keywords,
        "topics": topics,
    }
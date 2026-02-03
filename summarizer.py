import re
from collections import defaultdict

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

# Ensure NLTK resources
_resources = [("tokenizers/punkt", "punkt"), ("corpora/stopwords", "stopwords")]
for path, name in _resources:
    try:
        nltk.data.find(path)
    except LookupError:
        nltk.download(name, quiet=True)

STOP_WORDS = set(stopwords.words("english"))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def summarize_text(text: str, ratio: float = 0.3) -> str:
    if not text or not text.strip():
        return ""
    ratio = max(0.1, min(0.9, float(ratio)))
    text = _clean_text(text)
    sentences = sent_tokenize(text)
    if len(sentences) <= 1:
        return text
    words = word_tokenize(text.lower())
    freq = defaultdict(int)
    for w in words:
        if w.isalnum() and w not in STOP_WORDS:
            freq[w] += 1
    if not freq:
        n = max(1, int(len(sentences) * ratio))
        return " ".join(sentences[:n])
    maxf = max(freq.values())
    for w in list(freq.keys()):
        freq[w] = freq[w] / maxf
    sent_scores = {}
    for s in sentences:
        s_words = word_tokenize(s.lower())
        score = 0.0
        count = 0
        for w in s_words:
            if w.isalnum():
                count += 1
                if w in freq:
                    score += freq[w]
        if count > 0:
            sent_scores[s] = score / count
    select_n = max(1, int(len(sentences) * ratio))
    ranked = sorted(sent_scores.items(), key=lambda x: x[1], reverse=True)
    top_sentences = set([s for s, _ in ranked[:select_n]])
    summary_sentences = [s for s in sentences if s in top_sentences]
    if not summary_sentences:
        summary_sentences = sentences[:select_n]
    return " ".join(summary_sentences)
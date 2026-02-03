import re
from collections import defaultdict

import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords

# Ensure NLTK resources
_resources = [("tokenizers/punkt", "punkt"), ("corpora/stopwords", "stopwords")]
for path, name in _resources:
    try:
        nltk.data.find(path)
    except LookupError:
        nltk.download(name, quiet=True)

STOP_WORDS = set(stopwords.words("english"))


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return text


def extract_keywords(text: str, top_n: int = 5):
    words = word_tokenize(text.lower())
    freq = defaultdict(int)
    for w in words:
        if w.isalnum() and w not in STOP_WORDS and len(w) > 2:
            freq[w] += 1
    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in items[:top_n]]


def detect_intent(question: str):
    q = normalize_text(question)
    tokens = q.split()
    patterns = {
        "what_about": [["what", "about"], ["what", "is", "about"], ["tell", "me", "about"]],
        "key_points": [["key", "point"], ["main", "point"], ["important", "point"], ["key", "idea"], ["what", "are", "key"]],
        "make_shorter": [["shorter"], ["shorten"], ["condense"], ["brief"]],
        "explain": [["explain"], ["elaborate"], ["describe"], ["clarify"]],
        "summary_length": [["how", "long"], ["length"], ["word", "count"], ["character", "count"], ["stats"]],
    }
    for intent, pats in patterns.items():
        for pat in pats:
            if all(p in tokens for p in pat):
                return intent
    return "general"


def get_key_points(summary: str, max_points: int = 5):
    sents = sent_tokenize(summary)
    if not sents:
        return []
    keywords = extract_keywords(summary, top_n=10)
    scored = []
    for s in sents:
        ls = s.lower()
        score = sum(1 for k in keywords if k in ls)
        scored.append((s.strip(), score))
    scored.sort(key=lambda x: x[1], reverse=True)
    key_points = [s for s, sc in scored[:max_points] if sc > 0]
    if not key_points:
        key_points = [s.strip() for s in sents[:max_points]]
    return key_points


def make_shorter(summary: str, ratio: float = 0.5):
    try:
        from summarizer import summarize_text
        new = summarize_text(summary, ratio=ratio)
        return new or summary
    except Exception:
        sents = sent_tokenize(summary)
        n = max(1, int(len(sents) * ratio))
        return " ".join(sents[:n])


def explain_summary(summary: str) -> str:
    sents = sent_tokenize(summary)
    word_count = len(summary.split())
    char_count = len(summary)
    keywords = extract_keywords(summary, top_n=5)
    explanation = f"This summary contains {len(sents)} sentence(s), approximately {word_count} words ({char_count} characters). "
    if keywords:
        explanation += "Key topics: " + ", ".join(keywords) + "."
    return explanation


def get_summary_stats(summary: str) -> str:
    word_count = len(summary.split())
    char_count = len(summary)
    char_count_no_spaces = len(summary.replace(" ", ""))
    sentence_count = len(sent_tokenize(summary))
    paragraph_count = len([p for p in summary.split("\n\n") if p.strip()])
    s = f"📊 Summary Statistics:\n\n• Words: {word_count:,}\n• Characters: {char_count:,}\n• Characters (no spaces): {char_count_no_spaces:,}\n• Sentences: {sentence_count}\n• Paragraphs: {paragraph_count}"
    return s


def chat_with_summary(question: str, summary: str) -> str:
    if not summary or not summary.strip():
        return "I don't have a summary to discuss yet. Please generate a summary first!"
    if not question or not question.strip():
        return "Please ask a question about the summary!"
    intent = detect_intent(question)
    try:
        if intent == "what_about":
            keywords = extract_keywords(summary, top_n=5)
            first = sent_tokenize(summary)[0] if sent_tokenize(summary) else summary[:200]
            return f"This summary is about: {', '.join(keywords)}. For example: {first}"
        elif intent == "key_points":
            points = get_key_points(summary, max_points=5)
            if not points:
                return "I couldn't extract clear key points."
            out = "🔑 Key Points:\n"
            for i, p in enumerate(points, 1):
                out += f"{i}. {p}\n"
            return out.strip()
        elif intent == "make_shorter":
            short = make_shorter(summary, ratio=0.5)
            return f"📝 Shorter version:\n\n{short}"
        elif intent == "explain":
            return f"💡 Explanation:\n\n{explain_summary(summary)}"
        elif intent == "summary_length":
            return get_summary_stats(summary)
        else:
            qwords = [w for w in word_tokenize(question.lower()) if w.isalnum() and w not in STOP_WORDS]
            sents = sent_tokenize(summary)
            relevant = []
            for s in sents:
                ls = s.lower()
                if any(q in ls for q in qwords):
                    relevant.append(s)
            if relevant:
                return "Based on your question, here are relevant sentences:\n\n" + " ".join(relevant[:3])
            else:
                return "I didn't find a direct answer in the summary. Try: 'What is this about?', 'Give key points', 'Make it shorter', or 'How long is this summary?'"
    except Exception:
        return "I encountered an error processing your question. Please try rephrasing it."
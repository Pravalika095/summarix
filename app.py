import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

# Optional readability (readability-lxml)
try:
    from readability import Document  # readability-lxml
    HAS_READABILITY = True
except Exception:
    HAS_READABILITY = False

from summarizer import summarize_text
from chatbot import chat_with_summary

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB allowed upload (safe)

# Limits
MAX_TEXT_LENGTH = 200_000
MIN_TEXT_LENGTH = 50  # somewhat lower so many article pages pass

# Jinja filter
@app.template_filter('intcomma')
def intcomma_filter(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return value


def calculate_stats(text: str, summary: str = "") -> dict:
    original_words = len(text.split()) if text else 0
    original_chars = len(text) if text else 0
    original_chars_no_spaces = len(text.replace(" ", "")) if text else 0
    summary_words = len(summary.split()) if summary else 0
    summary_chars = len(summary) if summary else 0
    compression_ratio = 0.0
    if text and summary and len(text) > 0:
        compression_ratio = round((1 - (len(summary) / len(text))) * 100, 1)
    return {
        "original_words": original_words,
        "original_chars": original_chars,
        "original_chars_no_spaces": original_chars_no_spaces,
        "summary_words": summary_words,
        "summary_chars": summary_chars,
        "compression_ratio": compression_ratio,
    }


# ---------------------
# URL helpers & extract
# ---------------------
def _is_valid_url(candidate: str):
    if not candidate:
        return None
    candidate = candidate.strip()
    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = "http://" + candidate
        parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return candidate


def _extract_with_readability(html: str) -> str:
    doc = Document(html)
    summary_html = doc.summary()
    soup = BeautifulSoup(summary_html, "html.parser")
    return soup.get_text(separator="\n\n", strip=True)


def _extract_wikipedia(soup: BeautifulSoup) -> str:
    # Target Wikipedia page structure
    # Prefer #mw-content-text or div.mw-parser-output
    content = soup.find("div", id="mw-content-text") or soup.find("div", class_="mw-parser-output")
    if not content:
        return ""
    paragraphs = []
    # Exclude certain elements like tables, infoboxes, and metadata
    for child in content.find_all(["p", "h2", "h3", "h4"], recursive=False):
        if child.name == "p":
            text = child.get_text(" ", strip=True)
            if text and len(text) >= 40:
                paragraphs.append(text)
        else:
            # keep headings as paragraph separators
            paragraphs.append("\n\n" + child.get_text(" ", strip=True) + "\n\n")
    # If recursive=False didn't collect nested <p>, fall back to searching inside content
    if not paragraphs:
        for p in content.find_all("p"):
            t = p.get_text(" ", strip=True)
            if t and len(t) >= 40:
                paragraphs.append(t)
    return "\n\n".join(paragraphs).strip()


def extract_readable_text(url: str, timeout: int = 12) -> str:
    normalized = _is_valid_url(url)
    if not normalized:
        raise ValueError("Invalid URL. Please include a valid http(s) URL.")

    headers = {
        "User-Agent": "Summarix/1.0 (+https://example.com/) Python requests",
        "Accept": "text/html,application/xhtml+xml"
    }

    try:
        resp = requests.get(normalized, headers=headers, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        logger.warning("Network error fetching URL %s: %s", url, e)
        raise ValueError(f"Network error while fetching the URL: {e}")

    if resp.status_code != 200:
        raise ValueError(f"Failed to fetch page: HTTP {resp.status_code}")

    content_type = (resp.headers.get("Content-Type") or "")
    body = resp.text or ""
    if "html" not in content_type.lower() and "<html" not in body.lower():
        raise ValueError("URL did not return HTML content.")

    # Try readability first (if available)
    if HAS_READABILITY:
        try:
            text = _extract_with_readability(resp.text)
            if text and len(text) >= MIN_TEXT_LENGTH:
                logger.info("Used readability-lxml extraction (len=%d)", len(text))
                return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]{2,}', ' ', text)).strip()
        except Exception as e:
            logger.info("Readability extraction failed: %s", e)

    soup = BeautifulSoup(resp.content, "html.parser")

    # Domain-specific extraction for Wikipedia (reliably structured)
    parsed = urlparse(normalized)
    domain = parsed.netloc.lower()
    if "wikipedia.org" in domain:
        text = _extract_wikipedia(soup)
        if text and len(text) >= MIN_TEXT_LENGTH:
            logger.info("Used Wikipedia-specific extraction (len=%d)", len(text))
            return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]{2,}', ' ', text)).strip()
        # else continue to heuristics

    # Generic heuristics
    # Remove non-content tags
    for tag_name in ("script", "style", "noscript", "iframe", "svg", "picture", "figure", "button", "input", "form"):
        for t in soup.find_all(tag_name):
            t.decompose()

    for tag in soup.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()

    noisy_keywords = [
        "nav", "menu", "header", "footer", "sidebar", "advert", "ads",
        "cookie", "modal", "popup", "subscribe", "promo", "related", "breadcrumb", "share",
        "comment", "comments", "footer", "toolbar", "breadcrumb", "infobox"
    ]

    for elem in list(soup.find_all(True, attrs={"role": True})):
        role = (elem.get("role") or "").lower()
        if any(k in role for k in noisy_keywords):
            elem.decompose()

    for attr in ("id", "class"):
        for kw in noisy_keywords:
            selector = f'[{attr}*="{kw}"]'
            try:
                for tag in soup.select(selector):
                    tag.decompose()
            except Exception:
                continue

    # Prefer <article>
    article_tag = soup.find("article")
    if article_tag:
        text = article_tag.get_text(separator="\n\n", strip=True)
    else:
        paragraphs = []
        for p in soup.find_all("p"):
            p_text = p.get_text(separator=" ", strip=True)
            if not p_text:
                continue
            if len(p_text) < 40:
                continue
            parent = p.parent
            skip = False
            while parent and getattr(parent, "name", None) != "[document]":
                pid = (parent.get("id") or "").lower()
                pcls = " ".join(parent.get("class") or []).lower()
                if any(k in pid for k in noisy_keywords) or any(k in pcls for k in noisy_keywords):
                    skip = True
                    break
                parent = parent.parent
            if skip:
                continue
            paragraphs.append(p_text)
        if paragraphs:
            text = "\n\n".join(paragraphs)
        else:
            candidates = []
            for tag in soup.find_all(True):
                try:
                    t = tag.get_text(separator=" ", strip=True)
                except Exception:
                    continue
                if len(t) > 200:
                    candidates.append((len(t), t))
            if candidates:
                candidates.sort(reverse=True)
                text = candidates[0][1]
            else:
                text = ""

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    if not text or len(text) < MIN_TEXT_LENGTH:
        logger.info("Extracted text length: %d", len(text) if text else 0)
        raise ValueError("No readable article text found on the provided URL. The page might be JavaScript-driven or behind a paywall.")

    return text


# ---------------------
# Routes
# ---------------------
@app.route("/", methods=["GET", "POST"])
def index():
    summary = ""
    original_text = ""
    stats = {}
    error_message = ""
    ratio = 0.3
    url_value = ""

    if request.method == "POST":
        url_input = (request.form.get("url") or "").strip()
        text_input = (request.form.get("text") or "").strip()

        try:
            ratio = float(request.form.get("ratio", 0.3))
            ratio = max(0.1, min(0.9, ratio))
        except Exception:
            ratio = 0.3

        if not url_input and not text_input:
            error_message = "Please provide either a link (URL) or raw text to summarize."
            return render_template("index.html", summary=summary, original_text=original_text, stats=stats,
                                   error_message=error_message, ratio=ratio, max_length=MAX_TEXT_LENGTH,
                                   url_value=url_value)

        if url_input:
            url_value = url_input
            try:
                extracted = extract_readable_text(url_input)
                if len(extracted) < MIN_TEXT_LENGTH:
                    error_message = f"Extracted content too short (min {MIN_TEXT_LENGTH} chars)."
                elif len(extracted) > MAX_TEXT_LENGTH:
                    error_message = f"Extracted content too long (max {MAX_TEXT_LENGTH:,} chars)."
                else:
                    original_text = extracted
                    try:
                        summary = summarize_text(original_text, ratio=ratio)
                    except TypeError:
                        summary = summarize_text(original_text)
                    stats = calculate_stats(original_text, summary)
            except ValueError as ve:
                error_message = str(ve)
            except Exception as e:
                logger.exception("Unexpected extraction error: %s", e)
                error_message = "Unexpected error while extracting content. Check server logs."
        else:
            # raw text flow
            if len(text_input) < MIN_TEXT_LENGTH:
                error_message = f"Text too short. Enter at least {MIN_TEXT_LENGTH} characters."
            elif len(text_input) > MAX_TEXT_LENGTH:
                error_message = f"Text too long. Maximum {MAX_TEXT_LENGTH:,} characters allowed."
            else:
                original_text = text_input
                try:
                    try:
                        summary = summarize_text(original_text, ratio=ratio)
                    except TypeError:
                        summary = summarize_text(original_text)
                    stats = calculate_stats(original_text, summary)
                except Exception:
                    logger.exception("Summarization error")
                    error_message = "Error generating summary."

    else:
        try:
            ratio = float(request.args.get("ratio", 0.3))
            ratio = max(0.1, min(0.9, ratio))
        except Exception:
            ratio = 0.3

    return render_template("index.html", summary=summary, original_text=original_text, stats=stats,
                           error_message=error_message, ratio=ratio, max_length=MAX_TEXT_LENGTH,
                           url_value=url_value)


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        data = request.get_json()
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "No text provided"}), 400
        if len(text) < MIN_TEXT_LENGTH:
            return jsonify({"error": f"Text too short. Minimum {MIN_TEXT_LENGTH} chars required."}), 400
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({"error": f"Text too long. Maximum {MAX_TEXT_LENGTH:,} chars allowed."}), 400
        try:
            ratio = float(data.get("ratio", 0.3))
            ratio = max(0.1, min(0.9, ratio))
        except Exception:
            ratio = 0.3
        try:
            summary = summarize_text(text, ratio=ratio)
        except TypeError:
            summary = summarize_text(text)
        stats = calculate_stats(text, summary)
        return jsonify({"summary": summary, "stats": stats})
    except Exception:
        logger.exception("API summarize error")
        return jsonify({"error": "An error occurred processing your request"}), 500


@app.route("/api/chatbot", methods=["POST"])
def api_chatbot():
    try:
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        data = request.get_json()
        question = (data.get("question") or "").strip()
        summary = (data.get("summary") or "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400
        if not summary:
            return jsonify({"answer": "I don't have a summary to discuss yet. Please generate a summary first!", "error": "No summary available"}), 200
        answer = chat_with_summary(question, summary)
        return jsonify({"answer": answer, "question": question})
    except Exception:
        logger.exception("Chatbot error")
        return jsonify({"error": "An error occurred processing your question."}), 500


@app.errorhandler(413)
def too_large(error):
    return render_template("index.html", error_message="File too large (max 32MB).", original_text="", stats={}, max_length=MAX_TEXT_LENGTH), 413


@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")
    return render_template("index.html", error_message="Internal server error. Try again later.", original_text="", stats={}, max_length=MAX_TEXT_LENGTH), 500


if __name__ == "__main__":
    logger.info("Starting Summarix on http://0.0.0.0:5001")
    app.run(debug=True, host="0.0.0.0", port=5001)
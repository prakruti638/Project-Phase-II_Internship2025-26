from __future__ import annotations
import json
import re
from typing import Optional
from llm_service import call_llm, is_gemini_available

def clean_text_with_gemini(
    text: str,
    *,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
) -> tuple[str, str]:
    """Use an LLM (Gemini/Groq) to clean text via llm_service."""
    prompt = (
        "You will receive raw text. This could be a document, speech, or even song lyrics. "
        "Fix obvious OCR errors, but preserve artistic formatting, stanzas, and paragraphs. "
        "Do NOT summarize. Return only the cleaned text.\n\n"
        f"Text:\n{text}"
    )
    
    result, source = call_llm(prompt, api_key=api_key, model_name=model_name, temperature=0.2)
    if result:
        return result, source

    # Fallback: basic cleaning
    return clean_text_basic(text), "basic"


def clean_text_basic(text: str) -> str:
    """Basic text cleaning using regex."""
    if not text: return ""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


_BASIC_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "while", "for", "to", "of", "in", "on",
    "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "being", "it", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "them", "his", "her", "their", "our", "your",
    "not", "no", "yes", "do", "does", "did", "doing", "have", "has", "had", "having", "can", "could", "will",
    "would", "may", "might", "must", "should", "so", "such", "than", "too", "very",
}

def summarize_text_basic(text: str, *, target_word_count: int = 250) -> str:
    """Lightweight extractive summarization."""
    t = clean_text_basic(text)
    if not t: return ""
    words = t.split()
    original_word_count = len(words)
    
    if target_word_count >= original_word_count:
        target_word_count = max(1, int(original_word_count * 0.8))

    if len(t) > 250_000: t = f"{t[:200_000]}\n\n{t[-50_000:]}"

    target_word_count = max(1, min(2500, int(target_word_count)))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", t) if s.strip()]
    if len(sentences) <= 3: return " ".join(words[:target_word_count]).strip()

    tokens = re.findall(r"[A-Za-z0-9']+", t.lower())
    freqs: dict[str, int] = {}
    for w in tokens:
        if len(w) > 2 and w not in _BASIC_STOPWORDS:
            freqs[w] = freqs.get(w, 0) + 1
    if not freqs: return " ".join(words[:target_word_count]).strip()

    max_f = max(freqs.values())
    for k in freqs: freqs[k] /= max_f

    scored: list[tuple[float, int, str]] = []
    for idx, s in enumerate(sentences):
        stoks = re.findall(r"[A-Za-z0-9']+", s.lower())
        if not stoks: continue
        score_val: float = sum(freqs.get(w, 0.0) for w in stoks)
        score_val *= (1.0 + (0.35 * (1.0 - (idx / max(1, len(sentences) - 1)))))
        scored.append((score_val, idx, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    chosen: list[tuple[int, str]] = []
    wc = 0
    for _, idx, s in scored:
        s_wc = len(s.split())
        if wc + s_wc > target_word_count and wc >= int(target_word_count * 0.6): continue
        chosen.append((idx, s))
        wc += s_wc
        if wc >= target_word_count: break

    chosen.sort(key=lambda x: x[0])
    summary = " ".join(s for _, s in chosen).strip()
    return summary or " ".join(words[:target_word_count]).strip()


def summarize_text_with_gemini(
    text: str,
    *,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    target_word_count: int = 250,
) -> tuple[str, str]:
    """Summarize text via llm_service."""
    t = (text or "").strip()
    if not t: return "", "empty"
    
    original_word_count = len(t.split())
    if target_word_count >= original_word_count:
        target_word_count = max(1, int(original_word_count * 0.8))
        
    if original_word_count <= 10:
        return t, "original"

    prompt = (
        "You will receive text from a document. Create a concise, spoken-friendly summary. "
        f"Target strictly less than {original_word_count} words, ideally about {int(target_word_count)} words. "
        "Keep key facts, names, and numbers. Do not use markdown, headings, or bullet symbols. "
        "Return only plain text.\n\n"
        f"Text:\n{t}"
    )

    result, source = call_llm(prompt, api_key=api_key, model_name=model_name, temperature=0.3)
    if result:
        return result, source

    return summarize_text_basic(t, target_word_count=target_word_count), "basic"


def generate_questions_with_gemini(
    text: str,
    *,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    num_questions: int = 5,
) -> str:
    """Generate questions based on the text via llm_service."""
    t = (text or "").strip()
    if not t: return "No content available to generate questions."

    prompt = (
        f"You will receive text from a document. Generate {num_questions} insightful questions "
        "based on the content to test the reader's understanding. "
        "Return only the questions as a plain text list using '-' for each item, instead of bullet points. "
        "Do not include markdown formatting like bolding unless helpful.\n\n"
        f"Text:\n{t}"
    )

    result, source = call_llm(prompt, api_key=api_key, model_name=model_name, temperature=0.5)
    if result:
        result = result.replace("•", "-").replace("*", "-")
        return result

    return "Failed to generate questions. Please check your API key or connection."


def _extract_json_block(text: str) -> str:
    """Extract a JSON array/object from an LLM response."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start_idx = cleaned.find("[")
    end_idx = cleaned.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return cleaned[start_idx:end_idx + 1]
    return cleaned


def _build_fallback_quiz(text: str, num_questions: int) -> list[dict[str, object]]:
    """Simple deterministic fallback quiz when LLM output is unavailable."""
    t = clean_text_basic(text)
    if not t:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", t) if len(s.strip()) >= 25]
    if not sentences:
        return []

    quiz_items: list[dict[str, object]] = []
    choices = ["Option A", "Option B", "Option C", "Option D"]

    for idx, sentence in enumerate(sentences[:num_questions]):
        prompt_snippet = sentence[:120].strip()
        if not prompt_snippet.endswith((".", "?", "!")):
            prompt_snippet += "..."
        quiz_items.append(
            {
                "question": f"Which statement best matches this idea from the document? \"{prompt_snippet}\"",
                "options": choices,
                "answer_index": 0,
                "explanation": "Fallback quiz item generated without LLM response.",
            }
        )

    return quiz_items


def generate_mcq_quiz_with_gemini(
    text: str,
    *,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    num_questions: int = 5,
) -> list[dict[str, object]]:
    """Generate MCQ quiz objects from text via llm_service."""
    t = (text or "").strip()
    if not t:
        return []

    num_questions = max(5, min(10, int(num_questions)))
    # Keep prompt size bounded for stability and speed.
    if len(t) > 25_000:
        t = f"{t[:18_000]}\n\n{t[-7_000:]}"

    prompt = (
        "You will receive a document text. Create a student self-assessment quiz.\n"
        f"Generate exactly {num_questions} multiple-choice questions.\n"
        "Return ONLY valid JSON as an array of objects.\n"
        "Each object must have keys: question (string), options (array of 4 strings), "
        "answer_index (integer 0-3), explanation (string).\n"
        "Rules:\n"
        "- Questions must test understanding of the text, not trivial wording.\n"
        "- Exactly 4 options per question.\n"
        "- Only one correct option.\n"
        "- Keep language clear for students.\n"
        "- Do not add markdown, comments, or extra text.\n\n"
        f"Text:\n{t}"
    )

    result, _source = call_llm(prompt, api_key=api_key, model_name=model_name, temperature=0.4)
    if not result:
        return _build_fallback_quiz(t, num_questions)

    try:
        json_payload = _extract_json_block(result)
        parsed = json.loads(json_payload)
        if not isinstance(parsed, list):
            return _build_fallback_quiz(t, num_questions)

        normalized: list[dict[str, object]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            options = item.get("options", [])
            answer_index = item.get("answer_index", None)
            explanation = str(item.get("explanation", "")).strip()

            if not question or not isinstance(options, list) or len(options) != 4:
                continue
            clean_options = [str(opt).strip() for opt in options]
            if any(not opt for opt in clean_options):
                continue
            if not isinstance(answer_index, int) or answer_index < 0 or answer_index > 3:
                continue

            normalized.append(
                {
                    "question": question,
                    "options": clean_options,
                    "answer_index": answer_index,
                    "explanation": explanation,
                }
            )
            if len(normalized) >= num_questions:
                break

        if len(normalized) >= 1:
            return normalized[:num_questions]
    except Exception:
        pass

    return _build_fallback_quiz(t, num_questions)


def chat_with_document(
    query: str,
    document_text: str,
    chat_history: list[dict[str, str]],
    *,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
) -> str:
    """Chat with the document content using history."""
    doc_context = (document_text or "").strip()
    
    # Trim context if too long
    if len(doc_context) > 40_000:
        doc_context = f"{doc_context[:30_000]}\n\n[...]\n\n{doc_context[-10_000:]}"

    history_str = ""
    for msg in chat_history[-6:]:  # Keep last 3 turns
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        history_str += f"{role}: {content}\n"

    if doc_context:
        prompt = (
            "You are a helpful AI Audiobook Assistant. Answer questions based on the provided document content. "
            "If the user greets you (e.g., 'hi', 'hello', 'good morning'), respond warmly and acknowledge the document. "
            "If the answer to a question is not in the document, politely say so but offer to help with general questions. "
            "Keep responses concise, friendly, and professional.\n\n"
            f"Document Content:\n{doc_context}\n\n"
            f"Recent Conversation:\n{history_str}"
            f"User: {query}\n"
            "Assistant:"
        )
    else:
        prompt = (
            "You are a helpful AI Audiobook Assistant. No document has been uploaded yet. "
            "If the user greets you, respond warmly. "
            "If the user asks about the document or document-specific questions, politely inform them that you're ready "
            "and waiting for them to upload a PDF, Word, TXT, or Image file so you can help them analyze it. "
            "Keep responses concise and friendly.\n\n"
            f"Recent Conversation:\n{history_str}"
            f"User: {query}\n"
            "Assistant:"
        )

    result, _ = call_llm(prompt, api_key=api_key, model_name=model_name, temperature=0.6)
    return result or "I'm sorry, I couldn't process that request right now."

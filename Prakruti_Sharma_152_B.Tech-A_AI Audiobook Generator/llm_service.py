from __future__ import annotations
import os
from typing import Optional

def _import_gemini():
    """Try to import either google-genai or google-generativeai SDK."""
    try:
        from google import genai
        return genai
    except Exception:
        pass
    try:
        import google.generativeai as genai
        return genai
    except Exception:
        return None

def _import_groq():
    """Safely import the Groq client if available."""
    try:
        import groq
        return groq
    except Exception:
        return None

def is_gemini_available() -> bool:
    """Return True if a Gemini-capable SDK is installed."""
    return _import_gemini() is not None

def call_llm(
    prompt: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.2
) -> tuple[str, str]:
    """
    Core LLM call chain: Gemini (new SDK) -> Gemini (old SDK) -> Groq (Llama) -> Groq (backup).
    Returns (response_text, provider_name). Returns ("", "failed") if all fail.
    """
    gemini_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    groq_llama_key = os.getenv("GROQ_llama", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    genai_module = _import_gemini() if gemini_key else None
    groq_module = _import_groq()

    # 1. Gemini (New SDK)
    if genai_module and hasattr(genai_module, "Client"):
        try:
            client = genai_module.Client(api_key=gemini_key)
            resp = client.models.generate_content(model=model_name, contents=prompt)
            text = (getattr(resp, "text", "") or "").strip()
            if text: return text, "gemini"
        except Exception:
            pass

    # 2. Gemini (Older SDK)
    if genai_module and hasattr(genai_module, "GenerativeModel"):
        try:
            genai_module.configure(api_key=gemini_key)
            model = genai_module.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            text = (getattr(resp, "text", "") or "").strip()
            if text: return text, "gemini"
        except Exception:
            pass

    # 3. Groq (Llama key)
    if groq_module and groq_llama_key:
        try:
            client = groq_module.Groq(api_key=groq_llama_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            text = (resp.choices[0].message.content or "").strip()
            if text: return text, "groq"
        except Exception:
            pass

    # 4. Groq (Default key)
    if groq_module and groq_key:
        try:
            client = groq_module.Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            text = (resp.choices[0].message.content or "").strip()
            if text: return text, "groq"
        except Exception:
            pass

    return "", "failed"


def call_llm_with_image(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.0-flash",
) -> tuple[str, str]:
    """ multimodal call for Gemini to process images with fallbacks."""
    gemini_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    genai_module = _import_gemini() if gemini_key else None

    if not genai_module:
        return "", "failed"

    # Models to try: current requested, then stable flash
    models_to_try = [model_name]
    if "1.5-flash" not in model_name:
        models_to_try.append("gemini-1.5-flash")

    # 1. Gemini (New SDK: google-genai)
    if hasattr(genai_module, "Client"):
        try:
            client = genai_module.Client(api_key=gemini_key)
            # Try to import types locally to avoid early crashes
            try:
                from google.genai import types
            except ImportError:
                types = None

            if types:
                for target_model in models_to_try:
                    try:
                        content = types.Content(
                            parts=[
                                types.Part.from_text(text=prompt),
                                types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                            ]
                        )
                        resp = client.models.generate_content(model=target_model, contents=content)
                        text = (getattr(resp, "text", "") or "").strip()
                        if text: return text, "gemini"
                    except Exception:
                        continue
        except Exception:
            pass

    # 3. Groq Vision Fallback (Llama 3.2 Vision)
    groq_key = os.getenv("GROQ_API_KEY", os.getenv("GROQ_llama", "")).strip()
    if groq_key:
        try:
            import base64
            from groq import Groq
            client = Groq(api_key=groq_key)
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Try a few common vision models in case one is decommissioned
            for vision_model in ["meta-llama/llama-4-scout-17b-16e-instruct", "llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]:
                try:
                    completion = client.chat.completions.create(
                        model=vision_model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{base64_image}",
                                        },
                                    },
                                ],
                            }
                        ],
                        temperature=0.1,
                        max_tokens=1024,
                    )
                    if completion.choices[0].message.content:
                        return completion.choices[0].message.content.strip(), f"groq-{vision_model}"
                except Exception:
                    continue
        except Exception:
            pass

    # 2. Gemini (Older SDK: google-generativeai)
    if hasattr(genai_module, "GenerativeModel"):
        try:
            genai_module.configure(api_key=gemini_key)
            for target_model in models_to_try:
                try:
                    model = genai_module.GenerativeModel(target_model)
                    # Pass as list [prompt, dict] which is the standard vision format for old SDK
                    resp = model.generate_content([
                        prompt, 
                        {"mime_type": mime_type, "data": image_bytes}
                    ])
                    text = (getattr(resp, "text", "") or "").strip()
                    if text: return text, "gemini"
                except Exception:
                    continue
        except Exception:
            pass

    return "", "failed"

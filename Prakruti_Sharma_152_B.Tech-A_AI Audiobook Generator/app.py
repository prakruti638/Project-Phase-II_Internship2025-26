"""
AI Audiobook Generator — Streamlit entry point.
"""
import os
import time
from dotenv import load_dotenv
import streamlit as st

from text_extraction import extract_text, get_word_count
from tts import text_to_speech, VOICE_OPTIONS
from gemini_helper import (
    clean_text_with_gemini,
    summarize_text_with_gemini,
    generate_mcq_quiz_with_gemini,
)

from next_app import (
    init_state,
    apply_style,
    render_listen_section,
    render_chatbot,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
)

load_dotenv()





def render_upload_section(api_key: str) -> None:
    """Step 1: Upload document and extract/clean text."""
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("1. Upload your document")
    with col2:
        lang = st.radio(
            "Language",
            ["English", "Hindi"],
            index=0 if st.session_state.document_language == "English" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="lang_selector"
        )
        st.session_state.document_language = lang

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "docx", "txt", "jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        return

    file_size: int = uploaded_file.size or 0

    if file_size > MAX_FILE_SIZE_BYTES:
        st.error(f"File is too large ({file_size / 1_048_576:.1f} MB). Limit is {MAX_FILE_SIZE_MB} MB.")
        return

    if uploaded_file.name != st.session_state.last_file_name or file_size != st.session_state.last_file_size:
        with st.spinner("Extracting text…"):
            try:
                text = extract_text(uploaded_file, api_key=api_key)
                st.session_state.last_file_name = uploaded_file.name
                st.session_state.last_file_size = file_size
                st.session_state.audio_bytes = None
                st.session_state.audio_file_name = "audiobook.mp3"
                st.session_state.summary_text = ""
                st.session_state.summary_method = ""
                st.session_state.show_summary_preview = False
                st.session_state.clean_method = ""
                st.session_state.quiz_questions = []
                st.session_state.quiz_submitted = False
                st.session_state.quiz_score = 0
                st.session_state.quiz_key_version = 0

                if not text.strip():
                    st.session_state.extracted_text = ""
                    st.warning("No text could be read from this file. Try a different document.")
                else:
                    if api_key:
                        with st.spinner("Cleaning text..."):
                            try:
                                text, method = clean_text_with_gemini(text, api_key=api_key)
                                st.session_state.clean_method = method
                                if method == "gemini":
                                    label = "Gemini cleaning"
                                elif method == "groq":
                                    label = "Groq cleaning"
                                else:
                                    label = "Basic cleaning"
                                popup = st.empty()
                                popup.success(f"✅ {label} completed")
                                time.sleep(1.5)
                                popup.empty()
                            except Exception as e:
                                st.warning(f"Text cleaning error: {e}")

                    st.session_state.extracted_text = text
                    st.session_state.show_preview = True
                    st.session_state.scroll_target = "generate-audio-section"
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not read the file: {exc}")
        return

    if not st.session_state.extracted_text:
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(
            f"📄 {uploaded_file.name}  •  {get_word_count(st.session_state.extracted_text):,} words"
        )
        if st.session_state.clean_method:
            cm = st.session_state.clean_method
            if cm == "gemini":
                cm_label = "Gemini cleaning"
            elif cm == "groq":
                cm_label = "Groq cleaning"
            else:
                cm_label = "Basic cleaning"
            st.caption(f"✨ Cleaning: {cm_label}")
    with col2:
        label = "Hide" if st.session_state.show_preview else "View text"
        if st.button(label, key="toggle_preview"):
            st.session_state.show_preview = not st.session_state.show_preview
            st.rerun()

    if st.session_state.show_preview:
        st.text_area(
            "Extracted text",
            value=st.session_state.extracted_text,
            height=260,
            label_visibility="collapsed",
        )


def render_generate_section(api_key: str) -> None:
    """Step 2: Audio mode, voice, and generate button."""
    if not st.session_state.extracted_text:
        return

    st.markdown("---")
    st.markdown("<div id='generate-audio-section'></div>", unsafe_allow_html=True)
    st.subheader("2. Generate Audio")

    mode = st.radio(
        "Audio mode",
        ["Full audiobook", "Summarized audiobook"],
        index=0,
        horizontal=True,
    )

    summary_target_words = 250
    if mode == "Summarized audiobook":
        original_words = len(st.session_state.extracted_text.split())
        slider_max = max(10, original_words - 1)
        slider_max = min(2000, slider_max)
        
        slider_min = max(5, min(80, slider_max // 2))
        
        # Ensure min_value is strictly less than max_value for Streamlit
        if slider_min >= slider_max:
            slider_min = max(1, slider_max - 5)
            
        slider_val = min(250, slider_max)

        summary_target_words = st.slider(
            "Summary length (words)",
            min_value=slider_min,
            max_value=slider_max,
            value=slider_val,
            step=10 if slider_max <= 250 else 50,
        )

        sum_col1, sum_col2 = st.columns([3, 1])
        with sum_col1:
            if st.session_state.summary_text:
                method = st.session_state.summary_method or "basic"
                if method == "gemini":
                    friendly = "Gemini summary"
                elif method == "groq":
                    friendly = "Groq summary"
                elif method == "original":
                    friendly = "Full text (short input)"
                else:
                    friendly = "Basic summary"
                st.caption(
                    f"📝 Summary ready  •  {get_word_count(st.session_state.summary_text):,} words  •  {friendly}"
                )
        with sum_col2:
            if st.session_state.summary_text:
                label = "Hide" if st.session_state.show_summary_preview else "View summary"
                if st.button(label, key="toggle_summary_preview"):
                    st.session_state.show_summary_preview = not st.session_state.show_summary_preview
                    st.rerun()

        if st.session_state.show_summary_preview and st.session_state.summary_text:
            st.text_area(
                "Summary text",
                value=st.session_state.summary_text,
                height=220,
                label_visibility="collapsed",
            )

    # Filter voices based on selected language
    doc_lang = st.session_state.get("document_language", "English")
    if doc_lang == "Hindi":
        filtered_voices = [v for v in VOICE_OPTIONS.keys() if "Hindi" in v]
        default_idx = 0
    else:
        filtered_voices = [v for v in VOICE_OPTIONS.keys() if "Hindi" not in v]
        default_idx = 1 # US Female

    voice_label = st.selectbox(
        "Voice",
        filtered_voices,
        index=default_idx if default_idx < len(filtered_voices) else 0,
    )

    if not st.button("🎙 Generate audio", key="generate"):
        return

    progress_bar = st.progress(0.0)
    try:
        tts_text = st.session_state.extracted_text
        file_name = "audiobook.mp3"

        if mode == "Summarized audiobook":
            with st.spinner("Summarizing…"):
                summary, method = summarize_text_with_gemini(
                    st.session_state.extracted_text,
                    api_key=api_key or None,
                    target_word_count=summary_target_words,
                )
                st.session_state.summary_text = summary
                st.session_state.summary_method = method
                if method == "gemini":
                    friendly = "Gemini summary"
                elif method == "groq":
                    friendly = "Groq summary"
                elif method == "original":
                    friendly = "Original text"
                else:
                    friendly = "Basic summary"
                popup = st.empty()
                popup.success(f"📝 {friendly} completed")
                time.sleep(1.5)
                popup.empty()
                tts_text = summary
                file_name = "audiobook_summary.mp3"

        with st.spinner("Generating audio…"):
            def on_progress(done: int, total: int) -> None:
                if total <= 0:
                    progress_bar.progress(1.0)
                else:
                    progress_bar.progress(min(1.0, done / total))

            audio = text_to_speech(
                tts_text,
                voice=voice_label,
                progress_callback=on_progress,
            )
            st.session_state.audio_bytes = audio
            st.session_state.audio_file_name = file_name
            st.session_state.audio_voice = voice_label
            
            # Calculate stats
            words = len(tts_text.split())
            st.session_state.audio_word_count = words
            try:
                from pydub import AudioSegment
                audio.seek(0)
                seg = AudioSegment.from_mp3(audio)
                st.session_state.audio_duration_seconds = len(seg) / 1000.0
                audio.seek(0)
            except Exception:
                # Fallback estimate: ~2.5 words per second
                st.session_state.audio_duration_seconds = max(1.0, words / 2.5)
            progress_bar.empty()
            st.toast("✅ Audio ready!", icon="🎙")
            st.session_state.scroll_target = "listen-section"
    except Exception as exc:
        st.error(f"Audio generation failed: {exc}")
    finally:
        progress_bar.empty()


def render_quiz_section(api_key: str) -> None:
    """Step 4: Quiz generation and scoring for learners."""
    source_text = (st.session_state.get("summary_text") or st.session_state.get("extracted_text") or "").strip()
    if not source_text:
        return

    if "quiz_questions" not in st.session_state:
        st.session_state.quiz_questions = []
    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = False
    if "quiz_score" not in st.session_state:
        st.session_state.quiz_score = 0
    if "quiz_question_count" not in st.session_state:
        st.session_state.quiz_question_count = 5
    if "quiz_key_version" not in st.session_state:
        st.session_state.quiz_key_version = 0

    st.markdown("---")
    st.subheader("📝 Quiz Checkpoint")
    st.caption("Generate 5 to 10 MCQs from your uploaded document and check learning progress.")

    left_col, right_col = st.columns([2, 1])
    with left_col:
        question_count = st.slider(
            "Number of MCQ questions",
            min_value=5,
            max_value=10,
            value=int(st.session_state.quiz_question_count),
            step=1,
            key="quiz_count_slider",
        )
        st.session_state.quiz_question_count = question_count
    with right_col:
        if st.button("🧠 Generate quiz", key="generate_quiz_btn", use_container_width=True):
            with st.spinner("Creating quiz questions..."):
                st.session_state.quiz_questions = generate_mcq_quiz_with_gemini(
                    source_text,
                    api_key=api_key or None,
                    num_questions=question_count,
                )
            st.session_state.quiz_submitted = False
            st.session_state.quiz_score = 0
            st.session_state.quiz_key_version += 1
            st.rerun()

    quiz_questions = st.session_state.quiz_questions
    if not quiz_questions:
        st.info("No quiz generated yet. Click 'Generate quiz' to start.")
        return

    st.markdown("### Answer the questions")
    submitted = False
    score = 0
    total = len(quiz_questions)

    for idx, question_data in enumerate(quiz_questions, start=1):
        question_text = str(question_data.get("question", f"Question {idx}"))
        options = question_data.get("options", [])
        answer_index = question_data.get("answer_index", 0)
        explanation = str(question_data.get("explanation", "")).strip()

        if not isinstance(options, list) or len(options) != 4:
            continue

        st.write(f"**Q{idx}. {question_text}**")
        selected = st.radio(
            f"Choose answer for question {idx}",
            options,
            index=None,
            key=f"quiz_q_{st.session_state.quiz_key_version}_{idx}",
            label_visibility="collapsed",
        )

        if st.session_state.quiz_submitted and selected is not None:
            is_correct = selected == options[answer_index]
            if is_correct:
                st.success("Correct")
            else:
                st.error(f"Incorrect. Correct answer: {options[answer_index]}")
            if explanation:
                st.caption(f"Why: {explanation}")
        st.markdown("")

    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        submitted = st.button("✅ Submit quiz", key="submit_quiz_btn", use_container_width=True)
    with action_col2:
        if st.button("🔄 Regenerate quiz", key="regenerate_quiz_btn", use_container_width=True):
            with st.spinner("Generating a fresh quiz..."):
                st.session_state.quiz_questions = generate_mcq_quiz_with_gemini(
                    source_text,
                    api_key=api_key or None,
                    num_questions=st.session_state.quiz_question_count,
                )
            st.session_state.quiz_submitted = False
            st.session_state.quiz_score = 0
            st.session_state.quiz_key_version += 1
            st.rerun()

    if submitted:
        score = 0
        for idx, question_data in enumerate(quiz_questions, start=1):
            options = question_data.get("options", [])
            answer_index = question_data.get("answer_index", 0)
            if not isinstance(options, list) or len(options) != 4:
                continue
            selected = st.session_state.get(f"quiz_q_{st.session_state.quiz_key_version}_{idx}")
            if selected is not None and selected == options[answer_index]:
                score += 1

        st.session_state.quiz_submitted = True
        st.session_state.quiz_score = score
        st.rerun()

    if st.session_state.quiz_submitted:
        score = int(st.session_state.quiz_score)
        progress_pct = int((score / max(1, total)) * 100)
        st.markdown("---")
        st.markdown(f"### Your score: **{score}/{total}**")
        st.progress(progress_pct / 100)
        if progress_pct >= 80:
            st.success("Excellent progress! Keep going.")
        elif progress_pct >= 50:
            st.info("Good attempt. Review explanations and try again.")
        else:
            st.warning("Keep learning and regenerate a new quiz for practice.")


def main() -> None:
    st.set_page_config(page_title="AI Audiobook Generator", layout="wide")
    init_state()

    # Theme toggle (dark / light) in top-right.
    # We set dark_mode before applying styles so the CSS matches the toggle.
    top_cols = st.columns([10, 2])
    with top_cols[1]:
        light_default = st.session_state.get("light_mode", False)
        light_now = st.toggle("Light mode", value=light_default)
        st.session_state.light_mode = light_now

    apply_style()

    st.markdown(
        "Upload a **PDF**, **Word**, **Text**, or **Image** and convert it to speech."
    )
    st.markdown("---")

    api_key = os.getenv("GEMINI_API_KEY", "")
    render_upload_section(api_key)
    render_generate_section(api_key)
    render_listen_section()
    render_quiz_section(api_key)
    render_chatbot()


if __name__ == "__main__":
    main()

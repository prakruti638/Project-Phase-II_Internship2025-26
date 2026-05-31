"""
Audiobook Generator — UI Styling and Playback.
"""
import base64
import html
import re
import streamlit as st
import streamlit.components.v1 as components

import re
import os
import streamlit as st
import streamlit.components.v1 as components

from ui_1 import init_state, apply_style, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB
from ui_2 import avatar_html, avatar_audio_synced_html
from gemini_helper import generate_questions_with_gemini, chat_with_document
from tts import text_to_speech

def generate_notes(text: str, max_points: int = 10) -> str:
    """Create simple bullet-point notes from the text."""
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if not clean:
        return "No content available for notes."
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    bullets = [f"- {s.strip()}" for s in sentences if len(s.strip()) > 40]
    return "\n".join(bullets[:max_points]) or f"- {clean[:200]}..."

def render_listen_section() -> None:
    """Render the listen and download UI."""
    if not st.session_state.audio_bytes:
        return

    st.markdown("---")
    st.markdown("<div id='listen-section'></div>", unsafe_allow_html=True)
    st.subheader("3. Listen & Download")
    
    voice_used = st.session_state.get("audio_voice", "US Female")
    audio_val = st.session_state.audio_bytes.getvalue() if hasattr(st.session_state.audio_bytes, "getvalue") else st.session_state.audio_bytes
    is_dark = not st.session_state.get("light_mode", False)
    
    synced_html = avatar_audio_synced_html(voice_used, audio_val, is_dark)
    if synced_html:
        components.html(synced_html, height=320)
    else:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(avatar_html(voice_used), unsafe_allow_html=True)
        with col2:
            st.audio(st.session_state.audio_bytes, format="audio/mp3")

    dl_col, note_col, qs_col, stat_col = st.columns([1, 1, 1, 1])
    
    with dl_col:
        st.download_button(
            "⬇ Download MP3",
            data=st.session_state.audio_bytes,
            file_name=st.session_state.audio_file_name or "audiobook.mp3",
            mime="audio/mpeg",
            use_container_width=True
        )

    source_text = st.session_state.get("summary_text") or st.session_state.get("extracted_text", "")

    with note_col:
        if st.button("📝 Generate notes", use_container_width=True):
            if not source_text.strip():
                st.warning("No text available to generate notes.")
            else:
                st.session_state.notes_text = generate_notes(source_text)
                st.session_state.scroll_target = "notes-section"
                st.rerun()

    with qs_col:
        if st.button("❓ Generate questions", use_container_width=True):
            if not source_text.strip():
                st.warning("No text available to generate questions.")
            else:
                with st.spinner("Generating questions..."):
                    st.session_state.questions_text = generate_questions_with_gemini(
                        source_text,
                        api_key=os.getenv("GEMINI_API_KEY", "")
                    )
                st.session_state.scroll_target = "questions-section"
                st.rerun()
                
    with stat_col:
        word_count = st.session_state.get('audio_word_count', 0)
        duration = st.session_state.get('audio_duration_seconds', 0.0)
        if duration == 0.0 and word_count > 0:
            duration = max(1.0, word_count / 2.5)

        if hasattr(st, 'popover'):
            with st.popover("📊 Statistics", use_container_width=True):
                st.markdown(f"**Word Count:** {word_count:,} words")
                mins = int(duration // 60)
                secs = int(duration % 60)
                st.markdown(f"**Audio Time:** {mins}m {secs}s")
        else:
            if st.button("📊 Statistics", use_container_width=True):
                st.session_state.show_stats = not st.session_state.get("show_stats", False)
                st.rerun()

    if st.session_state.get("show_stats") and not hasattr(st, 'popover'):
        word_count = st.session_state.get('audio_word_count', 0)
        duration = st.session_state.get('audio_duration_seconds', 0.0)
        if duration == 0.0 and word_count > 0:
            duration = max(1.0, word_count / 2.5)
        mins = int(duration // 60)
        secs = int(duration % 60)
        st.info(f"**Word Count:** {word_count:,} words | **Audio Time:** {mins}m {secs}s")

    if st.session_state.get("notes_text"):
        st.markdown("---")
        st.markdown("<div id='notes-section'></div>", unsafe_allow_html=True)
        st.text_area("Generated Notes", st.session_state.notes_text, height=150)
        
        n_col1, n_col2 = st.columns(2)
        with n_col1:
            st.download_button(
                "⬇ Download notes text",
                data=st.session_state.notes_text,
                file_name="notes.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_notes_text"
            )
        with n_col2:
            if st.button("🎙 Generate Notes Audio", use_container_width=True, key="gen_notes_audio"):
                with st.spinner("Generating audio..."):
                    try:
                        st.session_state.notes_audio_bytes = text_to_speech(
                            st.session_state.notes_text, 
                            voice=voice_used
                        )
                    except Exception as e:
                        st.error(f"Audio generation failed: {e}")

        if st.session_state.get("notes_audio_bytes"):
            st.audio(st.session_state.notes_audio_bytes, format="audio/mp3")
            st.download_button(
                "⬇ Download Notes Audio",
                data=st.session_state.notes_audio_bytes,
                file_name="notes_audio.mp3",
                mime="audio/mpeg",
                use_container_width=True,
                key="dl_notes_audio_btn"
            )

    if st.session_state.get("questions_text"):
        st.markdown("---")
        st.markdown("<div id='questions-section'></div>", unsafe_allow_html=True)
        st.text_area("Generated Questions", st.session_state.questions_text, height=150)
        
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            st.download_button(
                "⬇ Download questions text",
                data=st.session_state.questions_text,
                file_name="questions.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_qs_text"
            )
        with q_col2:
            if st.button("🎙 Generate Questions Audio", use_container_width=True, key="gen_qs_audio"):
                with st.spinner("Generating audio..."):
                    try:
                        st.session_state.questions_audio_bytes = text_to_speech(
                            st.session_state.questions_text, 
                            voice=voice_used
                        )
                    except Exception as e:
                        st.error(f"Audio generation failed: {e}")

        if st.session_state.get("questions_audio_bytes"):
            st.audio(st.session_state.questions_audio_bytes, format="audio/mp3")
            st.download_button(
                "⬇ Download Questions Audio",
                data=st.session_state.questions_audio_bytes,
                file_name="questions_audio.mp3",
                mime="audio/mpeg",
                use_container_width=True,
                key="dl_qs_audio_btn"
            )

    components.html(
        """
        <script>
            function hideAudioDownload() {
                const parent = window.parent;
                if (!parent || !parent.document) return;
                const audios = parent.document.querySelectorAll('audio');
                audios.forEach(a => {
                    a.setAttribute('controlsList', 'nodownload');
                });
            }
            setTimeout(hideAudioDownload, 100);
            setTimeout(hideAudioDownload, 500);
            setTimeout(hideAudioDownload, 1000);
        </script>
        """,
        height=0
    )

    if st.session_state.get("scroll_target"):
        target = st.session_state.scroll_target
        st.session_state.scroll_target = ""
        components.html(
            f"""
            <script>
                function doScroll() {{
                    const parent = window.parent;
                    // Target specific element ID if available in Streamlit DOM
                    const targetEl = parent.document.getElementById('{target}');
                    if (targetEl) {{
                        targetEl.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                    }} else {{
                        // Fallback to scrolling to bottom
                        const selectors = ['section.main', '[data-testid="stAppViewContainer"]', '.block-container'];
                        let scrolled = false;
                        for (let sel of selectors) {{
                            const el = parent.document.querySelector(sel);
                            if (el) {{
                                el.scrollTo({{top: el.scrollHeight, behavior: 'smooth'}});
                                scrolled = true;
                            }}
                        }}
                        if (!scrolled) {{
                            parent.scrollTo({{top: parent.document.body.scrollHeight, behavior: 'smooth'}});
                        }}
                    }}
                }}
                // Execute with slight delays to ensure DOM is updated
                setTimeout(doScroll, 100);
                setTimeout(doScroll, 500);
            </script>
            """,
            height=0
        )

def render_chatbot() -> None:
    """Render the floating chatbot at the bottom right."""
    # Use a popover for the chatbot bubble
    # Custom CSS should handle the positioning of this popover button
    # but popovers in Streamlit are relatively positioned by default.
    # We'll use a div wrapper to target it.
    
    st.markdown('<div class="chatbot-wrapper">', unsafe_allow_html=True)
    with st.popover("💬 Chat", use_container_width=False):
        st.subheader("Document Assistant")
        st.write("Ask me anything about the document.")
        
        # Welcome message
        if not st.session_state.chat_history:
            with st.chat_message("assistant"):
                if st.session_state.get("extracted_text"):
                    st.markdown("👋 I've analyzed your document! Ask me any questions or request a summary.")
                else:
                    st.markdown("👋 Hello! I'm your AI Audiobook Assistant. Upload a document so I can help you analyze it, or just say hi!")
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                user_input = st.text_input("Ask a question...", placeholder="Type your message...", label_visibility="collapsed")
            with col2:
                submit_button = st.form_submit_button("➤", use_container_width=True)
            
            if submit_button and user_input:
                # Add user message to history
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                
                # Generate response
                doc_text = st.session_state.get("extracted_text") or st.session_state.get("summary_text", "")
                response = chat_with_document(
                    user_input, 
                    doc_text, 
                    st.session_state.chat_history,
                    api_key=os.getenv("GEMINI_API_KEY", "")
                )
                
                # Add assistant message to history
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Inject JS to fix the position of the chatbot wrapper
    components.html(
        """
        <script>
            function positionChatbot() {
                const parent = window.parent;
                const wrappers = parent.document.querySelectorAll('div.chatbot-wrapper');
                wrappers.forEach(w => {
                    const button = w.closest('.stElementContainer').querySelector('button');
                    if (button) {
                        button.style.position = 'fixed';
                        button.style.bottom = '25px';
                        button.style.right = '25px';
                        button.style.zIndex = '10000';
                        button.style.borderRadius = '50%';
                        button.style.width = '65px';
                        button.style.height = '65px';
                        button.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)';
                        button.style.display = 'flex';
                        button.style.alignItems = 'center';
                        button.style.justifyContent = 'center';
                        button.style.fontSize = '24px';
                        // Remove label text if it exists but keep the emoji
                        const p = button.querySelector('p');
                        if (p) p.style.display = 'none';
                    }
                });
            }
            setTimeout(positionChatbot, 100);
            setTimeout(positionChatbot, 500);
            setTimeout(positionChatbot, 1000);
        </script>
        """,
        height=0
    )

if __name__ == "__main__":
    st.set_page_config(page_title="Audiobook Generator", page_icon="🎧", layout="wide")
    init_state()
    apply_style()
    
    st.title("🎧 Audiobook Generator")
    
    from ui_1 import render_upload_section
    render_upload_section()
    
    render_listen_section()
    
    render_chatbot()

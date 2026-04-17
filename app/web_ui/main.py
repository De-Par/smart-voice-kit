from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from services.bootstrap import AppContext, build_app_context

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def get_context() -> AppContext:
    return build_app_context()


def _choose_audio_source() -> Any | None:
    source = st.radio(
        "Source",
        options=["Record with microphone", "Upload reference WAV"],
        horizontal=True,
    )

    if source == "Record with microphone":
        return st.audio_input("Record reference speech")

    return st.file_uploader("Upload a reference WAV file", type=["wav"])


def main() -> None:
    st.set_page_config(page_title="iVoice", layout="centered")

    context = get_context()
    service = context.service

    st.title("iVoice")

    language_default = context.settings.asr.language or ""
    language = st.text_input("Language", value=language_default, placeholder="optional")
    audio_file = _choose_audio_source()

    if audio_file is None:
        return

    audio_bytes = audio_file.getvalue()
    if not audio_bytes:
        st.error("The audio file is empty. Record again or upload a new WAV file.")
        return

    st.audio(audio_bytes, format="audio/wav")

    if st.button("Transcribe audio", type="primary", use_container_width=True):
        try:
            with st.spinner("Running local speech analysis..."):
                result = service.transcribe_bytes(
                    audio_bytes,
                    filename=audio_file.name,
                    language=language or None,
                )
        except Exception as error:
            logger.exception("Streamlit transcription failed")
            st.error(f"Transcription failed: {error}")
            return

        st.success("Transcription completed.")
        st.text_area("Transcript", value=result.metadata.transcript, height=200)
        st.text_area("Transcript EN", value=result.metadata.transcript_en, height=200)
        with st.expander("Metadata"):
            st.json(result.metadata.model_dump(mode="json"))


if __name__ == "__main__":
    main()

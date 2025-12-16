import streamlit as st
import svgwrite
import requests
import base64
import tempfile
import hashlib

import streamlit.components.v1 as components
import xml.etree.ElementTree as ET

import music21 as m21

st.set_page_config(
    page_title="Databass - Frequency Transcriber",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------
# CSS Rockabilly 1950s theme
# --------------------------
def local_css():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600&family=Roboto:wght@300;400;500&display=swap');

    .stApp {
        background-color: #040713;
        background-image:
            radial-gradient(circle at 20% 20%, rgba(24,28,49,0.95) 0%, rgba(5,8,20,1) 55%, rgba(2,5,12,1) 100%),
            url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%201600%20900'%20preserveAspectRatio='none'%3E%3Crect%20width='1600'%20height='900'%20fill='%23040713'/%3E%3Cg%20fill='none'%20stroke-linecap='round'%3E%3Cpath%20d='M0%20450%20C120%20300%20240%20600%20360%20450%20S600%20300%20720%20450%20S960%20600%201080%20450%20S1320%20300%201440%20450%20S1560%20600%201600%20450'%20stroke='rgba(111,63,255,0.35)'%20stroke-width='18'/%3E%3Cpath%20d='M0%20450%20C120%20300%20240%20600%20360%20450%20S600%20300%20720%20450%20S960%20600%201080%20450%20S1320%20300%201440%20450%20S1560%20600%201600%20450'%20stroke='rgba(0,224,255,0.55)'%20stroke-width='9'/%3E%3Cpath%20d='M0%20520%20C150%20380%20300%20660%20450%20520%20S750%20380%20900%20520%20S1200%20660%201350%20520%20S1500%20380%201600%20520'%20stroke='rgba(0,255,179,0.45)'%20stroke-width='6'/%3E%3Cpath%20d='M0%20360%20C160%20520%20320%20260%20480%20360%20S800%20520%20960%20360%20S1120%20260%201280%20360%20S1440%20520%201600%20360'%20stroke='rgba(13,110,253,0.4)'%20stroke-width='10'/%3E%3C/g%3E%3C/svg%3E");
        background-size: cover, cover;
        background-attachment: fixed, fixed;
        background-repeat: no-repeat, no-repeat;
        background-blend-mode: screen;
        color: #E6EEFF;
        font-family: 'Roboto', sans-serif;
    }
    header .decoration {
        display: none;
    }
    .hero-section {
        padding: 24px 28px;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(23,39,80,0.8), rgba(11,18,46,0.9));
        border: 1px solid rgba(125,249,255,0.35);
        box-shadow: 0 20px 45px rgba(0,0,0,0.55), 0 0 18px rgba(111,63,255,0.35);
        margin-bottom: 24px;
    }
    .hero-section h1 {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.6rem;
        color: #7DF9FF;
        text-shadow: 0 0 14px rgba(125,249,255,0.6);
        margin-bottom: 0.4rem;
    }
    .hero-section p {
        color: #B4C5FF;
        font-size: 1.05rem;
        margin: 0;
    }
    .stFileUploader {
        background: linear-gradient(135deg, rgba(12,18,42,0.85), rgba(8,12,32,0.85));
        border-radius: 16px;
        padding: 18px;
        border: 1px solid rgba(125,249,255,0.25);
        box-shadow: inset 0 0 18px rgba(0,224,255,0.12);
        margin-bottom: 20px;
    }
    .stFileUploader label {
        color: #E6EEFF !important;
        font-weight: 500;
    }
    .stButton>button {
        background: linear-gradient(135deg, #6F3FFF, #00E0FF);
        color: #050A18;
        border-radius: 999px;
        border: none;
        padding: 0.6rem 1.8rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        box-shadow: 0 12px 30px rgba(0,224,255,0.25);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stButton>button:hover {
        box-shadow: 0 16px 40px rgba(111,63,255,0.35);
        transform: translateY(-1px);
    }
    .stDownloadButton>button {
        background: transparent;
        color: #7DF9FF;
        border: 1px solid rgba(125,249,255,0.4);
        border-radius: 12px;
        padding: 0.5rem 1.4rem;
        box-shadow: 0 0 18px rgba(0,224,255,0.2);
    }
    .stDownloadButton>button:hover {
        background: rgba(125,249,255,0.12);
    }
    .stAlert {
        background-color: rgba(11,18,46,0.85);
        border: 1px solid rgba(125,249,255,0.2);
    }
    </style>
    """, unsafe_allow_html=True
    )

local_css()

# --------------------------
# UI layout
# --------------------------
main_col = st.columns([1, 10, 1])[1]

with main_col:
    for key in ("last_file_signature", "xml_content", "vexflow_notes", "transcription_error", "vexflow_html"):
        st.session_state.setdefault(key, None)
    st.markdown(
        """
        <div class="hero-section">
            <h1>Databass — Frequency Analyser</h1>
            <p>Upload a WAV bass line, let the AI transcribe it, and preview the score in real time.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    audio_file = st.file_uploader("", type=["wav"])
    # url = 'https://databass-77430240595.europe-west1.run.app/full_pipeline_xml'
    url = 'http://127.0.0.1:8080/full_pipeline_xml'

    if audio_file:
        file_bytes = audio_file.getvalue()
        signature = hashlib.md5(file_bytes).hexdigest()

        if st.session_state.get("last_file_signature") != signature:
            try:
                with st.spinner("Analyse en cours…"):
                    response = requests.post(
                        url,
                        files={"file": (audio_file.name, file_bytes, audio_file.type or "audio/wav")},
                        data={"model_type": "conv2d"}
                    )
                    response.raise_for_status()
            except requests.RequestException as exc:
                st.session_state.update({
                    "transcription_error": f"Erreur lors de l'appel API: {exc}",
                    "xml_content": None,
                    "vexflow_notes": None,
                    "vexflow_html": None,
                    "last_file_signature": None,
                })
            else:
                xml_content = response.text
                print(xml_content)
                html_content = build_music21j_html(xml_content)
                st.session_state.update({
                    "last_file_signature": signature,
                    "xml_content": xml_content,
                    "vexflow_html": html_content,
                    "vexflow_notes": None,
                    "transcription_error": None,
                })
        if st.session_state.get("transcription_error"):
            st.error(st.session_state["transcription_error"])
        else:
            if st.session_state.get("vexflow_html"):
                components.html(st.session_state["vexflow_html"], height=520, scrolling=False)
            else:
                st.warning("Aucune note à afficher.")
            if st.session_state.get("xml_content"):
                st.download_button(
                    label="Télécharger le XML",
                    data=st.session_state["xml_content"],
                    file_name="melody_output.xml",
                    mime="application/xml"
                )
    else:
        st.session_state.update({
            "last_file_signature": None,
            "xml_content": None,
            "vexflow_notes": None,
            "vexflow_html": None,
            "transcription_error": None,
        })
        ""

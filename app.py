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


def parse_musicxml_with_music21(xml_content):
    """Parse le XML avec music21 et retourne les notes sous forme de liste."""
    # Sauvegarder le XML dans un fichier temporaire
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_xml:
        tmp_xml.write(xml_content.encode())
        tmp_xml_path = tmp_xml.name

    # Charger le XML avec music21
    score = m21.converter.parse(tmp_xml_path)
    notes = []

    # Extraire les notes
    for element in score.flat.notes:
        pitch = str(element.pitch)
        # Extraire la lettre de la note (ex: 'D' ou 'D#')
        note_letter = pitch[:-1]
        # Extraire l'octave (ex: '2')
        octave = str(int(pitch[-1]) + 2)

        # Convertir la lettre en minuscule et ajouter le slash (ex: 'd#/2')
        pitch_vexflow = f"{note_letter}/{octave}"
        note_info = {
            "pitch": pitch_vexflow,
            "quarterLength": element.duration.quarterLength,
            "vexDuration": convert_duration(element.duration.quarterLength),
            "beat": element.beat,
            "measure": element.measureNumber
        }
        notes.append(note_info)

    return notes


def convert_duration(quarter_length):
    """Convertit une durée music21 en durée VexFlow."""
    if quarter_length == 1.0:
        return "q"  # Noire
    elif quarter_length == 2.0:
        return "h"  # Blanche
    elif quarter_length == 4.0:
        return "w"  # Ronde
    elif quarter_length == 0.5:
        return "8"  # Croche
    elif quarter_length == 0.25:
        return "16"  # double Croche
    elif quarter_length == 0.125:
        return "32"  # triple croche
    elif quarter_length == 0.0625:
        return "64"  # quadruple croche
    else:
        return "q"  # Par défaut


def prepare_vexflow_data(xml_content):
    notes = parse_musicxml_with_music21(xml_content)
    vexflow_notes = []

    for note in notes:
        quarter_length = note["quarterLength"]

        # ignorer les durées trop courtes si tu veux
        if quarter_length < 0.125:
            continue

        vexflow_notes.append({
            "pitch": note["pitch"],
            "duration": note["vexDuration"],
            "beat": note["beat"],
            "measure": note["measure"]
        })

    return vexflow_notes



def vexflow_component(xml, notes_per_line=20):
    notes = prepare_vexflow_data(xml)
    total_lines = max(1, (len(notes) + notes_per_line - 1) // notes_per_line)
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500&family=Roboto:wght@300;500&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/vexflow@1.2.91/releases/vexflow-min.js"></script>
        <style>
            :root {{
                color-scheme: dark;
            }}
            html {{
                height: 100%;
            }}
            body {{
                height: 93%;
                width: 94%;
                margin: 0;
                padding: 24px;
                padding-bottom: 0;
                font-family: 'Roboto', sans-serif;
                color: #E6EEFF;
                border-radius: 18px;
                background: linear-gradient(135deg, rgba(18,32,64,0.88), rgba(9,16,38,0.92));
                border: 1px solid rgba(125,249,255,0.25);
                box-shadow: 0 26px 50px rgba(0,0,0,0.55), 0 0 28px rgba(111,63,255,0.35), inset 0 0 18px rgba(0,224,255,0.12);

            }}
            .score-header {{
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 16px;
                color: #9AAAE0;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                font-size: 0.75rem;
            }}
            .score-header::before {{
                content: "";
                width: 36px;
                height: 2px;
                background: linear-gradient(90deg, rgba(0,224,255,0.7), rgba(111,63,255,0.25));
            }}
            #output {{
                width: 100%;
                min-height: 240px;
                border-radius: 14px;
                overflow: hidden;
            }}
            #output svg {{
                background: radial-gradient(circle at 20% 20%, rgba(16,26,56,0.95), rgba(7,12,30,0.92));
                border-radius: 14px;
                box-shadow: inset 0 0 30px rgba(0,224,255,0.18);
            }}
        </style>
    </head>
    <body>
            <div class="score-header">AI Partition</div>
            <div id="output"></div>
        <script>
            const neonAccent = "#7DF9FF";
            const neonBeam = "rgba(111,63,255,0.65)";

            function createBeams(notes, notesData) {{
                const beams = [];
                let group = [];
                for (let i = 0; i < notes.length; i++) {{
                    const current = notesData[i];
                    const prev = notesData[i - 1];
                    const beamable = ["8", "16", "32"].includes(current.duration);
                    const newGroup = !prev || current.measure !== prev.measure || Math.floor(current.beat) !== Math.floor(prev.beat);
                    if (!beamable || newGroup) {{
                        if (group.length > 1) {{
                            beams.push(new Vex.Flow.Beam(group));
                        }}
                        group = beamable ? [notes[i]] : [];
                    }} else {{
                        group.push(notes[i]);
                    }}
                }}
                if (group.length > 1) {{
                    beams.push(new Vex.Flow.Beam(group));
                }}
                beams.forEach(beam => {{
                    beam.render_options.fill_style = neonBeam;
                    beam.render_options.stroke_style = neonBeam;
                    beam.render_options.shadow_color = "rgba(0,224,255,0.35)";
                    beam.render_options.shadow_blur = 6;
                }});
                return beams;
            }}

            function renderVexFlow(notesData, notesPerLine) {{
                const div = document.getElementById("output");
                div.innerHTML = "";
                const totalLines = Math.max(1, Math.ceil(notesData.length / notesPerLine));
                const renderer = new Vex.Flow.Renderer(div, Vex.Flow.Renderer.Backends.SVG);
                renderer.resize(960, 220 * totalLines);
                const ctx = renderer.getContext();
                ctx.setFont("14px 'Roboto'", 14, "");
                ctx.setFillStyle("#E6EEFF");

                for (let lineIndex = 0; lineIndex < totalLines; lineIndex++) {{
                    const start = lineIndex * notesPerLine;
                    const slice = notesData.slice(start, start + notesPerLine);
                    const y = 30 + lineIndex * 160;

                    ctx.save();
                    ctx.setStrokeStyle("rgba(125,249,255,0.35)");
                    const stave = new Vex.Flow.Stave(20, y, 900);
                    stave.addClef("bass").setContext(ctx).draw();
                    ctx.restore();

                    const vexNotes = slice.map(noteData => {{
                        const note = new Vex.Flow.StaveNote({{
                            keys: [noteData.pitch],
                            duration: noteData.duration
                        }});
                        note.setStyle({{
                            fillStyle: neonAccent,
                            strokeStyle: neonAccent
                        }});
                        if (noteData.pitch.includes("#")) {{
                            const accidental = new Vex.Flow.Accidental("#");
                            accidental.setStyle({{ fillStyle: neonAccent, strokeStyle: neonAccent }});
                            note.addAccidental(0, accidental);
                        }}
                        return note;
                    }});

                    const beams = createBeams(vexNotes, slice);
                    Vex.Flow.Formatter.FormatAndDraw(ctx, stave, vexNotes);
                    beams.forEach(beam => beam.setContext(ctx).draw());
                }}
            }}

            renderVexFlow({notes}, {notes_per_line});
        </script>
    </body>
    </html>
    """
    st.components.v1.html(html, height=240 * total_lines + 160)


def build_music21j_html(xml_content: str) -> str:
    encoded_xml = base64.b64encode(xml_content.encode("utf-8")).decode("utf-8")
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<style>
    html {{ background: transparent; }}
    body {{ margin: 0; background: transparent; }}
    #score {{ padding: 12px; }}
</style>
<script>
    window.m21conf = {{ loadSoundfont: false }};
</script>
<script src="https://cdn.jsdelivr.net/npm/music21j/releases/music21.debug.min.js"></script>
</head>
    <body>
        <div id="score"></div>
        <script>
            const xmlString = atob("{encoded_xml}");
            const target = document.getElementById("score");
            target.innerHTML = "<p style='color:#9AAAE0;font-family:Roboto,sans-serif;'>Chargement de la partition…</p>";
            sp = new music21.musicxml.xmlToM21.ScoreParser();
            score = sp.scoreFromText(xmlString);
            target.innerHTML = "";
            score.appendNewDOM(target);
        </script>
    </body>
</html>
"""

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
            loading_placeholder = st.empty()
            loading_placeholder.markdown("""
            <div style="display:flex;justify-content:center;margin:24px 0;">
                <svg width="320" height="200" viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg">
                    <defs>
                        <radialGradient id="bgGlow" cx="50%" cy="50%" r="65%">
                            <stop offset="0%" stop-color="rgba(0,224,255,0.45)"/>
                            <stop offset="70%" stop-color="rgba(15,25,55,0.05)"/>
                            <stop offset="100%" stop-color="rgba(7,12,30,0)"/>
                        </radialGradient>
                        <linearGradient id="neckGlow" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stop-color="#7DF9FF"/>
                            <stop offset="50%" stop-color="#6F3FFF"/>
                            <stop offset="100%" stop-color="#00FFC6"/>
                        </linearGradient>
                        <filter id="neonGlow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                            <feMerge>
                                <feMergeNode in="coloredBlur"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                    <rect x="0" y="0" width="320" height="200" fill="url(#bgGlow)" opacity="0.55"/>
                    <g filter="url(#neonGlow)">
                        <path d="M70 130 C40 100 40 60 80 50 C110 45 130 70 150 70 C180 72 210 40 210 22 C230 26 250 36 252 54 C238 74 236 90 246 104 C232 118 216 132 190 132 C170 128 156 118 140 110 C118 118 106 140 102 158 C92 162 78 152 70 130Z"
                              fill="none" stroke="url(#neckGlow)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M196 28 L220 12" stroke="#7DF9FF" stroke-width="5" stroke-linecap="round">
                            <animate attributeName="stroke-width" values="5;8;5" dur="1.4s" repeatCount="indefinite"/>
                        </path>
                        <circle cx="245" cy="104" r="10" fill="rgba(111,63,255,0.65)">
                            <animate attributeName="r" values="10;16;10" dur="1.6s" repeatCount="indefinite"/>
                            <animate attributeName="opacity" values="0.8;0.4;0.8" dur="1.6s" repeatCount="indefinite"/>
                        </circle>
                        <polyline points="250,46 262,36 257,60 270,52"
                                  fill="none" stroke="#00FFC6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <animate attributeName="stroke-opacity" values="0.2;1;0.2" dur="1s" repeatCount="indefinite"/>
                        </polyline>
                        <path d="M82 52 Q120 44 150 70" stroke="#00FFC6" stroke-width="3" stroke-linecap="round" stroke-dasharray="8 12">
                            <animate attributeName="stroke-dashoffset" values="0;-40" dur="2s" repeatCount="indefinite"/>
                        </path>
                    </g>
                </svg>
            </div>
            """, unsafe_allow_html=True)
            try:
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
                html_content = vexflow_component(
                    xml_content,
                    notes_per_line=20
                )
                st.session_state.update({
                    "last_file_signature": signature,
                    "xml_content": xml_content,
                    "vexflow_html": html_content,
                    "vexflow_notes": None,
                    "transcription_error": None,
                })
            finally:
                loading_placeholder.empty()
    else:
        st.session_state.update({
            "last_file_signature": None,
            "xml_content": None,
            "vexflow_notes": None,
            "vexflow_html": None,
            "transcription_error": None,
        })
        ""

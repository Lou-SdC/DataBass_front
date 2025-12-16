import streamlit as st
import svgwrite
import requests
import base64
import tempfile

import streamlit.components.v1 as components
import xml.etree.ElementTree as ET

import music21 as m21

# Optional aubio
try:
    import aubio
    AUBIO_AVAILABLE = True
except Exception:
    AUBIO_AVAILABLE = False

st.set_page_config(page_title="Databass - Frequency Transcriber", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------
# CSS Rockabilly 1950s theme
# --------------------------
def local_css():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Concert+One&family=Rock+Salt&display=swap');

    .stApp {
        background: radial-gradient(circle at 10% 10%, #1a1a1a 0%, #0f0f0f 40%), url('https://i.imgur.com/nBDPLoS.png');
        background-blend-mode: overlay;
        color: #FAF3E0;
        background-size: cover;
    }
    header .decoration {
        display: none;
    }
    h1, .big-title {
        font-family: 'Concert One', cursive;
        color: #F2CB05;
        text-shadow: 2px 2px #C72C41;
    }
    .retro-box {
        background: linear-gradient(145deg, rgba(20,20,20,0.6), rgba(10,10,10,0.6));
        border: 2px solid #F2CB05;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 6px 6px 0px 0px rgba(199,44,65,0.25);
    }
    .stButton>button {
        background-color: #C72C41;
        color: white;
        border-radius: 8px;
        border: 2px solid #F2CB05;
    }
    .note-display {
        font-family: 'Rock Salt', cursive;
        font-size: 1.5rem;
        color: #FAF3E0;
        background: rgba(0,0,0,0.3);
        padding: 8px;
        border-radius: 8px;
        border: 1px solid #C72C41;
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


def prepare_vexflow_data(notes):
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



def vexflow_component(notes, notes_per_line=20):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/vexflow@1.2.91/releases/vexflow-min.js"></script>
        <style>
            body {{
                background-color: white;
                margin: 0;
                padding: 0;
            }}
            #output {{
                background-color: white;
            }}
            svg {{
                background-color: white;
            }}
        </style>
    </head>
    <body>
        <div id="output"></div>
        <script>
            function isBeamable(noteData) {{
                return ["8", "16", "32"].includes(noteData.duration);
            }}

            function createBeams(notes, notesData) {{
                const beams = [];
                let group = [];

                for (let i = 0; i < notes.length; i++) {{
                    const current = notesData[i];
                    const prev = notesData[i - 1];
                    const beamable = ["8", "16", "32"].includes(current.duration);
                    const newGroup =
                        !prev ||
                        current.measure !== prev.measure ||
                        Math.floor(current.beat) !== Math.floor(prev.beat);

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

                return beams;
            }}

            function renderVexFlow(notesData, notesPerLine) {{
                const div = document.getElementById("output");
                const renderer = new Vex.Flow.Renderer(div, Vex.Flow.Renderer.Backends.SVG);
                renderer.resize(1000, 300 * Math.ceil(notesData.length / notesPerLine));
                const ctx = renderer.getContext();

                // Découpe les notes en groupes pour chaque ligne
                for (let i = 0; i < notesData.length; i += notesPerLine) {{
                    const group = notesData.slice(i, i + notesPerLine);
                    const y = 20 + (i / notesPerLine) * 120;

                    const stave = new Vex.Flow.Stave(10, y, 900);
                    stave.addClef("bass").setContext(ctx).draw();

                    const vexNotes = group.map(noteData => {{
                        const note = new Vex.Flow.StaveNote({{
                            keys: [noteData.pitch],
                            duration: noteData.duration
                        }});
                        if (noteData.pitch.includes('#')) {{
                            note.addAccidental(0, new Vex.Flow.Accidental('#'));
                        }}
                        return note;
                    }});

                    const beams = createBeams(vexNotes, group);

                    // Formatter et dessiner les notes
                    Vex.Flow.Formatter.FormatAndDraw(ctx, stave, vexNotes);

                    // Dessiner les beams par-dessus
                    beams.forEach(beam => {{
                        beam.setContext(ctx).draw();
                    }});
                }}
            }}

            renderVexFlow({notes}, {notes_per_line});
        </script>
    </body>
    </html>
    """
    st.components.v1.html(html, height=350 * (1 + len(notes) // notes_per_line))







# --------------------------
# UI layout
# --------------------------
st.title("🎸 Databass — Frequency Transcriber")
st.markdown("Upload ton fichier audio et transforme le en partition avec notre juke-box 🎼🔥")
 #visualise le spectre, prédis les notes et exporte MusicXML / TAB.")


audio_file = st.file_uploader("📤 Dépose un fichier WAV ici", type=["wav"])
col1, col2 = st.columns([2,3])

#url = 'https://databass-77430240595.europe-west1.run.app/full_pipeline'
url = 'http://127.0.0.1:8000/full_pipeline_xml'


# Sélection du modèle
model_type = st.selectbox(
    "Choisir le type de modèle",
    options=["conv2d", "randforest"],
    index=0
)

if audio_file:
    if st.button("Envoyer"):
        # Préparer les données pour la requête
        files = {"file": (audio_file.name, audio_file.read(), audio_file.type)}
        data = {"model_type": model_type}

        # Envoyer la requête POST
        response = requests.post(
            url,
            files=files,
            data=data
        )

        if response.status_code == 200:
            # Récupérer le contenu XML
            xml_content = response.text

            # Parser le XML avec music21
            notes = parse_musicxml_with_music21(xml_content)

            # Préparer les données pour VexFlow
            vexflow_notes = prepare_vexflow_data(notes)

            # Afficher la partition avec VexFlow
            if vexflow_notes:
                vexflow_component(vexflow_notes)
            else:
                st.warning("Aucune note à afficher.")

            # Après avoir récupéré xml_content
            st.download_button(
                label="Télécharger le XML",
                data=xml_content,
                file_name="melody_output.xml",
                mime="application/xml"
            )


        else:
            st.error(f"Erreur {response.status_code}: {response.text}")


else:
    st.info("Dépose un fichier audio pour commencer. Exemple : ligne de basse monophonique (WAV/MP3).")

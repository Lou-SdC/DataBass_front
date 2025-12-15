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
        note_info = {
            "pitch": f"{element.name[0].lower()}/{element.octave}",
            "duration": str(element.duration.quarterLength)
        }
        notes.append(note_info)

    print(notes)
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
        return "4"  # Croche
    elif quarter_length == 0.25:
        return "8"  # double Croche
    elif quarter_length == 0.125:
        return "16"  # triple croche
    elif quarter_length == 0.0625:
        return "32"  # quadruple croche
    else:
        return "q"  # Par défaut


def prepare_vexflow_data(notes):
    """Prépare les données des notes pour VexFlow."""
    vexflow_notes = []
    for note in notes:
        pitch = note["pitch"]
        quarter_length = float(note["duration"])
        vexflow_duration = convert_duration(quarter_length)

        vexflow_notes.append({
            "pitch": pitch,
            "duration": vexflow_duration
        })

    return vexflow_notes

def vexflow_component(notes):
    """Affiche une partition avec VexFlow."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/vexflow@1.2.91/releases/vexflow-min.js"></script>
        <style>
            body { background-color: white; margin: 0; padding: 0; }
            #output { width: 100%; height: 300px; background-color: white; }
        </style>
    </head>
    <body>
        <div id="output"></div>
        <script>
            function renderVexFlow(notesData) {
                const div = document.getElementById("output");
                const renderer = new Vex.Flow.Renderer(div, Vex.Flow.Renderer.Backends.SVG);
                renderer.resize(1000,300)
                const ctx = renderer.getContext();

                // Créer une portée
                const stave = new Vex.Flow.Stave(10, 10, 700);
                stave.addClef("bass").setContext(ctx).draw();

                // Créer les notes
                const notes = notesData.map(noteData => {
                    return new Vex.Flow.StaveNote({
                        keys: [noteData.pitch],
                        duration: noteData.duration
                    });
                });

                // Formater et dessiner les notes
                Vex.Flow.Formatter.FormatAndDraw(ctx, stave, notes);
            }

            const notesData = !NOTES_DATA!;
            renderVexFlow(notesData);
        </script>
    </body>
    </html>
    """
    html = html.replace("!NOTES_DATA!", str(notes).replace("'", '"'))
    st.components.v1.html(html, height=350)


# --------------------------
# Tablature generator (4-string bass E A D G)
# --------------------------
STRING_PITCHES = {'E': 40, 'A': 45, 'D': 50, 'G': 55}  # MIDI numbers for open strings (E2..G3)
STRING_ORDER = ['G', 'D', 'A', 'E']  # top to bottom for typical tab SVG

def midi_to_fret(midi_note):
    """
    Find a good (string, fret) pair for given midi_note on 4-string bass EADG,
    preferring minimal fret >=0 and fret <= 24
    """
    if midi_note is None:
        return (None, None)
    best = None
    for s, open_m in STRING_PITCHES.items():
        fret = midi_note - open_m
        if 0 <= fret <= 24:
            # choose smallest absolute fret
            if best is None or fret < best[1]:
                best = (s, fret)
    # If none found within 0-24, allow negative or higher (wrap to nearest)
    if best is None:
        # allow nearest by absolute distance
        best = min(((s, abs(midi_note - open_m)) for s, open_m in STRING_PITCHES.items()), key=lambda x: x[1])
        # compute fret (may be negative)
        s = best[0]
        fret = midi_note - STRING_PITCHES[s]
        best = (s, fret)
    return best

def generate_tab_svg(midi_seq, filename=None):
    """
    midi_seq: list of tuples (midi, duration_quarter)
    returns SVG bytes
    """
    # layout params
    width = 1100
    margin = 20
    line_spacing = 18
    top = margin
    # create svg
    dwg = svgwrite.Drawing(size=(width, 200 + len(midi_seq)*5))
    # header
    dwg.add(dwg.rect(insert=(0,0), size=('100%','100%'), fill='transparent'))
    # draw 4 lines per measure-like across width
    y_positions = [top + i*line_spacing for i in range(4)]
    for y in y_positions:
        dwg.add(dwg.line(start=(margin, y), end=(width-margin, y), stroke='#FAF3E0', stroke_width=2))
    # place fret numbers at increasing x
    x = margin + 30
    step = max(60, (width-2*margin-60)//max(1, len(midi_seq)))
    for midi, dur in midi_seq:
        name = "—"
        if midi is None:
            name = "x"
            string = 'E'
        else:
            string, fret = midi_to_fret(midi)
            name = str(fret)
        # find y for string
        idx = STRING_ORDER.index(string) if string in STRING_ORDER else 3
        y = y_positions[idx]
        dwg.add(dwg.text(name, insert=(x, y+6), fill='#C72C41', font_size=16, font_family='Rock Salt'))
        x += step
    return dwg.tostring().encode('utf-8')



# --------------------------
# UI layout
# --------------------------
st.title("🎸 Databass — Frequency Transcriber")
st.markdown("Upload ton fichier audio et transforme le en partition avec notre juke-box 🎼🔥")
 #visualise le spectre, prédis les notes et exporte MusicXML / TAB.")


audio_file = st.file_uploader("📤 Dépose un fichier WAV ici", type=["wav"])
col1, col2 = st.columns([2,3])

#url = 'https://databass-77430240595.europe-west1.run.app/full_pipeline'
url = 'http://127.0.0.1:8000/full_pipeline'


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

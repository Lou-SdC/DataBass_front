import streamlit as st
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
import io
import svgwrite
from music21 import stream, note, meter, tempo, metadata
import base64
import tempfile
import os

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

# --------------------------
# Helpers : f0 detection
# --------------------------
def extract_f0_aubio(y, sr, hop_length=512):
    """
    Use aubio to extract f0 -> returns times, freqs (Hz) with Nones for unvoiced.
    """
    if not AUBIO_AVAILABLE:
        return None
    hop_s = hop_length / float(sr)
    tolerance = 0.8
    method = "yin"
    a = aubio.pitch(method, 2048, hop_length, sr)
    a.set_unit("Hz")
    a.set_silence(-40)
    pitches = []
    confidences = []
    times = []
    for i in range(0, len(y), hop_length):
        frame = y[i:i+hop_length].astype(np.float32)
        if len(frame) < hop_length:
            frame = np.pad(frame, (0, hop_length - len(frame)), 'constant')
        pitch = a(frame)[0]
        confidence = a.get_confidence()
        t = (i) / sr
        if pitch <= 0.0 or confidence < 0.6:
            pitches.append(np.nan)
        else:
            pitches.append(pitch)
        confidences.append(confidence)
        times.append(t)
    return np.array(times), np.array(pitches), np.array(confidences)

def extract_f0_librosa(y, sr, frame_length=2048, hop_length=512):
    # Use librosa's pyin (if available) for f0 tracking
    try:
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=40, fmax=1000,
                                                     sr=sr, frame_length=frame_length, hop_length=hop_length)
        times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
        f0 = np.where(voiced_flag, f0, np.nan)
        return times, f0, voiced_probs
    except Exception as e:
        # fallback naive via librosa.yin
        f0 = librosa.yin(y, fmin=40, fmax=1000, sr=sr, frame_length=frame_length, hop_length=hop_length)
        times = librosa.times_like(f0, sr=sr, hop_length=hop_length)
        return times, f0, np.ones_like(f0)

def hz_to_note_name(hz):
    if np.isnan(hz) or hz <= 0:
        return ("Rest", None)
    midi = librosa.hz_to_midi(hz)
    midi_rounded = int(np.round(midi))
    name = librosa.midi_to_note(midi_rounded)
    return (name, midi_rounded)

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
# MusicXML generator via music21
# --------------------------
def generate_musicxml(midi_seq, title="Transcription"):
    s = stream.Score()
    s.insert(0, metadata.Metadata())
    s.metadata.title = title
    s.metadata.composer = "Databass Transcriber"
    p = stream.Part()
    p.append(tempo.MetronomeMark(number=100))
    p.append(meter.TimeSignature('4/4'))
    for midi, dur in midi_seq:
        if midi is None:
            r = note.Rest(quarterLength=dur)
            p.append(r)
        else:
            n = note.Note()
            n.pitch.midi = int(midi)
            n.quarterLength = float(dur)
            p.append(n)
    s.append(p)
    # write to temp file and read bytes
    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.musicxml')
    s.write('musicxml', fp=tmpf.name)
    tmpf.close()
    with open(tmpf.name, 'rb') as f:
        data = f.read()
    os.unlink(tmpf.name)
    return data

# --------------------------
# UI layout
# --------------------------
st.title("🎸 Databass — Frequency Transcriber")
st.markdown("Upload ton fichier audio et transforme le en partition + tablature avec notre juke-box 🎼🔥")
 #visualise le spectre, prédis les notes et exporte MusicXML / TAB.")


with st.sidebar:
    st.header("Paramètres")
    sr = st.selectbox("Fréquence d'échantillonnage (sr)", options=[22050, 44100, 48000], index=1)
    hop_length = st.slider("Hop length (samples)", min_value=256, max_value=2048, value=512, step=256)
    use_aubio = st.checkbox("Utiliser aubio si disponible (meilleur f0 pour basse)", value=AUBIO_AVAILABLE)
    transposition = st.slider("Transposition (demi-tons) pour basse", -24, 24, 0)

uploaded = st.file_uploader("📤 Dépose un fichier WAV/MP3 ici", type=["wav", "mp3", "m4a"])
col1, col2 = st.columns([2,3])

if uploaded:
    # load audio into librosa
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.' + uploaded.name.split('.')[-1])
    tf.write(uploaded.read())
    tf.flush()
    y, sr_audio = librosa.load(tf.name, sr=sr)
    duration = librosa.get_duration(y=y, sr=sr)
    st.sidebar.write(f"Durée : {duration:.2f}s — Échantillons: {len(y)}")
    # spectrogram
    with col1:
        st.markdown("### 🔊 Spectrogramme")
        fig, ax = plt.subplots(figsize=(6,3))
        S = librosa.stft(y, n_fft=2048, hop_length=hop_length)
        S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)
        img = librosa.display.specshow(S_db, sr=sr, hop_length=hop_length, x_axis='time', y_axis='hz', ax=ax)
        ax.set_title("Spectrogramme")
        plt.colorbar(img, ax=ax, format="%+2.0f dB")
        st.pyplot(fig)

    # f0 extraction
    with st.spinner("Extraction de la fondamentale..."):
        if use_aubio and AUBIO_AVAILABLE:
            times, f0s, confs = extract_f0_aubio(y, sr, hop_length=hop_length)
        else:
            times, f0s, confs = extract_f0_librosa(y, sr, frame_length=2048, hop_length=hop_length)

    # map f0 to note names (and midi)
    notes = []
    midi_seq = []
    for hz in f0s:
        if np.isnan(hz):
            notes.append(("Rest", None))
            midi_seq.append((None, 0.5))
        else:
            name, midi = hz_to_note_name(hz)
            # quantize octaves and basic duration (simple: every frame -> 1/ (sr/hop))
            notes.append((name, midi))
            midi_seq.append((midi, 0.5))  # default small dur, we'll re-quantize later

    # Basic length and a slider to step through time
    st.markdown("### 🎚️ Prévision dynamique des notes")
    t_index = st.slider("Position (s)", min_value=0.0, max_value=float(duration), value=0.0, step=round(hop_length/sr,3))
    # find nearest frame
    nearest_idx = (np.abs(times - t_index)).argmin()
    cur_hz = f0s[nearest_idx]
    cur_name, cur_midi = hz_to_note_name(cur_hz)

    col_note, col_conf = st.columns([3,1])
    with col_note:
        st.markdown("<div class='note-display'>Note estimée : <strong style='color:#F2CB05'>{}</strong></div>".format(cur_name), unsafe_allow_html=True)
        st.write(f"Fréquence : {cur_hz:.1f} Hz" if not np.isnan(cur_hz) else "Pas de note détectée")
    with col_conf:
        st.metric("Confiance", f"{(confs[nearest_idx]*100):.0f}%" if len(confs)>nearest_idx else "N/A")

    # Show a simple table of times -> notes for the first N frames
    st.markdown("#### Aperçu (temps → note)")
    preview = []
    for i in range(min(40, len(times))):
        hz = f0s[i]
        n, m = hz_to_note_name(hz)
        preview.append((f"{times[i]:.2f}", n))
    st.table(preview)

    # Simple quantization: merge consecutive same midi to one note with counted frames
    quant = []
    prev = (None, None)
    count = 0
    for midi, dur in midi_seq:
        if prev[0] == midi:
            count += 1
        else:
            if prev[0] is not None or count>0:
                quant.append((prev[0], count))
            prev = (midi, 1)
            count = 1
    quant.append((prev[0], count))

    # Convert counts to quarterLength approximations
    frame_quarter = (hop_length / sr) / 0.25  # how many frames per quarter note (approx)
    midi_for_export = []
    for midi, frames_count in quant:
        qlen = max(0.25, round((frames_count * (hop_length/sr)) / 0.25) * 0.25)  # quantize to quarter fractions
        midi_for_export.append((midi, qlen))

    # show downloadable MusicXML and Tab
    with st.expander("🎼 Export / Téléchargements"):
        xml_bytes = generate_musicxml(midi_for_export, title="Transcription Databass")
        st.download_button("⬇️ Télécharger MusicXML", data=xml_bytes, file_name="transcription.musicxml", mime="application/xml")

        svg_bytes = generate_tab_svg([(m if m is not None else None, d) for m,d in midi_for_export])
        st.download_button("⬇️ Télécharger Tablature (SVG)", data=svg_bytes, file_name="tablature.svg", mime="image/svg+xml")

    # Playback (simple)
    with st.expander("🔊 Lecture (audio upload)"):
        st.audio(tf.name, format='audio/wav')

    # Visual timeline: plot note sequence over time
    with col2:
        st.markdown("### ⏱️ Timeline des notes détectées")
        fig2, ax2 = plt.subplots(figsize=(9,3))
        # convert midi values to pitches for plotting (nan -> 0)
        midi_plot = np.array([m if m is not None else np.nan for m in [m for (_,m) in notes]])
        ax2.plot(times, midi_plot, marker='o', linestyle='-', markersize=3)
        ax2.set_ylabel("MIDI note")
        ax2.set_xlabel("Time (s)")
        ax2.set_title("Pitch track (MIDI)")
        st.pyplot(fig2)

else:
    st.info("Dépose un fichier audio pour commencer. Exemple : ligne de basse monophonique (WAV/MP3).")

# 🌊 culture-ocean: Generative Maui Ocean Beach Acoustic Synthesizer

A real-time procedural DSP physical-acoustic sound synthesizer modeled after the shorelines of Maui, Hawaiʻi. Generates infinite, non-repeating coastal soundscapes on demand directly through ALSA / system audio output or WAV rendering with negligible CPU utilization (~0.2%).

Rather than looping pre-recorded audio samples, `culture-ocean` continuously models the physical fluid dynamics, bubble acoustics, sand percolation, trade winds, and swell sets mathematically in real-time.

---

## 🌺 Acoustic Modeling & DSP Architecture

1. **Pacific Groundswell & Set Dynamics:**
   - Real-world Pacific swell periods (9–18 seconds) modeled using Markovian wave set clustering (3–5 energetic waves arriving consecutively followed by a calming lull).
   - Equal-power stereo panning drift simulates the natural lateral peeling progression of waves breaking across a coastline.

2. **Layered Wave Physics:**
   - **Pelagic Ocean Floor Bed:** Sub-bass brownian noise resonance (< 110 Hz) providing the deep physical body of open Pacific water mass.
   - **Breaker Turbulence & Lip Collapse:** Resonant bandpass-filtered noise with dynamic spectral centroid sweeping from high cresting turbulence down to low-mid rolling surge.
   - **Shorebreak Thump:** Low-frequency impact impulse (55 Hz damped sine resonator) simulating waves dumping onto shallow sand ledges.
   - **Foam Effervescence (Swash):** High-frequency resonant fizz (2.2 kHz – 9.5 kHz) with microbubble granular amplitude modulation modeling millions of bursting air bubbles as water washes up the beach slope.
   - **Sand & Coral Backwash Undertow:** Granular friction percolation modeling the textured drag of water receding through coarse volcanic and coral sand.

3. **Maui Trade Winds (*Ka Makani*):**
   - Dual-LFO modulated bandpassed pink noise (85 Hz – 750 Hz) simulating warm tropical breezes whispering across dunes and ironwood pines.

4. **Hawaiian Coastal Wildlife:**
   - Subtle, sparse procedural whistles of the Pacific Golden-Plover (*Kōlea*) drifting across the stereo field at natural intervals.

---

## 🏖️ Built-in Beach Presets

| Preset | Location / Profile | Acoustic Character |
| :--- | :--- | :--- |
| `napili` *(default)* | **Napili Bay & Kapalua Coves** | Calm, sheltered cove with soft coral sand swash, gentle rhythmic lapping, and light warm trade breeze. |
| `makena` | **Makena / Big Beach** | Powerful Pacific shorebreak thuds, deep low-end resonance, and energetic churning backwash. |
| `northshore` | **Paia & Hoʻokipa** | Rolling outer reef surf lines, steady Hawaiian trade winds through ironwood pines. |
| `keawakapu` | **Keawakapu & Wailea** | Ultra-peaceful South Maui evening shoreline; slow rhythmic wave sets, fine sand percolation, and soft sunset lull. |

---

## 🚀 Installation & Usage

### Prerequisites
- Python 3.8+
- `numpy`, `scipy`
- `aplay` (ALSA) or standard audio output

### CLI Commands

```bash
# Play default preset (Napili Bay) continuously in background
culture-ocean play

# Play with a custom duration and volume
culture-ocean play --preset makena --duration 20m --volume 0.5
culture-ocean play --preset northshore --duration 1h

# Check playback status
culture-ocean status
culture-ocean status --json

# Stop active playback
culture-ocean stop

# List available presets
culture-ocean presets

# Render to a standalone WAV file
culture-ocean render output.wav --preset napili --duration 60s

# Stream raw 16-bit 48kHz stereo PCM to stdout (pipe into ffmpeg/sox/etc.)
culture-ocean stream --preset makena | aplay -f S16_LE -r 48000 -c 2
```

---

## 📦 License
MIT License

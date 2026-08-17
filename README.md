# 🌊 culture-ocean: Generative Hawaiian Ocean Beach Acoustic Synthesizer

A real-time procedural DSP physical-acoustic sound synthesizer modeled after the iconic shorelines of Maui and Kauaʻi, Hawaiʻi. Generates infinite, non-repeating coastal soundscapes on demand directly through ALSA / system audio output or WAV rendering with negligible CPU utilization (~0.2%).

Rather than looping pre-recorded audio samples, `culture-ocean` continuously models the physical fluid dynamics, bubble acoustics, sand percolation, trade winds, distant outer barrier reefs, and swell sets mathematically in real-time.

---

## 🌺 Acoustic Modeling & DSP Architecture

1. **Pacific Groundswell & Set Dynamics:**
   - Real-world Pacific swell periods (8.5–19 seconds) modeled using Markovian wave set clustering (3–5 energetic waves arriving consecutively followed by a calming lull).
   - Equal-power stereo panning drift simulates the natural lateral peeling progression of waves breaking across a coastline.

2. **Layered Wave & Water Physics:**
   - **Pelagic Ocean Floor Bed:** Sub-bass brownian noise resonance (< 110 Hz) providing the deep physical body of open Pacific water mass.
   - **Breaker Turbulence & Lip Collapse:** Resonant bandpass-filtered noise with dynamic spectral centroid sweeping from high cresting turbulence down to low-mid rolling surge.
   - **Shorebreak Thump:** Low-frequency impact impulse (55 Hz damped sine resonator) simulating waves dumping onto shallow sand ledges.
   - **Distant Outer Barrier Reef Breakers:** Atmospheric HF attenuation filter (420 Hz lowpass) modeling giant ocean swells breaking on outer barrier reefs hundreds of yards offshore (crucial for Kauaʻi's Anini and Keʻe reefs).
   - **Foam Effervescence (Swash):** High-frequency resonant fizz (2.2 kHz – 9.5 kHz) with microbubble granular amplitude modulation modeling millions of bursting air bubbles as water washes up the beach slope.
   - **Sand & Coral Backwash Undertow:** Granular friction percolation modeling the textured drag of water receding through coarse volcanic and coral sand.

3. **Hawaiian Trade Winds (*Ka Makani*):**
   - Dual-LFO modulated bandpassed pink noise (85 Hz – 750 Hz) simulating warm tropical breezes whispering across dunes, sea cliffs, and ironwood pines.

4. **Hawaiian Coastal Wildlife:**
   - Procedural calls of native coastal birds:
     - *Kōlea* (Pacific Golden-Plover): soft descending coastal slurs.
     - *Koaʻe kea* (White-tailed Tropicbird): high-pitched undulating aerial trills echoing off Na Pali / Hanalei sea cliffs.

---

## 🏖️ Built-in Beach Presets

### 🌺 Maui
| Preset | Location / Profile | Acoustic Character |
| :--- | :--- | :--- |
| `napili` *(default)* | **Napili Bay & Kapalua Coves** | Calm, sheltered cove with soft coral sand swash, gentle rhythmic lapping, and light warm trade breeze. |
| `makena` | **Makena / Big Beach** | Powerful Pacific shorebreak thuds, deep low-end resonance, and energetic churning backwash. |
| `northshore` | **Paia & Hoʻokipa** | Rolling outer reef surf lines, steady Hawaiian trade winds through ironwood pines. |
| `keawakapu` | **Keawakapu & Wailea** | Ultra-peaceful South Maui evening shoreline; slow rhythmic wave sets, fine sand percolation, and soft sunset lull. |

### 🌿 Kauaʻi
| Preset | Location / Profile | Acoustic Character |
| :--- | :--- | :--- |
| `hanalei` | **Hanalei Bay** | Grand emerald crescent bay framed by waterfalls; long-period North Pacific groundswells peeling into the rivermouth with lush mountain amphitheater mist. |
| `polihale` | **Polihale & Barking Sands** | Booming, high-energy shorebreak slamming massive desert dunes facing the Niʻihau channel, dry roaring winds, and intense churning undertow. |
| `kee` | **Keʻe Beach & Na Pali** | Deep rolling outer barrier reef breaks 200m offshore beneath towering sea cliffs, with a tranquil crystal lagoon swash and soaring *Koaʻe kea* calls. |
| `poipu` | **Poipu Beach** | Sunny golden tombolo split by coral reefs; rhythmic gentle surf lapping sheltered sandy lagoons with warm afternoon trade breezes. |
| `anini` | **Anini Beach & Barrier Reef** | Hawaii's widest protective fringing reef; constant distant white-water roar 400m offshore paired with ultra-tranquil glassy ripples along shallow sandbars. |

---

## 🚀 Installation & Usage

### Prerequisites
- Python 3.8+
- `numpy`, `scipy`
- `aplay` (ALSA) or standard audio output

### CLI Commands

```bash
# Play default preset (Napili Bay, Maui) continuously in background
culture-ocean play

# Play classic Kauaʻi beaches
culture-ocean play --preset hanalei --duration 30m
culture-ocean play --preset polihale --volume 0.5
culture-ocean play --preset kee --duration 1h
culture-ocean play --preset anini --volume 0.4

# Check playback status
culture-ocean status
culture-ocean status --json

# Stop active playback
culture-ocean stop

# List all available presets grouped by island
culture-ocean presets

# Render to a standalone WAV file
culture-ocean render output.wav --preset hanalei --duration 60s

# Stream raw 16-bit 48kHz stereo PCM to stdout (pipe into ffmpeg/sox/etc.)
culture-ocean stream --preset kee | aplay -f S16_LE -r 48000 -c 2
```

---

## 📦 License
MIT License

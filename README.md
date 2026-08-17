# 🌊 culture-ocean: Generative Hawaiian Ocean Beach Acoustic Synthesizer

A real-time procedural DSP physical-acoustic sound synthesizer modeled after the iconic shorelines of Maui and Kauaʻi, Hawaiʻi. Generates infinite, non-repeating coastal soundscapes on demand directly through ALSA / system audio output or WAV rendering with negligible CPU utilization (~0.2%).

Rather than looping pre-recorded audio samples, `culture-ocean` continuously models the physical fluid dynamics, bubble acoustics, volcanic sand/pebble friction, blowholes, hollow reef barrels, trade winds, distant outer barrier reefs, tropical rain squalls, and swell sets mathematically in real-time.

---

## 🌺 Acoustic Modeling & DSP Architecture

1. **Pacific Groundswell & Live Buoy Coupling:**
   - Real-world Pacific swell periods (8.5–19 seconds) modeled using Markovian wave set clustering (3–5 energetic waves arriving consecutively followed by a calming lull).
   - **Live NOAA Telemetry Ingestion (Default ON):** Ingests live swell height, dominant period, and direction from offshore NOAA NDBC buoys (e.g. Buoy 51205 Pauwela, Maui) and Open-Meteo marine/weather stations to dynamically scale wave energy, swell timing, trade winds, and live precipitation.
   - Equal-power stereo panning drift simulates the natural lateral peeling progression of waves breaking across a coastline.

2. **24-Hour Diurnal Circadian Cycle (Default ON):**
   - Automatically synchronizes with Hawaiian Standard Time (HST) to modulate coastal acoustics:
     - **Dawn (*Kawaipuna / Kakahiaka*):** Glassy morning swells, gentle swash, low wind, active morning birds.
     - **Day (*Awakea*):** Brisk Hawaiian trade winds, energetic breaker collapses, crisp effervescence.
     - **Sunset (*Nāulu / Ahiahi*):** Golden-hour trade lull, warm low-end acoustic body, relaxing meditative rhythm.
     - **Night (*Pō*):** Nocturnal coastal crickets (*Laupala*) pulsating in kiawe groves, cool katabatic mountain breezes flowing down Haleakalā, deeper sub-bass swell bed, and resting diurnal birds.

3. **Tropical Squalls & Rain on Ocean:**
   - Procedural stochastic Poisson droplet impact modeling simulating tropical rain showers striking the ocean surface, high-frequency water surface sizzle, and distant rolling Pacific thunder rumbles.

4. **Layered Wave & Coastal Physics:**
   - **Pelagic Ocean Floor Bed:** Sub-bass brownian noise resonance (< 110 Hz) providing the deep physical body of open Pacific water mass.
   - **Breaker Turbulence & Lip Collapse:** Resonant bandpass-filtered noise with dynamic spectral centroid sweeping from high cresting turbulence down to low-mid rolling surge.
   - **Hollow Barrel Resonance:** Swept acoustic cavity resonance simulating plunging right-hand reef barrels (e.g. *Honolua Point*).
   - **Shorebreak Thump:** Low-frequency impact impulse (55 Hz damped sine resonator) simulating waves dumping onto shallow sand ledges and lava rock.
   - **Volcanic Blowhole & Sea Cave Surges:** Deep air/water compression impulse (< 45 Hz) modeling cavernous blowholes and sea caves (e.g. *Waʻānapanapa*).
   - **Basalt Pebble Drag & Undertow:** Granular friction modeling coarse black volcanic shingle/pebble rattle during heavy undertows.
   - **Distant Outer Barrier Reef Breakers:** Atmospheric HF attenuation filter (420 Hz lowpass) modeling giant ocean swells breaking on outer barrier reefs hundreds of yards offshore.
   - **Foam Effervescence (Swash):** High-frequency resonant fizz (2.2 kHz – 9.5 kHz) with microbubble granular amplitude modulation modeling millions of bursting air bubbles.

5. **Hawaiian Coastal Wildlife & Fauna:**
   - Procedural calls of native coastal birds and nocturnal insects:
     - *Kōlea* (Pacific Golden-Plover): soft descending coastal slurs.
     - *Koaʻe kea* (White-tailed Tropicbird): undulating aerial trills echoing off sea cliffs.
     - *Noio* (Brown Noddy / Shearwater): gentle oceanic churring trills over offshore reefs.
     - *Laupala* / Coastal Tree Crickets: rhythmic nocturnal syncopated pulses in coastal groves.

---

## 🏖️ Built-in Beach Presets

### 🌺 Maui
| Preset | Location / Profile | Acoustic Character |
| :--- | :--- | :--- |
| `napili` *(default)* | **Napili Bay & Kapalua Coves** | Calm, sheltered cove with soft coral sand swash, gentle rhythmic lapping, and light warm trade breeze. |
| `makena` | **Makena / Big Beach** | Powerful Pacific shorebreak thuds, deep low-end resonance, and energetic churning backwash. |
| `northshore` | **Paia & Hoʻokipa** | Rolling outer reef surf lines, steady Hawaiian trade winds through ironwood pines. |
| `keawakapu` | **Keawakapu & Wailea** | Ultra-peaceful South Maui evening shoreline; slow rhythmic wave sets, fine sand percolation, and soft sunset lull. |
| `honolua` *(new)* | **Honolua Bay & Point Break** | Lush valley amphitheater with long-period northwest swell wrapping into perfect peeling hollow reef barrels and canopy winds. |
| `waianapanapa` *(new)* | **Waʻānapanapa Black Sand & Lava Tubes** | Dramatic East Maui black basalt pebble beach with cavernous blowhole surges, sea-cave echoes, and volcanic shingle undertow friction. |
| `la-perouse` *(new)* | **Keoneʻōʻio / La Perouse Bay** | Jagged black aʻā lava coast facing the Alenuihāhā channel; raw swells slamming into rock ledges with fierce spray and isolated winds. |
| `molokini` *(new)* | **Molokini Crater & Caldera Reef** | Offshore volcanic caldera with 360-degree pelagic swell wrap, deep oceanic mass, outer caldera reef wash, and wheeling seabirds. |

### 🌿 Kauaʻi
| Preset | Location / Profile | Acoustic Character |
| :--- | :--- | :--- |
| `hanalei` | **Hanalei Bay** | Grand emerald crescent bay framed by waterfalls; long-period North Pacific groundswells peeling into the rivermouth with mountain mist. |
| `polihale` | **Polihale & Barking Sands** | Booming, high-energy shorebreak slamming massive desert dunes facing the Niʻihau channel, dry roaring winds, and intense churning undertow. |
| `kee` | **Keʻe Beach & Na Pali** | Deep rolling outer barrier reef breaks 200m offshore beneath towering sea cliffs, with a tranquil crystal lagoon swash and soaring *Koaʻe kea*. |
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
# Play default preset (Napili Bay, Maui) with live NOAA sync and circadian time active
culture-ocean play

# Shuffle Mode: continuously wanders between random beach locations & acoustic settings
culture-ocean play --shuffle --shuffle-interval 10m

# Play specific new coastal presets
culture-ocean play --preset honolua
culture-ocean play --preset waianapanapa
culture-ocean play --preset la-perouse
culture-ocean play --preset molokini

# Engage tropical rain / squall generator
culture-ocean play --preset hanalei --rain --rain-intensity 0.7

# Force specific diurnal lighting / phase
culture-ocean play --preset keawakapu --time night   # Pō Mode (night crickets & offshore breeze)
culture-ocean play --preset napili --time dawn       # Kawaipuna Mode (glassy water & waking birds)
culture-ocean play --preset makena --time sunset     # Nāulu Mode (warm golden-hour lull)

# Check playback status (shows live NOAA buoy swell, wind, rain, and circadian phase)
culture-ocean status
culture-ocean status --json

# Stop active playback
culture-ocean stop

# List all available presets grouped by island
culture-ocean presets

# Render to a standalone WAV file
culture-ocean render output.wav --preset waianapanapa --duration 60s --rain

# Stream raw 16-bit 48kHz stereo PCM to stdout (pipe into ffmpeg/sox/etc.)
culture-ocean stream --preset honolua | aplay -f S16_LE -r 48000 -c 2
```

---

## 📦 License
MIT License

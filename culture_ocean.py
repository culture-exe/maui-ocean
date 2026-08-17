#!/usr/bin/env python3
"""
Hawaiian Ocean Beach Synthesizer (culture-ocean)
Generative, on-demand ocean beach acoustic landscape engine modeled after Maui & Kauaʻi shorelines.
Features live NOAA buoy telemetry sync, 24-hour diurnal circadian transitions,
tropical squalls/rain, shuffle mode, and black sand / blowhole / hollow barrel physical acoustics.
"""

import sys
import os
import time
import json
import signal
import random
import argparse
import subprocess
import threading
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.synth_engine import HawaiianOceanSynthesizer, SAMPLE_RATE
from src.live_data import fetch_live_telemetry, determine_circadian_phase

STATE_DIR = Path.home() / '.local/state/culture-ocean'
PID_FILE = STATE_DIR / 'ocean.pid'
INFO_FILE = STATE_DIR / 'ocean.json'

def parse_duration(val):
    if not val or str(val).lower() in ('inf', 'infinite', '0', 'none'):
        return None
    val = str(val).strip().lower()
    if val.endswith('s'):
        return float(val[:-1])
    elif val.endswith('m'):
        return float(val[:-1]) * 60.0
    elif val.endswith('h'):
        return float(val[:-1]) * 3600.0
    try:
        return float(val)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid duration format: '{val}'. Use e.g. 30s, 10m, 1h, or raw seconds.")

def get_active_process():
    if not PID_FILE.exists():
        return None, None
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return None, None
    
    try:
        os.kill(pid, 0)
    except OSError:
        try:
            PID_FILE.unlink(missing_ok=True)
            INFO_FILE.unlink(missing_ok=True)
        except Exception: pass
        return None, None

    info = {}
    if INFO_FILE.exists():
        try:
            info = json.loads(INFO_FILE.read_text())
        except Exception: pass

    return pid, info

def stop_playback():
    pid, info = get_active_process()
    if not pid:
        return False, "No active ocean soundscape playback found."
    
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    
    try:
        PID_FILE.unlink(missing_ok=True)
        INFO_FILE.unlink(missing_ok=True)
    except Exception: pass
    
    preset = info.get('preset', 'unknown')
    return True, f"Stopped ocean soundscape (PID {pid}, preset: {preset})."

def run_audio_stream(
    preset='napili',
    volume=1.0,
    duration=None,
    birds=True,
    enable_live=True,
    circadian_mode='auto',
    rain=False,
    rain_intensity=None,
    shuffle=False,
    shuffle_interval=600.0,
    output_wav=None,
    raw_stdout=False
):
    """Core audio loop for streaming to ALSA or file."""
    forced_rain = None
    if rain:
        forced_rain = rain_intensity if rain_intensity is not None else 0.55
    elif rain_intensity is not None:
        forced_rain = rain_intensity

    all_presets = list(HawaiianOceanSynthesizer.PRESETS.keys())
    if shuffle and preset == 'napili':
        preset = random.choice(all_presets)

    synth = HawaiianOceanSynthesizer(
        preset_name=preset,
        sample_rate=SAMPLE_RATE,
        enable_live=enable_live,
        circadian_mode=circadian_mode,
        rain_intensity=forced_rain
    )
    if not birds:
        synth.preset['wildlife_prob'] = 0.0

    chunk_size = 4096
    total_samples = int(duration * SAMPLE_RATE) if duration else None
    samples_produced = 0

    aplay_proc = None
    wav_file = None

    if output_wav:
        import wave
        wav_file = wave.open(output_wav, 'wb')
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
    elif raw_stdout:
        pass
    else:
        cmd = ['aplay', '-q', '-D', 'default', '-f', 'S16_LE', '-r', str(SAMPLE_RATE), '-c', '2']
        aplay_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def close_handles():
        nonlocal aplay_proc, wav_file
        if aplay_proc:
            try:
                aplay_proc.stdin.close()
                aplay_proc.terminate()
                aplay_proc.wait(timeout=1.0)
            except Exception:
                try: aplay_proc.kill()
                except Exception: pass
            aplay_proc = None
        if wav_file:
            try: wav_file.close()
            except Exception: pass
            wav_file = None

    def sig_handler(sig=None, frame=None):
        close_handles()
        try:
            PID_FILE.unlink(missing_ok=True)
            INFO_FILE.unlink(missing_ok=True)
        except Exception: pass
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    last_telemetry_refresh = time.time()
    last_shuffle_time = time.time()
    current_preset = preset

    def update_state_file():
        if not INFO_FILE.exists():
            return
        try:
            cur_info = json.loads(INFO_FILE.read_text())
            p_info = HawaiianOceanSynthesizer.PRESETS.get(current_preset, {})
            cur_info['preset'] = current_preset
            cur_info['island'] = p_info.get('island', 'Hawaii')
            cur_info['preset_name'] = p_info.get('name', 'Custom')
            cur_info['telemetry'] = synth.last_telemetry
            INFO_FILE.write_text(json.dumps(cur_info, indent=2) + '\n')
        except Exception:
            pass

    try:
        while True:
            if total_samples and samples_produced >= total_samples:
                break

            to_gen = chunk_size
            if total_samples and (samples_produced + to_gen) > total_samples:
                to_gen = total_samples - samples_produced

            now = time.time()

            if (now - last_telemetry_refresh) > 600.0:
                last_telemetry_refresh = now
                synth.refresh_telemetry(force_sync=False)
                update_state_file()

            if shuffle and (now - last_shuffle_time) >= shuffle_interval:
                last_shuffle_time = now
                other_presets = [p for p in all_presets if p != current_preset]
                current_preset = random.choice(other_presets)
                synth.set_preset(current_preset)
                if not birds:
                    synth.preset['wildlife_prob'] = 0.0
                update_state_file()

            chunk = synth.generate_chunk(to_gen)
            chunk = chunk * np.clip(volume, 0.0, 2.0)
            pcm_data = np.int16(np.clip(chunk * 32767.0, -32768, 32767)).tobytes()

            if wav_file:
                wav_file.writeframes(pcm_data)
            elif raw_stdout:
                sys.stdout.buffer.write(pcm_data)
                sys.stdout.buffer.flush()
            elif aplay_proc:
                try:
                    aplay_proc.stdin.write(pcm_data)
                    aplay_proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    break

            samples_produced += to_gen
    finally:
        close_handles()

def start_background(
    preset='napili',
    volume=1.0,
    duration=None,
    birds=True,
    enable_live=True,
    circadian_mode='auto',
    rain=False,
    rain_intensity=None,
    shuffle=False,
    shuffle_interval=600.0
):
    stop_playback()
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    args = [sys.executable, str(Path(__file__).resolve()), '_worker',
            '--preset', preset,
            '--volume', str(volume),
            '--time', circadian_mode]
    
    if duration:
        args.extend(['--duration', str(duration)])
    if not birds:
        args.append('--no-birds')
    if not enable_live:
        args.append('--no-live')
    if rain:
        args.append('--rain')
    if rain_intensity is not None:
        args.extend(['--rain-intensity', str(rain_intensity)])
    if shuffle:
        args.append('--shuffle')
        args.extend(['--shuffle-interval', str(shuffle_interval)])

    proc = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    telemetry = None
    if enable_live or circadian_mode == 'auto':
        try:
            telemetry = fetch_live_telemetry(force_refresh=False)
        except Exception:
            pass

    p_info = HawaiianOceanSynthesizer.PRESETS.get(preset, {})
    info = {
        'pid': proc.pid,
        'preset': preset,
        'island': p_info.get('island', 'Hawaii'),
        'preset_name': p_info.get('name', 'Custom'),
        'volume': volume,
        'duration_sec': duration,
        'birds': birds,
        'enable_live': enable_live,
        'circadian_mode': circadian_mode,
        'rain': rain or (telemetry and telemetry.get('precipitation_mm', 0) > 0.05),
        'rain_intensity': rain_intensity,
        'shuffle': shuffle,
        'shuffle_interval': shuffle_interval,
        'telemetry': telemetry,
        'started_at': time.time(),
        'started_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    PID_FILE.write_text(str(proc.pid) + '\n')
    INFO_FILE.write_text(json.dumps(info, indent=2) + '\n')
    return proc.pid, info

def show_status(json_output=False):
    pid, info = get_active_process()
    if not pid:
        status = {
            'playing': False,
            'message': 'Ocean soundscape is idle.'
        }
    else:
        uptime = time.time() - info.get('started_at', time.time())
        mins = int(uptime // 60)
        secs = int(uptime % 60)
        telem = info.get('telemetry') or {}
        
        circadian_phase = info.get('circadian_mode', 'auto')
        if circadian_phase == 'auto':
            phase_code, phase_name = determine_circadian_phase()
            circadian_display = f"Auto ({phase_name})"
        else:
            circadian_display = circadian_phase.capitalize()

        status = {
            'playing': True,
            'pid': pid,
            'preset': info.get('preset'),
            'island': info.get('island', 'Hawaii'),
            'preset_name': info.get('preset_name') or HawaiianOceanSynthesizer.PRESETS.get(info.get('preset'), {}).get('name', 'Custom'),
            'volume': info.get('volume', 1.0),
            'duration_sec': info.get('duration_sec'),
            'uptime_sec': round(uptime, 1),
            'uptime_human': f"{mins}m {secs}s",
            'birds': info.get('birds', True),
            'live_telemetry_enabled': info.get('enable_live', True),
            'circadian_mode': info.get('circadian_mode', 'auto'),
            'circadian_display': circadian_display,
            'shuffle': info.get('shuffle', False),
            'shuffle_interval': info.get('shuffle_interval', 600),
            'rain': info.get('rain', False),
            'telemetry': telem,
            'started_at': info.get('started_at_iso')
        }
    
    if json_output:
        print(json.dumps(status, indent=2))
    else:
        if not status['playing']:
            print("🌊 Ocean Soundscape: Idle (not playing)")
        else:
            print("🌊 Hawaiian Ocean Soundscape: Playing")
            print(f"   PID:         {status['pid']}")
            print(f"   Location:    {status['island']} - {status['preset']} ({status['preset_name']})")
            print(f"   Volume:      {int(status['volume'] * 100)}%")
            print(f"   Diurnal:     {status['circadian_display']}")
            print(f"   Shuffle:     {'Enabled (every ' + str(int(status['shuffle_interval']//60)) + 'm)' if status['shuffle'] else 'Off'}")
            print(f"   Rain/Squall: {'Active' if status['rain'] else 'Dry'}")
            print(f"   Wildlife:    {'Enabled' if status['birds'] else 'Disabled'}")
            
            telem = status.get('telemetry', {})
            if telem and status.get('live_telemetry_enabled'):
                wvht = telem.get('wave_height_m', 'N/A')
                period = telem.get('wave_period_s', 'N/A')
                wspd = telem.get('wind_speed_kmh', 'N/A')
                source = telem.get('source', 'Hawaii Telemetry')
                print(f"   Live NOAA:   {wvht}m swell @ {period}s | Wind {wspd} km/h [{source}]")
            
            print(f"   Duration:    {str(status['duration_sec']) + 's' if status['duration_sec'] else 'Continuous / Infinite'}")
            print(f"   Elapsed:     {status['uptime_human']}")

def list_presets():
    print("🌺 Hawaiian Ocean Beach Soundscape Presets:\n")
    islands = {}
    for key, p in HawaiianOceanSynthesizer.PRESETS.items():
        isl = p.get('island', 'Other')
        islands.setdefault(isl, []).append((key, p))

    for isl, presets in islands.items():
        print(f"=== {isl.upper()} ===")
        for key, p in presets:
            print(f"  • {key.ljust(14)} - {p['name']}")
            print(f"    {p['description']}\n")

def main():
    parser = argparse.ArgumentParser(
        description="🌊 Hawaiian Ocean Beach Synthesizer (culture-ocean) - Generative, live telemetry acoustic soundscapes."
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # play
    p_play = subparsers.add_parser('play', help='Play Hawaiian ocean soundscape')
    p_play.add_argument('--preset', choices=list(HawaiianOceanSynthesizer.PRESETS.keys()), default='napili',
                        help='Beach acoustic profile')
    p_play.add_argument('--duration', '-d', type=parse_duration, default=None,
                        help='Playback duration (e.g. 30s, 10m, 1h). Default: continuous infinite')
    p_play.add_argument('--volume', '-v', type=float, default=1.0, help='Volume scaling (0.1 to 2.0)')
    p_play.add_argument('--no-birds', action='store_true', help='Disable procedural coastal wildlife/birds')
    p_play.add_argument('--foreground', '-f', action='store_true', help='Run in foreground instead of background daemon')
    p_play.add_argument('--no-live', action='store_true', help='Disable live NOAA marine & weather telemetry sync')
    p_play.add_argument('--time', choices=['auto', 'dawn', 'day', 'sunset', 'night', 'off'], default='auto',
                        help='Circadian time-of-day phase (default: auto using Hawaii local time HST)')
    p_play.add_argument('--rain', action='store_true', help='Engage tropical rain and squall generator')
    p_play.add_argument('--rain-intensity', type=float, default=None, help='Forced rain intensity (0.0 to 1.0)')
    p_play.add_argument('--shuffle', action='store_true', help='Shuffle mode: wander between random beach locations & settings')
    p_play.add_argument('--shuffle-interval', type=parse_duration, default=600.0,
                        help='Interval for changing location in shuffle mode (default: 10m)')

    # stop
    p_stop = subparsers.add_parser('stop', help='Stop running ocean soundscape')

    # status
    p_status = subparsers.add_parser('status', help='Show ocean soundscape status')
    p_status.add_argument('--json', action='store_true', help='Output in JSON format')

    # presets
    p_presets = subparsers.add_parser('presets', help='List available Hawaiian beach presets')

    # render
    p_render = subparsers.add_parser('render', help='Render ocean audio to a WAV file')
    p_render.add_argument('output', help='Output WAV file path')
    p_render.add_argument('--preset', choices=list(HawaiianOceanSynthesizer.PRESETS.keys()), default='napili')
    p_render.add_argument('--duration', '-d', type=parse_duration, default=30.0, help='Duration to render (default: 30s)')
    p_render.add_argument('--volume', '-v', type=float, default=1.0)
    p_render.add_argument('--no-birds', action='store_true')
    p_render.add_argument('--no-live', action='store_true')
    p_render.add_argument('--time', choices=['auto', 'dawn', 'day', 'sunset', 'night', 'off'], default='auto')
    p_render.add_argument('--rain', action='store_true')
    p_render.add_argument('--rain-intensity', type=float, default=None)

    # stream (stdout)
    p_stream = subparsers.add_parser('stream', help='Stream raw 16-bit 48kHz stereo PCM to stdout')
    p_stream.add_argument('--preset', choices=list(HawaiianOceanSynthesizer.PRESETS.keys()), default='napili')
    p_stream.add_argument('--duration', '-d', type=parse_duration, default=None)
    p_stream.add_argument('--volume', '-v', type=float, default=1.0)
    p_stream.add_argument('--no-birds', action='store_true')
    p_stream.add_argument('--no-live', action='store_true')
    p_stream.add_argument('--time', choices=['auto', 'dawn', 'day', 'sunset', 'night', 'off'], default='auto')
    p_stream.add_argument('--rain', action='store_true')
    p_stream.add_argument('--rain-intensity', type=float, default=None)

    # internal worker
    p_worker = subparsers.add_parser('_worker')
    p_worker.add_argument('--preset', default='napili')
    p_worker.add_argument('--volume', type=float, default=1.0)
    p_worker.add_argument('--duration', type=float, default=None)
    p_worker.add_argument('--no-birds', action='store_true')
    p_worker.add_argument('--no-live', action='store_true')
    p_worker.add_argument('--time', default='auto')
    p_worker.add_argument('--rain', action='store_true')
    p_worker.add_argument('--rain-intensity', type=float, default=None)
    p_worker.add_argument('--shuffle', action='store_true')
    p_worker.add_argument('--shuffle-interval', type=float, default=600.0)

    args = parser.parse_args()

    if args.command == 'presets':
        list_presets()
    elif args.command == 'status':
        show_status(json_output=args.json)
    elif args.command == 'stop':
        ok, msg = stop_playback()
        print(msg)
    elif args.command == 'play':
        enable_live = not args.no_live
        if args.foreground:
            print(f"🌊 Playing Hawaiian ocean soundscape ({args.preset}). Press Ctrl+C to stop...")
            run_audio_stream(
                preset=args.preset,
                volume=args.volume,
                duration=args.duration,
                birds=not args.no_birds,
                enable_live=enable_live,
                circadian_mode=args.time,
                rain=args.rain,
                rain_intensity=args.rain_intensity,
                shuffle=args.shuffle,
                shuffle_interval=args.shuffle_interval
            )
        else:
            pid, info = start_background(
                preset=args.preset,
                volume=args.volume,
                duration=args.duration,
                birds=not args.no_birds,
                enable_live=enable_live,
                circadian_mode=args.time,
                rain=args.rain,
                rain_intensity=args.rain_intensity,
                shuffle=args.shuffle,
                shuffle_interval=args.shuffle_interval
            )
            p_info = HawaiianOceanSynthesizer.PRESETS[args.preset]
            p_name = p_info['name']
            dur_str = f"for {args.duration}s" if args.duration else "continuously"
            shuf_str = " [Shuffle Mode Active]" if args.shuffle else ""
            print(f"🌊 Started Hawaiian ocean soundscape ({args.preset} - {p_name}){shuf_str} {dur_str} in background.")
            print(f"   Volume: {int(args.volume * 100)}% | Live NOAA: {'On' if enable_live else 'Off'} | Diurnal: {args.time} | PID: {pid}")
            print(f"   Run 'culture-ocean stop' or ask me anytime to stop playing.")
    elif args.command == 'render':
        out_path = os.path.abspath(args.output)
        dur = args.duration or 30.0
        print(f"🌊 Rendering {dur}s of {args.preset} beach soundscape to {out_path}...")
        t0 = time.time()
        run_audio_stream(
            preset=args.preset,
            volume=args.volume,
            duration=dur,
            birds=not args.no_birds,
            enable_live=not args.no_live,
            circadian_mode=args.time,
            rain=args.rain,
            rain_intensity=args.rain_intensity,
            output_wav=out_path
        )
        el = time.time() - t0
        print(f"✓ Render complete in {el:.2f}s ({out_path})")
    elif args.command == 'stream':
        run_audio_stream(
            preset=args.preset,
            volume=args.volume,
            duration=args.duration,
            birds=not args.no_birds,
            enable_live=not args.no_live,
            circadian_mode=args.time,
            rain=args.rain,
            rain_intensity=args.rain_intensity,
            raw_stdout=True
        )
    elif args.command == '_worker':
        run_audio_stream(
            preset=args.preset,
            volume=args.volume,
            duration=args.duration,
            birds=not args.no_birds,
            enable_live=not args.no_live,
            circadian_mode=args.time,
            rain=args.rain,
            rain_intensity=args.rain_intensity,
            shuffle=args.shuffle,
            shuffle_interval=args.shuffle_interval
        )

if __name__ == '__main__':
    main()

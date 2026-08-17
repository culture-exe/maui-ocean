#!/usr/bin/env python3
"""
Culture Maui Ocean Beach Synthesizer (culture-ocean)
Generative, on-demand ocean beach acoustic landscape engine modeled after Maui coastlines.
"""

import sys
import os
import time
import json
import signal
import argparse
import subprocess
from pathlib import Path
import numpy as np

# Add local src directory to import path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.synth_engine import MauiOceanSynthesizer, SAMPLE_RATE

STATE_DIR = Path.home() / '.local/state/culture-ocean'
PID_FILE = STATE_DIR / 'ocean.pid'
INFO_FILE = STATE_DIR / 'ocean.json'

def parse_duration(val):
    if not val or val.lower() in ('inf', 'infinite', '0', 'none'):
        return None
    val = val.strip().lower()
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
    
    # Check if process exists and is actually culture-ocean
    try:
        os.kill(pid, 0)
    except OSError:
        # Stale pid
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

def run_audio_stream(preset='napili', volume=1.0, duration=None, birds=True, output_wav=None, raw_stdout=False):
    """Core audio loop for streaming to ALSA or file."""
    synth = MauiOceanSynthesizer(preset_name=preset, sample_rate=SAMPLE_RATE)
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
        # Pipe directly into aplay
        cmd = ['aplay', '-q', '-D', 'default', '-f', 'S16_LE', '-r', str(SAMPLE_RATE), '-c', '2']
        aplay_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def cleanup(sig=None, frame=None):
        nonlocal aplay_proc, wav_file
        if aplay_proc:
            try:
                aplay_proc.stdin.close()
                aplay_proc.terminate()
                aplay_proc.wait(timeout=1.0)
            except Exception:
                try: aplay_proc.kill()
                except Exception: pass
        if wav_file:
            try: wav_file.close()
            except Exception: pass
        try:
            PID_FILE.unlink(missing_ok=True)
            INFO_FILE.unlink(missing_ok=True)
        except Exception: pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            if total_samples and samples_produced >= total_samples:
                break

            to_gen = chunk_size
            if total_samples and (samples_produced + to_gen) > total_samples:
                to_gen = total_samples - samples_produced

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
        cleanup()

def start_background(preset='napili', volume=1.0, duration=None, birds=True):
    # Stop any running ocean first
    stop_playback()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    args = [sys.executable, str(Path(__file__).resolve()), '_worker',
            '--preset', preset,
            '--volume', str(volume)]
    if duration:
        args.extend(['--duration', str(duration)])
    if not birds:
        args.append('--no-birds')

    proc = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    info = {
        'pid': proc.pid,
        'preset': preset,
        'volume': volume,
        'duration_sec': duration,
        'birds': birds,
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
        status = {
            'playing': True,
            'pid': pid,
            'preset': info.get('preset'),
            'preset_name': MauiOceanSynthesizer.PRESETS.get(info.get('preset'), {}).get('name', 'Custom'),
            'volume': info.get('volume', 1.0),
            'duration_sec': info.get('duration_sec'),
            'uptime_sec': round(uptime, 1),
            'uptime_human': f"{mins}m {secs}s",
            'birds': info.get('birds', True),
            'started_at': info.get('started_at_iso')
        }
    
    if json_output:
        print(json.dumps(status, indent=2))
    else:
        if not status['playing']:
            print("🌊 Ocean Soundscape: Idle (not playing)")
        else:
            print("🌊 Ocean Soundscape: Playing")
            print(f"   PID:         {status['pid']}")
            print(f"   Preset:      {status['preset']} ({status['preset_name']})")
            print(f"   Volume:      {int(status['volume'] * 100)}%")
            print(f"   Birds:       {'Enabled (Kōlea plover)' if status['birds'] else 'Disabled'}")
            print(f"   Duration:    {str(status['duration_sec']) + 's' if status['duration_sec'] else 'Continuous / Infinite'}")
            print(f"   Elapsed:     {status['uptime_human']}")

def list_presets():
    print("🌺 Maui Ocean Beach Soundscape Presets:\n")
    for key, p in MauiOceanSynthesizer.PRESETS.items():
        print(f"  • {key.ljust(12)} - {p['name']}")
        print(f"    {p['description']}\n")

def main():
    parser = argparse.ArgumentParser(
        description="🌊 Culture Maui Ocean Beach Synthesizer - Generative, on-demand acoustic soundscapes."
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # play
    p_play = subparsers.add_parser('play', help='Play Maui ocean soundscape')
    p_play.add_argument('--preset', choices=list(MauiOceanSynthesizer.PRESETS.keys()), default='napili',
                        help='Beach acoustic profile (napili, makena, northshore, keawakapu)')
    p_play.add_argument('--duration', '-d', type=parse_duration, default=None,
                        help='Playback duration (e.g. 30s, 10m, 1h). Default: continuous infinite')
    p_play.add_argument('--volume', '-v', type=float, default=1.0, help='Volume scaling (0.1 to 2.0)')
    p_play.add_argument('--no-birds', action='store_true', help='Disable procedural Hawaiian coastal birds')
    p_play.add_argument('--foreground', '-f', action='store_true', help='Run in foreground instead of background daemon')

    # stop
    p_stop = subparsers.add_parser('stop', help='Stop running ocean soundscape')

    # status
    p_status = subparsers.add_parser('status', help='Show ocean soundscape status')
    p_status.add_argument('--json', action='store_true', help='Output in JSON format')

    # presets
    p_presets = subparsers.add_parser('presets', help='List available Maui beach presets')

    # render
    p_render = subparsers.add_parser('render', help='Render ocean audio to a WAV file')
    p_render.add_argument('output', help='Output WAV file path')
    p_render.add_argument('--preset', choices=list(MauiOceanSynthesizer.PRESETS.keys()), default='napili')
    p_render.add_argument('--duration', '-d', type=parse_duration, default=30.0, help='Duration to render (default: 30s)')
    p_render.add_argument('--volume', '-v', type=float, default=1.0)
    p_render.add_argument('--no-birds', action='store_true')

    # stream (stdout)
    p_stream = subparsers.add_parser('stream', help='Stream raw 16-bit 48kHz stereo PCM to stdout')
    p_stream.add_argument('--preset', choices=list(MauiOceanSynthesizer.PRESETS.keys()), default='napili')
    p_stream.add_argument('--duration', '-d', type=parse_duration, default=None)
    p_stream.add_argument('--volume', '-v', type=float, default=1.0)
    p_stream.add_argument('--no-birds', action='store_true')

    # internal worker
    p_worker = subparsers.add_parser('_worker')
    p_worker.add_argument('--preset', default='napili')
    p_worker.add_argument('--volume', type=float, default=1.0)
    p_worker.add_argument('--duration', type=float, default=None)
    p_worker.add_argument('--no-birds', action='store_true')

    args = parser.parse_args()

    if args.command == 'presets':
        list_presets()
    elif args.command == 'status':
        show_status(json_output=args.json)
    elif args.command == 'stop':
        ok, msg = stop_playback()
        print(msg)
    elif args.command == 'play':
        if args.foreground:
            print(f"🌊 Playing Maui ocean soundscape ({args.preset}). Press Ctrl+C to stop...")
            run_audio_stream(
                preset=args.preset,
                volume=args.volume,
                duration=args.duration,
                birds=not args.no_birds
            )
        else:
            pid, info = start_background(
                preset=args.preset,
                volume=args.volume,
                duration=args.duration,
                birds=not args.no_birds
            )
            p_name = MauiOceanSynthesizer.PRESETS[args.preset]['name']
            dur_str = f"for {args.duration}s" if args.duration else "continuously"
            print(f"🌊 Started Maui ocean soundscape ({args.preset} - {p_name}) {dur_str} in background.")
            print(f"   Volume: {int(args.volume * 100)}% | PID: {pid}")
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
            raw_stdout=True
        )
    elif args.command == '_worker':
        run_audio_stream(
            preset=args.preset,
            volume=args.volume,
            duration=args.duration,
            birds=not args.no_birds
        )

if __name__ == '__main__':
    main()

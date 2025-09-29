# encoder.py
import os
import time
import subprocess
import sys
import tempfile

import ffmpeg

from .helpers import *
from . import config

def encodeFile(input_file, outfile, v_bps, a_bps, duration,
               passlogfile,
               target_container,
               target_pix_fmt,
               threads,
               cpu_used=None,
               test_only=False,
               test_seconds=config.SAMPLE_SECONDS,
               video_codec=config.VIDEO_CODEC,
               audio_codec=config.AUDIO_CODEC
               ):
    """
    Encode a file (or test encode if test_only=True).
    Returns (file_size_bytes, used_video_bps, used_audio_bps)
    """

    if cpu_used is None:
        cpu_used = config.VIDEO_CPU_USED

    # ---- get detailed source parameters ----
    source_info = getSourceParams(input_file)

    if not source_info:
        raise ValueError("Failed to retrieve source parameters.")

    # ---- unpack format-level metadata ----
    src_format_name        = source_info.get('format_name')
    src_format_long_name   = source_info.get('format_long_name')
    src_duration           = source_info.get('duration_sec')
    src_file_size_bytes    = source_info.get('size_bytes')
    src_container_bitrate  = source_info.get('bitrate_bps')

    if not src_duration or src_duration <= 0:
        raise ValueError("Source duration is invalid.")
    
    if v_bps is None or a_bps is None:
        # Use global target file size from config here
        target_total_bps = (config.TARGET_FILESIZE_BYTES * 8.0) / src_duration
        v_bps, a_bps = computeBitrates(target_total_bps)


    # ---- unpack video stream metadata ----
    src_video_info         = source_info.get('video', {})
    src_video_bitrate  = src_video_info.get('bitrate_bps')
    src_w              = src_video_info.get('width')
    src_h              = src_video_info.get('height')
    src_video_codec        = src_video_info.get('codec_name')
    src_video_profile      = src_video_info.get('profile')
    src_pix_fmt            = src_video_info.get('pix_fmt')
    src_avg_frame_rate     = src_video_info.get('avg_frame_rate')
    src_r_frame_rate       = src_video_info.get('r_frame_rate')
    src_nb_frames          = src_video_info.get('nb_frames')
    src_aspect_ratio       = src_video_info.get('aspect_ratio')
    src_video_tags         = src_video_info.get('tags', {})

    # ---- unpack audio stream metadata ----
    src_audio_info         = source_info.get('audio', {})
    src_audio_codec        = src_audio_info.get('codec_name')
    src_audio_sample_rate  = src_audio_info.get('sample_rate')
    src_audio_channels     = src_audio_info.get('channels')
    src_audio_bitrate      = src_audio_info.get('bit_rate')
    src_audio_duration     = src_audio_info.get('duration_sec')
    src_audio_frames       = src_audio_info.get('nb_frames')
    src_audio_tags         = src_audio_info.get('tags', {})

    # Suggested settings
    audio_channels, audio_bitrate_str, fps_adapt, default_res, video_bitrate_str, audio_samplerate_str, audio_cutoff_str = adaptSettings(
        v_bps, a_bps, src_res=f"{src_w}x{src_h}" if src_w and src_h else None, src_fps=src_avg_frame_rate
        )

    # ---- prepare values and source references for bitrate capping ----
    values_to_cap = {
        'v_bps': v_bps,
        'a_bps': a_bps,
        'fps': int(fps_adapt),
        'res_w': int(default_res.split('x')[0]),
        'res_h': int(default_res.split('x')[1]),
        'audio_channels': int(audio_channels),
        'audio_samplerate': int(audio_samplerate_str),
    }

    reference_values = {
        'v_bps': src_video_bitrate,
        'a_bps': src_audio_bitrate,
        'fps': parse_framerate(src_avg_frame_rate) if src_avg_frame_rate else None,
        'res_w': src_w,
        'res_h': src_h,
        'audio_channels': src_audio_channels,
        'audio_samplerate': src_audio_sample_rate,
    }

    capped = capDictToOriginal(values_to_cap, reference_values)

    # Assign back
    v_bps = capped['v_bps']
    a_bps = capped['a_bps']
    fps_adapt = capped['fps']
    forced_resolution = f"{int(capped['res_w'])}x{int(capped['res_h'])}"
    audio_channels_local = str(capped['audio_channels'])
    audio_samplerate_local = capped['audio_samplerate']

    # -----------------------------
    # Build value dicts for capping
    # -----------------------------
    values = {
        'v_bps': v_bps,
        'a_bps': a_bps,
        'fps': int(fps_adapt),
        'frame_duration': config.AUDIO_FRAME_DURATION,
        'audio_samplerate': int(audio_samplerate_str),
        'audio_cutoff': int(audio_cutoff_str),
        'res_w': int(default_res.split("x")[0]),
        'res_h': int(default_res.split("x")[1]),
        'audio_channels': int(audio_channels),
    }

    reference = {
        'v_bps': src_video_bitrate,
        'a_bps': src_audio_bitrate,
        'fps': getattr(config, 'MAX_FPS', None),
        'frame_duration': getattr(config, 'MAX_FRAME_DURATION', None),
        'audio_samplerate': src_audio_sample_rate,
        'audio_cutoff': (src_audio_sample_rate / 2),
        'res_w': src_w,
        'res_h': src_h,
        'audio_channels': 2,       # cap stereo
    }

    # Apply caps
    capped = capDictToOriginal(values, reference)

    # Assign back
    v_bps = capped['v_bps']
    a_bps = capped['a_bps']
    fps_adapt = capped['fps']
    frame_duration = capped['frame_duration']
    audio_samplerate_local = capped['audio_samplerate']
    if config.AUDIO_CODEC == 'libopus':
        adjusted_rate = round_nearest_opus_samplerate(audio_samplerate_local)
        if adjusted_rate != audio_samplerate_local:
            print(f"[WARN] libopus does not support {audio_samplerate_local} Hz. Using nearest valid rate: {adjusted_rate} Hz.")
        audio_samplerate_local = adjusted_rate
    audio_cutoff_local = capped['audio_cutoff']
    forced_resolution = f"{int(capped['res_w'])}x{int(capped['res_h'])}"
    audio_channels_local = str(capped['audio_channels'])

    v_bitrate_str = formatBPSToFfmpeg(v_bps)
    a_bitrate_str = formatBPSToFfmpeg(a_bps)

    print(f"[DEBUG] encodeFile -> v={v_bitrate_str}, a={a_bitrate_str}, res={forced_resolution}, fps={fps_adapt}, channels={audio_channels_local}")

    # -----------------------------
    # Video args
    # -----------------------------
    video_args = {
        'vcodec': video_codec,
        'b:v': v_bitrate_str,
        'g': min(int(fps_adapt * 10), 300),
        'qmin': config.VIDEO_QMIN,
        'qmax': config.VIDEO_QMAX,
        'r': fps_adapt,
        's': forced_resolution,
        'undershoot-pct': config.VIDEO_UNDERSHOOT_PCT,
        'overshoot-pct': config.VIDEO_OVERSHOOT_PCT,
        'lag-in-frames': config.VIDEO_LAG_IN_FRAMES,
        'tune': config.VIDEO_TUNE,
        'quality': config.VIDEO_QUALITY,
        'cpu-used': cpu_used,
        'auto-alt-ref': config.VIDEO_AUTO_ALT_REF,
        'arnr-maxframes': config.VIDEO_ARNR_MAXFRAMES,
        'arnr-strength': config.VIDEO_ARNR_STRENGTH,
        'aq-mode': config.VIDEO_AQ_MODE,
        'row-mt': config.VIDEO_ROW_MT,
        'tile-columns': config.VIDEO_TILE_COLUMNS,
        'tile-rows': config.VIDEO_TILE_ROWS,
        'enable-tpl': config.VIDEO_ENABLE_TPL,
        'profile:v': config.VIDEO_PROFILE,
    }

    audio_args = {
        'acodec': audio_codec,
        'b:a': a_bitrate_str,
        'ar': str(audio_samplerate_local),
        'ac': audio_channels_local,
        'vbr': config.AUDIO_VBR,
        'application': config.AUDIO_APPLICATION,
        'cutoff': str(audio_cutoff_local),
        'frame_duration': frame_duration,
    }

    target_args = {
        'threads': threads,
        'pix_fmt': target_pix_fmt,
    }

    # -----------------------------
    # Test encode
    # -----------------------------
    if test_only:
        fd, tmp = tempfile.mkstemp(suffix="." + target_container)
        os.close(fd)
        target_args['t'] = test_seconds
        try:
            (
                ffmpeg
                .input(input_file)
                .output(tmp, format=target_container, **video_args, **audio_args, **target_args)
                .overwrite_output()
                .run(quiet=True)
            )
            size = os.path.getsize(tmp)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return size, v_bps, a_bps

    # -----------------------------
    # Full encode (two-pass)
    # -----------------------------
    fd, firstpass_file = tempfile.mkstemp(suffix=".webm")
    os.close(fd)
    try:
        first_pass_cmd = (
            ffmpeg.input(input_file)
                  .output(firstpass_file, **video_args, **target_args,
                          **{'pass': 1, 'passlogfile': passlogfile, 'an': None})
                  .global_args('-progress', 'pipe:2')
                  .overwrite_output()
                  .compile()
        )

        second_pass_cmd = (
            ffmpeg.input(input_file)
                  .output(outfile, **video_args, **audio_args, **target_args,
                          **{'pass': 2, 'passlogfile': passlogfile})
                  .global_args('-progress', 'pipe:2')
                  .overwrite_output()
                  .compile()
        )

        def runWithProgress(cmd, pass_label, duration_sec):
            print(f"[{pass_label}] Encoding started...")
            start_time = time.time()
            duration_ms = max(1, int(duration_sec * 1000))
            last_update = 0.0

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            while True:
                line = proc.stderr.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue
                line = line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        out_time_ms = int(line.split("=", 1)[1])
                        percent = min(out_time_ms / duration_ms * 100.0, 100.0)
                        now = time.time()
                        if now - last_update >= 0.5 and percent > 0:
                            elapsed_time = now - start_time
                            eta = elapsed_time * (100.0 - percent) / percent
                            eta_hr, rem = divmod(int(eta), 3600)
                            eta_min, eta_sec = divmod(rem, 60)
                            sys.stdout.write(f"\r[{pass_label}] {percent:.1f}% (ETA {eta_hr:02d}:{eta_min:02d}:{eta_sec:02d})")
                            sys.stdout.flush()
                            last_update = now
                    except Exception:
                        continue
            proc.wait()
            sys.stdout.write("\n")
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg {pass_label} failed (returncode {proc.returncode})")
            return proc.returncode

        runWithProgress(first_pass_cmd, "PASS 1", duration)
        runWithProgress(second_pass_cmd, "PASS 2", duration)

    finally:
        if os.path.exists(firstpass_file):
            os.remove(firstpass_file)

    return os.path.getsize(outfile), v_bps, a_bps

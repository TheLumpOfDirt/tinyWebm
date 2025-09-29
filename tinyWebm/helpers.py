# helpers.py
import math

import ffmpeg

def capToOriginal(value, original):
    """
    Cap value to not exceed original reference.
    Works with int, float, or comparable types.
    If original is None, return value unmodified.
    """
    if original is None or value is None:
        return value

    # Convert strings like "30/1" (fps) to float if possible
    if isinstance(value, str) and '/' in value:
        try:
            num, den = value.split('/')
            value = float(num) / float(den)
        except Exception:
            pass

    if isinstance(original, str) and '/' in original:
        try:
            num, den = original.split('/')
            original = float(num) / float(den)
        except Exception:
            pass

    try:
        return min(float(value), float(original))
    except Exception:
        # fallback: if can't convert to float, just compare as is
        return min(value, original)


def capDictToOriginal(values: dict, reference: dict) -> dict:
    """
    Cap each value in `values` to the corresponding value in `reference`.
    If reference value is None or missing, no capping for that key.
    Handles conversion of strings representing fractions.
    """
    capped = {}
    for k, v in values.items():
        ref = reference.get(k)
        if ref is not None and v is not None:
            capped[k] = capToOriginal(v, ref)
        else:
            capped[k] = v
    return capped

def getSourceParams(path):
    """
    Return detailed information about the first video and audio streams, and format-level metadata.
    Returns a dictionary with all available parameters, or None if probing fails.
    """
    try:
        probe = ffmpeg.probe(path)
        format_info = probe.get('format', {})
        streams = probe.get('streams', [])

        # Video stream (first one)
        video_stream = next((s for s in streams if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in streams if s['codec_type'] == 'audio'), None)

        info = {
            'format_name': format_info.get('format_name'),
            'format_long_name': format_info.get('format_long_name'),
            'duration_sec': float(format_info.get('duration', 0)),
            'size_bytes': int(format_info.get('size', 0)),
            'bitrate_bps': int(format_info.get('bit_rate', 0)),

            'video': {},
            'audio': {}
        }

        if video_stream:
            info['video'] = {
                'codec_name': video_stream.get('codec_name'),
                'codec_long_name': video_stream.get('codec_long_name'),
                'profile': video_stream.get('profile'),
                'bitrate_bps': int(video_stream.get('bit_rate', 0)) or None,
                'width': int(video_stream.get('width', 0)) or None,
                'height': int(video_stream.get('height', 0)) or None,
                'pix_fmt': video_stream.get('pix_fmt'),
                'avg_frame_rate': video_stream.get('avg_frame_rate'),
                'r_frame_rate': video_stream.get('r_frame_rate'),
                'duration_ts': video_stream.get('duration_ts'),
                'duration_sec': float(video_stream.get('duration', 0)) if video_stream.get('duration') else None,
                'nb_frames': int(video_stream.get('nb_frames', 0)) if video_stream.get('nb_frames') else None,
                'aspect_ratio': video_stream.get('display_aspect_ratio'),
                'tags': video_stream.get('tags', {})
            }

        if audio_stream:
            info['audio'] = {
                'codec_name': audio_stream.get('codec_name'),
                'codec_long_name': audio_stream.get('codec_long_name'),
                'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream.get('sample_rate') else None,
                'channels': int(audio_stream.get('channels', 0)) if audio_stream.get('channels') else None,
                'bitrate_bps': int(audio_stream.get('bit_rate', 0)) if audio_stream.get('bit_rate') else None,
                'duration_sec': float(audio_stream.get('duration', 0)) if audio_stream.get('duration') else None,
                'nb_frames': int(audio_stream.get('nb_frames', 0)) if audio_stream.get('nb_frames') else None,
                'tags': audio_stream.get('tags', {})
            }

        return info

    except Exception as e:
        print(f"[WARN] Could not probe source video params: {e}")
        return None

def computeBitrates(
    total_bps,
    audio_min_bitrate=6_000,
    audio_max_bitrate=256_000,
):
    """
    Allocate total_bps between audio and video using a sigmoid curve for audio.
    
    - Audio gets between audio_min_bitrate and audio_max_bitrate.
    - Audio ramps up early and levels off.
    - Video gets whatever remains (no minimum).
    """

    total_bps = max(1, int(total_bps))

    # ---- AUDIO CURVE ----
    # Smooth sigmoid: centered around 500 kbps, spreads over ~400 kbps
    audio_scale = sigmoid((total_bps - 500_000) / 200_000)
    audio_bitrate = int(audio_min_bitrate + (audio_max_bitrate - audio_min_bitrate) * audio_scale)

    # Clamp to total budget
    audio_bitrate = min(audio_bitrate, total_bps - 1)

    # ---- VIDEO ----
    video_bitrate = total_bps - audio_bitrate

    return int(video_bitrate), int(audio_bitrate)


def computeAudioEncodingParams(audio_bitrate_bps):
    """
    Decide practical Opus samplerate (Hz) and lowpass cutoff (Hz) from audio bitrate.

    Rules (practical):
      - < 24 kbps : 16 kHz
      - 24 - 48 kbps : 24 kHz
      - 48 - 96 kbps : 48 kHz (fullband)
      - >= 96 kbps : 48 kHz (fullband)
    Cutoff set a bit below Nyquist to allow encoder headroom, capped at 20 kHz.
    Returns (samplerate_int, cutoff_int).
    """
    br_k = float(audio_bitrate_bps) / 1000.0

    if br_k < 24.0:
        sr = 16000
    elif br_k < 48.0:
        sr = 24000
    else:
        sr = 48000

    cutoff = min(int(sr / 2 * 0.95), 20000)  # keep a bit below Nyquist
    return int(sr), int(cutoff)

def adaptSettings(video_bitrate_bps, audio_bitrate_bps, src_res=None, src_fps=None):
    """
    Return adapted encoding settings and bitrate strings for ffmpeg.

    Behavior:
      - Only shrink resolution/fps if bitrate requires it.
      - Never upscale: if source is smaller, keep source resolution/fps.
      - Audio samplerate and cutoff follow computeAudioEncodingParams.

    Returns:
      (audio_channels, audio_bitrate_str, fps_int, resolution_str,
       video_bitrate_str, audio_samplerate_str, audio_cutoff_str)
    """
    # audio channel decision
    audio_channels = "2" if audio_bitrate_bps >= 64_000 else "1"
    audio_bitrate_str = f"{int(round(audio_bitrate_bps/1000.0))}k"

    # audio samplerate/cutoff
    audio_samplerate_int, audio_cutoff_int = computeAudioEncodingParams(audio_bitrate_bps)
    audio_samplerate_str = str(audio_samplerate_int)
    audio_cutoff_str = str(audio_cutoff_int)

    # video resolution / fps thresholds (practical tiers)
    if video_bitrate_bps >= 3_500_000:
        target_res = "1920x1080"
        target_fps = 30
    elif video_bitrate_bps >= 1_500_000:
        target_res = "1280x720"
        target_fps = 30
    elif video_bitrate_bps >= 800_000:
        target_res = "854x480"
        target_fps = 24
    elif video_bitrate_bps >= 400_000:
        target_res = "640x360"
        target_fps = 24
    elif video_bitrate_bps >= 200_000:
        target_res = "426x240"
        target_fps = 15
    elif video_bitrate_bps >= 100_000:
        target_res = "256x144"
        target_fps = 12
    else:
        target_res = "128x72"
        target_fps = 6

    # Determine final resolution: only shrink if bitrate requires it
    if src_res:
        try:
            src_w, src_h = map(int, src_res.split("x"))
            tr_w, tr_h = map(int, target_res.split("x"))
            # shrink only if target < source
            final_w = min(tr_w, src_w)
            final_h = min(tr_h, src_h)
            final_res = f"{int(final_w)}x{int(final_h)}"
        except Exception:
            final_res = target_res
    else:
        final_res = target_res

    # Determine final FPS: only shrink if target < source
    if src_fps is not None:
        try:
            final_fps = min(int(target_fps), int(src_fps))
        except Exception:
            final_fps = int(target_fps)
    else:
        final_fps = int(target_fps)

    video_bitrate_str = f"{int(round(video_bitrate_bps/1000.0))}k"

    return audio_channels, audio_bitrate_str, final_fps, final_res, video_bitrate_str, audio_samplerate_str, audio_cutoff_str

def formatBPSToFfmpeg(v_bps):
    """Format integer bits-per-second to ffmpeg 'k' string (rounded kbps)."""
    return f"{int(round(v_bps/1000.0))}k"

def parse_framerate(fps_str):
    try:
        if '/' in fps_str:
            num, denom = fps_str.split('/')
            return float(num) / float(denom)
        else:
            return float(fps_str)
    except Exception:
        return None
   
def round_nearest_opus_samplerate(rate):
    valid_rates = [8000, 12000, 16000, 24000, 48000]
    return min(valid_rates, key=lambda x: abs(x - rate))

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

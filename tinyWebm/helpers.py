# helpers.py
import math

def capToOriginal(value, original):
    """
    Cap value to not exceed original reference.
    Works with int, float, or comparable types.
    If original is None, return value unmodified.
    """
    if original is None:
        return value
    return min(value, original)

def capDictToOriginal(values: dict, reference: dict) -> dict:
    """
    Cap each value in `values` to the corresponding value in `reference`,
    but never shrink values that are already lower than the reference.
    If a reference value is None, it is ignored (no cap applied).
    """
    capped = {}
    for k, v in values.items():
        ref = reference.get(k)
        if ref is not None and v is not None:
            # Only cap if value exceeds reference
            capped[k] = min(v, ref)
        else:
            # No reference or value, keep original
            capped[k] = v
    return capped

import math

def computeBitrates(total_bps, audio_min_bitrate=6_000, audio_max_bitrate=256_000, max_video_audio_ratio=10.0):
    """
    Split total_bps into (video_bps, audio_bps) using a smooth logarithmic curve.
    - Low bitrate: audio dominates
    - High bitrate: video dominates up to max_video_audio_ratio
    """
    total_bps = max(1, int(total_bps))

    # Calculate a smooth fraction for audio based on total_bps
    # log scale: log(total_bps + 1) / log(max_total + 1)
    # Adjust max_total for normalization (~5 Mbps)
    max_total = 5_000_000
    fraction = max(0.2, min(0.8, 0.66 - 0.46 * math.log10(total_bps + 1) / math.log10(max_total + 1)))

    audio_target = int(total_bps * fraction)
    audio_bitrate = max(audio_min_bitrate, min(audio_target, audio_max_bitrate))
    audio_bitrate = min(audio_bitrate, total_bps - 1)  # ensure video >= 1

    video_bitrate = total_bps - audio_bitrate

    # enforce max ratio
    if video_bitrate > audio_bitrate * max_video_audio_ratio:
        video_bitrate = int(audio_bitrate * max_video_audio_ratio)
        audio_bitrate = total_bps - video_bitrate
        audio_bitrate = max(audio_min_bitrate, min(audio_bitrate, audio_max_bitrate))

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
            final_res = f"{final_w}x{final_h}"
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

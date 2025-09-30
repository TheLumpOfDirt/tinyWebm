# __main__.py
import os
import sys
import time

import psutil

from . import config
from .helpers import computeBitrates, capDictToOriginal, getSourceParams
from .encoder import encodeFile

# ---- argument parsing ----
if not len(sys.argv) == 3:
    print("Usage: python -m tinywebm [input.*] [output.webm]")
    sys.exit(2)

input_file = str(sys.argv[1])
output_file = str(sys.argv[2])

# derive threads
threads = min(psutil.cpu_count() or 1, 8)

# config variables
passlogfile = config.PASSLOGFILE
target_filesize_bytes = config.TARGET_FILESIZE_BYTES
target_container = config.TARGET_CONTAINER
target_pix_format = config.TARGET_PIX_FORMAT
max_passes = config.MAX_PASSES

def iterativeEncode(input_file, output_file, duration, target_size_bytes,
                    passlogfile, target_container, target_pix_fmt, threads,
                    init_v_bps, init_a_bps, max_passes=5, test_only=False):
    """Iteratively encode (sample or full) until filesize converges to target."""

    video_bitrate_bps, audio_bitrate_bps = init_v_bps, init_a_bps
    passes_done = 0
    total_start = time.time()

    last_size = None
    last_v_bps = None
    last_a_bps = None

    while passes_done < max_passes:
        size_bytes, video_bitrate_bps, audio_bitrate_bps = encodeFile(
            input_file,
            output_file,
            video_bitrate_bps,
            audio_bitrate_bps,
            duration,
            passlogfile,
            target_container,
            target_pix_fmt,
            threads,
            cpu_used=(5 if test_only else config.VIDEO_CPU_USED),
            test_only=test_only,
            test_seconds=(config.SAMPLE_SECONDS if test_only else None)
        )
        passes_done += 1

        # Calculate error ratio
        error_ratio = size_bytes / target_size_bytes
        if abs(1 - error_ratio) < 0.02:  # within 2% of target
            if size_bytes < target_size_bytes:
                break


        # Smooth correction to avoid oscillation
        if size_bytes > target_size_bytes:
            alpha = 0.75
        else:
            alpha = 0.5
        correction = alpha * ((1 / error_ratio) - 1)

        # Optional: clamp correction to avoid wild swings
        max_correction = 0.2
        correction = max(min(correction, max_correction), -max_correction)

        # Apply correction
        total_bps = video_bitrate_bps + audio_bitrate_bps
        corrected_total_bps = total_bps * (1 + correction)

        # Recalculate bitrates
        video_bitrate_bps, audio_bitrate_bps = computeBitrates(corrected_total_bps, src_duration)

        # ---- cap again ----
        capped = capDictToOriginal({'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps},
                                   {'v_bps': src_video_bitrate, 'a_bps': src_audio_bitrate})
        video_bitrate_bps, audio_bitrate_bps = capped['v_bps'], capped['a_bps']

        # prevent stopping too early: require meaningful change
        if (last_v_bps is not None and abs(video_bitrate_bps - last_v_bps) < 500
                and abs(audio_bitrate_bps - last_a_bps) < 500
                and last_size is not None and abs(size_bytes - last_size) < 1024 * 50
                and size_bytes < target_size_bytes):
            print(f"[INFO] No significant change detected, stopping retries early after {passes_done} passes")
            break

        elapsed_total = time.time() - total_start
        passes_remaining = max_passes - passes_done
        eta_total_sec = (elapsed_total / passes_done) * passes_remaining if passes_done > 0 else 0
        eta_hr, rem = divmod(int(eta_total_sec), 3600)
        eta_min, eta_sec = divmod(rem, 60)

        print(f"[ADJUST {passes_done}/{max_passes}] Size={size_bytes/1024/1024:.2f} MiB "
              f"(error_ratio {error_ratio:.3f}) -> trying {video_bitrate_bps/1000:.1f}k/"
              f"{audio_bitrate_bps/1000:.1f}k "
              f"(Overall ETA {eta_hr:02d}:{eta_min:02d}:{eta_sec:02d})")

        last_v_bps, last_a_bps, last_size = video_bitrate_bps, audio_bitrate_bps, size_bytes

    return size_bytes, video_bitrate_bps, audio_bitrate_bps


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

# fix missing audio bitrate if applicable
if src_audio_bitrate is None and src_container_bitrate is not None and src_video_bitrate is not None:
    src_audio_bitrate = max(src_container_bitrate - src_video_bitrate, 0)


# ---- compute target bitrates ----
target_total_bps = (target_filesize_bytes * 8.0) / src_duration
video_bitrate_bps, audio_bitrate_bps = computeBitrates(target_total_bps, src_duration)

# ---- prepare values and source references for bitrate capping ----
values = {
    'v_bps': video_bitrate_bps,
    'a_bps': audio_bitrate_bps,
}

reference = {
    'v_bps': src_video_bitrate,
    'a_bps': src_audio_bitrate,
}

# ---- apply capping logic ----
capped = capDictToOriginal(values, reference)

video_bitrate_bps = capped['v_bps']
audio_bitrate_bps = capped['a_bps']

# ---- iterative test encode ----
if config.SAMPLE_SECONDS < src_duration:
    test_target_size = target_filesize_bytes * (config.SAMPLE_SECONDS / src_duration)
    _, video_bitrate_bps, audio_bitrate_bps = iterativeEncode(
        input_file, os.path.join("/tmp", "tinywebm_test.webm"),
        duration=config.SAMPLE_SECONDS,
        target_size_bytes=test_target_size,
        passlogfile=passlogfile,
        target_container=target_container,
        target_pix_fmt=target_pix_format,
        threads=threads,
        init_v_bps=video_bitrate_bps,
        init_a_bps=audio_bitrate_bps,
        max_passes=max_passes,
        test_only=True
    )

    print(f"[DEBUG] Duration={src_duration:.2f}s, Refined Video={video_bitrate_bps/1000:.1f}k, "
          f"Audio={audio_bitrate_bps/1000:.1f}k")
else:
    print(f"[INFO] Video test encode skipped;"
          f" test sample ({config.SAMPLE_SECONDS} seconds) is more than"
          f" video length ({src_duration} seconds)")

# ---- final full encode ----
final_size_bytes, video_bitrate_bps, audio_bitrate_bps = iterativeEncode(
    input_file, output_file,
    duration=src_duration,
    target_size_bytes=target_filesize_bytes,
    passlogfile=passlogfile,
    target_container=target_container,
    target_pix_fmt=target_pix_format,
    threads=threads,
    init_v_bps=video_bitrate_bps,
    init_a_bps=audio_bitrate_bps,
    max_passes=max_passes,
    test_only=False
)

# ---- final report ----
print(f"[DONE] Final size {final_size_bytes/1024/1024:.2f} MiB "
      f"(target {target_filesize_bytes/1024/1024:.2f} MiB)")
print(f"[RESULT] Video={int(video_bitrate_bps/1000)}k, Audio={int(audio_bitrate_bps/1000)}k, "
      f"Size={final_size_bytes/1024/1024:.2f} MiB")
print(output_file)

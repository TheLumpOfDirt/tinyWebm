# __main__.py
import os
import sys
import time

import ffmpeg
import psutil

from . import config
from .helpers import computeBitrates, capDictToOriginal
from .encoder import encodeFile, getSourceVideoParams

# ---- argument parsing ----
if len(sys.argv) < 3:
    print("Usage: python __main__.py <input> <output>")
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

# ---- probe input for duration and source params ----
probe = ffmpeg.probe(input_file)
duration = float(probe["format"]["duration"])
src_bitrate, src_w, src_h = getSourceVideoParams(input_file)


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

        error_ratio = size_bytes / target_size_bytes
        if abs(1 - error_ratio) < 0.02:  # within 2% of target
            break

        # smooth correction to avoid oscillation
        alpha = 0.5
        corrected_total_bps = (video_bitrate_bps + audio_bitrate_bps) * (1 + alpha * (1/error_ratio - 1))
        video_bitrate_bps, audio_bitrate_bps = computeBitrates(corrected_total_bps)

        # ---- cap again ----
        capped = capDictToOriginal({'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps},
                                   {'v_bps': src_bitrate, 'a_bps': None})
        video_bitrate_bps, audio_bitrate_bps = capped['v_bps'], capped['a_bps']

        # prevent stopping too early: require meaningful change
        if (last_v_bps is not None and abs(video_bitrate_bps - last_v_bps) < 500
                and abs(audio_bitrate_bps - last_a_bps) < 500
                and last_size is not None and abs(size_bytes - last_size) < 1024 * 50):
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


# ---- initial average total bitrate ----
target_total_bps = (target_filesize_bytes * 8.0) / duration
video_bitrate_bps, audio_bitrate_bps = computeBitrates(target_total_bps)

# ---- cap bitrates to source before test encode ----
values = {'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps}
reference = {'v_bps': src_bitrate, 'a_bps': None}
capped = capDictToOriginal(values, reference)
video_bitrate_bps = capped['v_bps']
audio_bitrate_bps = capped['a_bps']

# ---- iterative test encode ----
test_target_size = target_filesize_bytes * (config.SAMPLE_SECONDS / duration)
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

print(f"[DEBUG] Duration={duration:.2f}s, Refined Video={video_bitrate_bps/1000:.1f}k, "
      f"Audio={audio_bitrate_bps/1000:.1f}k")

# ---- final full encode ----
final_size_bytes, video_bitrate_bps, audio_bitrate_bps = iterativeEncode(
    input_file, output_file,
    duration=duration,
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

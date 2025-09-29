# __main__.py
import sys
import time
import os

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

# ---- initial average total bitrate ----
target_total_bps = (target_filesize_bytes * 8.0) / duration
video_bitrate_bps, audio_bitrate_bps = computeBitrates(target_total_bps)

# ---- cap bitrates to source before test encode ----
values = {'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps}
reference = {'v_bps': src_bitrate, 'a_bps': None}
capped = capDictToOriginal(values, reference)
video_bitrate_bps = capped['v_bps']
audio_bitrate_bps = capped['a_bps']

# ---- test encode to adjust bitrates ----
sample_size_bytes, _, _ = encodeFile(
    input_file,
    outfile=os.path.join("/tmp", "tinywebm_test.webm"),
    v_bps=video_bitrate_bps,
    a_bps=audio_bitrate_bps,
    duration=duration,
    passlogfile=passlogfile,
    target_container=target_container,
    target_pix_fmt=target_pix_format,
    threads=threads,
    cpu_used=5,
    test_only=True,
    test_seconds=config.SAMPLE_SECONDS
)

scaling_factor = (target_filesize_bytes / duration * config.SAMPLE_SECONDS) / sample_size_bytes \
    if sample_size_bytes > 0 else 1.0

corrected_total_bps = target_total_bps * scaling_factor
video_bitrate_bps, audio_bitrate_bps = computeBitrates(corrected_total_bps)

# ---- cap bitrates again before full encode ----
values = {'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps}
capped = capDictToOriginal(values, reference)
video_bitrate_bps = capped['v_bps']
audio_bitrate_bps = capped['a_bps']

print(f"[DEBUG] Duration={duration:.2f}s, Video={video_bitrate_bps/1000:.1f}k, Audio={audio_bitrate_bps/1000:.1f}k")

# ---- adaptive adjustment loop ----
total_start = time.time()
passes_done = 0

# first full encode (unpack tuple)
final_size_bytes, video_bitrate_bps, audio_bitrate_bps = encodeFile(
    input_file,
    output_file,
    video_bitrate_bps,
    audio_bitrate_bps,
    duration,
    passlogfile,
    target_container,
    target_pix_format,
    threads
)
passes_done += 1

last_final_size = None
last_video_bps = None
last_audio_bps = None

while abs(final_size_bytes - target_filesize_bytes) / target_filesize_bytes > 0.02 \
        and passes_done < max_passes:

    error_ratio = final_size_bytes / target_filesize_bytes
    corrected_total_bps /= error_ratio
    video_bitrate_bps, audio_bitrate_bps = computeBitrates(corrected_total_bps)

    # ---- cap each iteration ----
    values = {'v_bps': video_bitrate_bps, 'a_bps': audio_bitrate_bps}
    capped = capDictToOriginal(values, reference)
    video_bitrate_bps = capped['v_bps']
    audio_bitrate_bps = capped['a_bps']

    # stop if nothing changed
    if (video_bitrate_bps == last_video_bps and audio_bitrate_bps == last_audio_bps) \
            or (last_final_size is not None and final_size_bytes == last_final_size):
        print(f"[INFO] No further change detected, stopping retries early after {passes_done} passes")
        break

    elapsed_total = time.time() - total_start
    passes_remaining = max_passes - passes_done
    eta_total_sec = (elapsed_total / passes_done) * passes_remaining if passes_done > 0 else 0
    eta_hr, rem = divmod(int(eta_total_sec), 3600)
    eta_min, eta_sec = divmod(rem, 60)

    print(f"[ADJUST {passes_done}/{max_passes}] Size={final_size_bytes/1024/1024:.2f} MiB "
          f"(error_ratio {error_ratio:.3f}) -> trying {video_bitrate_bps/1000:.1f}k/{audio_bitrate_bps/1000:.1f}k "
          f"(Overall ETA {eta_hr:02d}:{eta_min:02d}:{eta_sec:02d})")

    final_size_bytes, video_bitrate_bps, audio_bitrate_bps = encodeFile(
        input_file,
        output_file,
        video_bitrate_bps,
        audio_bitrate_bps,
        duration,
        passlogfile,
        target_container,
        target_pix_format,
        threads
    )

    last_video_bps = video_bitrate_bps
    last_audio_bps = audio_bitrate_bps
    last_final_size = final_size_bytes
    passes_done += 1

# ---- final report ----
print(f"[DONE] Final size {final_size_bytes/1024/1024:.2f} MiB (target {target_filesize_bytes/1024/1024:.2f} MiB)")
print(f"[RESULT] Video={int(video_bitrate_bps/1000)}k, Audio={int(audio_bitrate_bps/1000)}k, "
      f"Size={final_size_bytes/1024/1024:.2f} MiB")

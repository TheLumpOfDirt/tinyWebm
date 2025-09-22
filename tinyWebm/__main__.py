# __main__.py
import os
import sys

import ffmpeg
import psutil
import pymkv

# ---- default settings ----
input_file = str(sys.argv[1])
output_file = str(sys.argv[2])
passlogfile = "ffmpeg2pass"
# TODO, make this dynamic

target_filesize = (10 * 8 * 1024 * 1024) # 10 MiB
target_container = "webm"
target_fps = "6"
target_resolution = "160x120"
target_pix_format = "yuv420p"

# ---- general settings ----
threads = (min(8, psutil.cpu_count()))

# ---- audio settings ----
audio_codec = "libopus" # libopus or libvorbis; libvorbis not implemented yet
audio_bitrate = "8k"
audio_samplerate = "48000"
audio_vbr = "1"
audio_application = "voip" # voip, audio, or lowdelay
audio_cutoff = "12000"


# ---- video settings ----
video_codec = "libvpx-vp9"
video_bitrate = "6k"
video_gop = int(target_fps) * 10
video_qmin = 30
video_qmax = 58
video_undershoot_pct = 80
video_overshoot_pct = 100
video_lag_in_frames = 25


# ---- preparing ffmpeg args ----

target_args = {
    'threads': threads,
    'pix_fmt': target_pix_format,
}

# generic audio encoding args
audio_args = {
    'acodec': audio_codec,
    'b:a': audio_bitrate,
    'ar': audio_samplerate,
    'ac': 1,
    'vbr': audio_vbr,
    'application': audio_application,
    'cutoff': audio_cutoff,
}

# generic video encoding args
video_args = {
    'vcodec': video_codec,
    'b:v': video_bitrate,
    'g': video_gop,
    'qmin': video_qmin,
    'qmax': video_qmax,
    'r': target_fps,
    's': target_resolution,
    'undershoot-pct': video_undershoot_pct,
    'overshoot-pct': video_overshoot_pct,
    'lag-in-frames': video_lag_in_frames,
}

# ---- actually create the ffmpeg commands ----

# first pass
first_pass = (
    ffmpeg
    .input(input_file)
    .output(
        'NUL' if os.name == 'nt' else '/dev/null',
        format = 'null',
        **target_args,
        **video_args,
        **{
            'pass': 1,
            'passlogfile': passlogfile,
            'an': None,  # no audio in first pass
        }
    )
)

# second pass
second_pass = (
    ffmpeg
    .input(input_file)
    .output(
        output_file,
        format = target_container,
        **target_args,
        **video_args,
        **audio_args,
        **{
            'pass': 2,
            'passlogfile': passlogfile,
        }
    )
)

# run the passes
first_pass.run(overwrite_output=True)
second_pass.run(overwrite_output=True)

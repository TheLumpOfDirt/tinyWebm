# build_ffmpeg_command.py
import sys

import ffmpeg

def buildFFmpegCommand(
    input_file, output_file,
    target_resolution, target_fps,
    audio_codec, audio_bitrate, audio_samplerate,
    audio_vbr, audio_application, audio_frame_duration,
    video_use_vp9, video_bitrate, video_minrate, video_maxrate,
    video_bufsize, video_speed, video_quality,
    video_auto_alt_ref, video_lag_in_frames,
    video_arnr_maxframes, video_arnr_strength,
    video_tile_columns, video_frame_parallel,
    video_tune_content, video_keyframe_max_dist,
    pass_num
):
    """Build an ffmpeg-python command chain for VP9 + Opus with two-pass encoding."""

    # Parse resolution "WxH"
    w, h = (int(x) for x in target_resolution.split("x"))

    # Start input
    stream = ffmpeg.input(input_file)

    # Apply scaling + fps filter
    stream = stream.filter("scale", w, h).filter("fps", fps=int(target_fps)).filter("format", "yuv420p")

    # Video arguments
    video_args = {
        "c:v": "libvpx-vp9" if video_use_vp9 else "libvpx",
        "b:v": video_bitrate,
        "minrate": video_minrate,
        "maxrate": video_maxrate,
        "bufsize": video_bufsize,
        "speed": int(video_speed),
        "quality": video_quality,
        "auto-alt-ref": int(video_auto_alt_ref),
        "lag-in-frames": int(video_lag_in_frames),
        "arnr-maxframes": int(video_arnr_maxframes),
        "arnr-strength": int(video_arnr_strength),
        "tile-columns": int(video_tile_columns),
        "frame-parallel": int(video_frame_parallel),
        "tune-content": int(video_tune_content),
        "g": int(video_keyframe_max_dist),
        "row-mt": 1,
        "threads": 8,
        "pass": int(pass_num)
    }


    audio_args = {
    "c:a": str(audio_codec),        # libopus
    "b:a": str(audio_bitrate),      # e.g. 64k
    "ar": int(audio_samplerate),    # 48000
    "ac": 2                         # force stereo (more compatible than mono)
    }


    if pass_num == 1:
        output_target = "NUL" if sys.platform == "win32" else "/dev/null"
        out = ffmpeg.output(
            stream,
            output_target,
            f="null",   # required for Linux
            **video_args,
            **audio_args
        )

    else:
        out = (
            ffmpeg.output(
                stream,
                output_file,
                f="webm",
                **video_args,
                **audio_args
            )
            .global_args(
                "-vbr", str(audio_vbr),
                "-application", str(audio_application),
                "-frame_duration", str(audio_frame_duration)
            )
        )

    return out

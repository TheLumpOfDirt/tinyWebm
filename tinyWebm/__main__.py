# __main__.py
import sys

import psutil
import ffmpeg

# ---- default settings ----
input_file = str(sys.argv[1])
output_file = str(sys.argv[2])
# TODO, make this dynamic

target_filesize = (10 * 1024 * 1024) # 10 MiB
target_container = "matroska" # no reason to change this, this is required for webm
target_fps = "8"

# ---- general settings ----
threads = (min(8, psutil.cpu_count()))
profile = 2 # DO NOT CHANGE

# ---- audio settings ----
audio_codec = "libopus" # libopus or libvorbis; libvorbis not implemented yet

if audio_codec == "libopus":
    audio_bitrate = "6000" # bps (bits per second)
    audio_vbr = "constrained" # off, on, or constrained
    audio_compression_level = "10" # 0-10, no need to change for most cases unless you need speed
    audio_frame_duration = "60" # can be 2.5, 5, 10, 20, 40, 60; 20 or less is kinda pointless at these bitrates
    audio_application = "audio" # voip, audio, or lowdelay
    audio_cutoff = "8000" # 4000, 6000, 8000, 12000, 20000; 0 is disabled, 8000 (or less) is forced under 15,000 bps
    audio_apply_phase_inversion = "1" # sounds better in mono-downmixes, worse in stereo
elif audio_codec == "libvorbis":
    pass # TODO

# ---- video settings ----
video_encoder = "libvpx" # DO NOT CHANGE
video_use_vp9 = True
video_bitrate = ""
video_keyframe_max_dist = str(target_fps * 10)
video_keyframe_min_dist = ""
video_qmin = ""
video_qmax = ""
video_bufsize = ""
video_rc_occupancy = ""
video_undershoot_pct = ""
video_overshoot_pct = ""
video_skip_threshold = ""
video_qcomp = ""
video_maxrate = ""
video_minrate = ""
video_crf = ""
video_tune = "psnr" # psnr or ssim
video_quality = "good" # best, good, or realtime; DO NOT CHANGE
video_speed = "3"
video_noise_sensitivity = ""
video_static_thresh = ""
video_slices = ""
video_max_intra_rate = ""
video_force_key_frames = ""

video_auto_alt_ref = "1"
video_arnr_maxframes = "7"
video_arnr_type = "" # backward, forward, centered. 
video_arnr_strength = "4"
video_lag_in_frames = "25"
video_min_gf_interval = ""
video_error_resilient = "1"
video_sharpness = "" # integer

video_ts_number_layers = ""
video_ts_target_bitrate = ""
video_ts_rate_decimator = ""
video_ts_periodicity = ""
video_ts_layer_id = ""
video_ts_layering_mode = "0"
video_temporal_id = ""

if video_use_vp9:
    video_lossless = ""
    video_tile_columns = "1"
    video_tile_rows = "0"
    video_frame_parallel = ""
    video_aq_mode = "0"
    video_colorspace = ""
    video_row_mt = "1" # boolean
    video_tune_content = "0" # default (0), screen (1), film (2). 
    video_corpus_complexity = "0" 
    video_enable_tpl = "1" # boolean
    video_ref_frame_config = ""
    video_rfc_update_buffer_slot = ""
    video_rfc_update_last = ""
    video_rfc_update_golden = ""
    video_rfc_update_alt_ref = ""
    video_rfc_lst_fb_idx = ""
    video_rfc_gld_fb_idx = ""
    video_rfc_alt_fb_idx = ""
    video_rfc_reference_last = ""
    video_rfc_reference_golden = ""
    video_rfc_reference_alt_ref = ""
    video_rfc_reference_duration = ""
else:
    video_screen_content_mode = "0" # 0 (off), 1 (screen), 2 (screen with more aggressive rate control).

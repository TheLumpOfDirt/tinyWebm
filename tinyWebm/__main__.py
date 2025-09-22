# __main__.py
import os
import sys

import ffmpeg
import psutil

# ---- default settings ----
input_file = str(sys.argv[1])
output_file = str(sys.argv[2])
passlogfile = "ffmpeg2pass"
# TODO, make this dynamic

target_filesize = (10 * 1024 * 1024) # 10 MiB
target_container = "webm"
target_fps = "6"
target_resolution = "160x120"

# ---- general settings ----
threads = (min(8, psutil.cpu_count()))

# ---- audio settings ----
audio_codec = "libopus" # libopus or libvorbis; libvorbis not implemented yet

if audio_codec == "libopus":
    audio_bitrate = "6k" # bps (bits per second)
    audio_vbr = "constrained" # off, on, or constrained
    audio_compression_level = "10" # 0-10, no need to change for most cases unless you need speed
    audio_frame_duration = "60" # can be 2.5, 5, 10, 20, 40, 60; 20 or less is kinda pointless at these bitrates
    audio_application = "voip" # voip, audio, or lowdelay
    audio_cutoff = "8000" # 4000, 6000, 8000, 12000, 20000; 0 is disabled, 8000 (or less) is forced under 15,000 bps
    audio_apply_phase_inversion = "1" # sounds better in mono-downmixes, worse in stereo
elif audio_codec == "libvorbis":
    print("libvorbis is not implemented yet!") # TODO
else:
    print(audio_codec, " is not recognized or not supported")

audio_samplerate = "12000"

# ---- video settings ----
video_codec = "libaom-av1" # libvpx-vp9 or libaom-av1; libvpx-vp9 is faster, libaom-av1 is better quality

if video_codec == "libaom-av1":
    video_bitrate = str(int((target_filesize * 8) / 1000) - int(audio_bitrate[:-1])) + "k" # bps (bits per second)
    video_gop = str(int(target_fps) * 10) # keyframe interval, in frames; 10 seconds is a good baseline
    video_qmin = "14" # 0-63, lower is better quality; 30 is a good baseline
    video_qmax = "58" # 0-63, higher is worse quality; 50 is a good baseline
    video_threads = str(threads) # number of threads to use
    video_cpu_used = "2" # 0 to 6, lower is better quality but slower;
    video_auto_alt_ref = "1"
    video_arnr_max_frames = "15"
    video_arnr_strength = "6"
    video_aq_mode = "3"
    video_tune = "1" # psnr (0) or ssim (1); ssim is better for small resolutions
    video_static_thresh = "20"
    video_drop_frame = "30"
    video_denoise_noise_level = "5"
    video_denoise_block_size = "32"
    video_undershoot_pct = "80"
    video_overshoot_pct = "100"
    video_minsection_pct = "-1"
    video_maxsection_pct = "-1"
    video_frame_parallel = "1" #boolean
    video_tiles = ""
    video_tile_columns = "0"
    video_tile_rows = "0"
    video_row_mt = "1" #boolean
    video_enable_cdef = "1" #boolean
    video_enable_restoration = "1"
    video_enable_global_motion = ""
    video_enable_intrabc = ""
    video_enable_rect_partitions = ""
    video_enable_1to4_partitions = ""
    video_enable_ab_partitions = "0"
    video_enable_angle_delta = ""
    video_enable_cfl_intra = ""
    video_enable_filter_intra = ""
    video_enable_intra_edge_filter = ""
    video_enable_smooth_intra = ""
    video_enable_paeth_intra = ""
    video_enable_palette = ""
    video_enable_flip_idtx = ""
    video_enable_tx64 = ""
    video_reduced_tx_type_set = ""
    video_use_intra_dct_only = ""
    video_use_inter_dct_only = ""
    video_use_intra_default_tx_only = ""
    video_enable_ref_frame_mvs = ""
    video_enable_reduced_reference_set = ""
    video_enable_obmc = ""
    video_enable_dual_filter = ""
    video_enable_diff_wtd_comp = ""
    video_enable_dist_wtd_comp = "0"
    video_enable_onesided_comp = ""
    video_enable_interinter_wedge = ""
    video_enable_interintra_wedge = ""
    video_enable_masked_comp = ""
    video_enable_interintra_comp = ""
    video_enable_smooth_interintra = ""

    video_sb_size = "dynamic"
    video_lag_in_frames = "35"
    video_bit_depth = "10"
    video_deltaq_mode = "1"
    video_sharpness = "7"
    video_enable_dnl_denoising = "0"
    video_denoise_noise_level = "5"
    video_tune_content = "default"
    video_enable_qm = "1"
    video_quant_b_adapt = "1"
    video_enable_fw_kf = "1"
    video_enable_chroma_deltaq = "0"
    video_enable_keyframe_filtering = "2"
    video_profile = "0"

    #aom specific parameters    video_superres_qthresh = "50"
    video_resize_denominator = "15"
    video_resize_kf_denominator = "10"
    video_superres_kf_qthresh = "55"
    video_resize_mode = "3"
    video_sframe_dist = "8"
    video_sframe_mode = "2"
    video_enable_tpl_model = "1"
    video_frame_boost = "1"
    video_tune_content = "screen"
    video_bias_pct = "100"
    video_end_usage = "q"
    video_coeff_cost_upd_freq = "1"
    video_target_bitrate = "1"
    video_width = "128"
    video_height = "72"
    video_u = "0"
    video_t = "2"
    video_p = "2"
    video_disable_trellis_quant = "0"
    video_cq_level = "53"
    video_superres_mode = "4"
    video_tune = "vmaf"
    video_pass = "(insert pass number here)"
    video_fpf = "pass.txt"
    video_mv_cost_upd_freq = "1"
    video_noise_sensitivity = "2"
elif video_codec == "libvpx-vp9":
    print("libvpx-vp9 is not implemented yet!") # TODO
else:
    print(video_codec, " is not recognized or not supported")

# ---- preparing ffmpeg args ----

# generic audio encoding args
audio_args = {
    'acodec': audio_codec,
    'b:a': audio_bitrate,                     # bitrate
    'ar': audio_samplerate,                    # samplerate
    'ac': 1,                                   # channels
    'vbr': audio_vbr,
    'application': audio_application,
    'cutoff': audio_cutoff,
}

# Generic video encoding args
video_args = {
    'vcodec': 'libaom-av1',
    'b:v': video_bitrate,     # bitrate
    'g': video_gop,           # GOP/keyframe interval
    'qmin': video_qmin,       # min quantizer
    'qmax': video_qmax,       # max quantizer
    'threads': video_threads, # threading
    'r': target_fps,          # framerate
    's': target_resolution,   # scale
    'undershoot-pct': video_undershoot_pct,
    'overshoot-pct': video_overshoot_pct,
    'lag-in-frames': video_lag_in_frames,
}

# AV1 encoder-specific params
aom_params_str = ":".join([
    f"cpu-used={video_cpu_used}",
    f"auto-alt-ref={video_auto_alt_ref}",
    f"arnr-maxframes={video_arnr_max_frames}",
    f"arnr-strength={video_arnr_strength}",
    f"aq-mode={video_aq_mode}",
    f"static-thresh={video_static_thresh}",
    f"frame-parallel={video_frame_parallel}",
    f"tile-columns={video_tile_columns}",
    f"tile-rows={video_tile_rows}",
    f"row-mt={video_row_mt}",
    f"enable-cdef={video_enable_cdef}",
    f"enable-restoration={video_enable_restoration}",
    f"sb-size={video_sb_size}",
    f"deltaq-mode={video_deltaq_mode}",
    f"sharpness={video_sharpness}",
    f"tune-content={video_tune_content}",
    f"enable-qm={video_enable_qm}",
    f"quant-b-adapt={video_quant_b_adapt}",
    f"enable-keyframe-filtering={video_enable_keyframe_filtering}",
    f"enable-tpl-model={video_enable_tpl_model}",
    f"frame-boost={video_frame_boost}",
    f"coeff-cost-upd-freq={video_coeff_cost_upd_freq}",
    f"disable-trellis-quant={video_disable_trellis_quant}",
    f"cq-level={video_cq_level}",
    f"mv-cost-upd-freq={video_mv_cost_upd_freq}",
    f"noise-sensitivity={video_noise_sensitivity}",
])

# First pass
first_pass = (
    ffmpeg
    .input(input_file)
    .output(
        'NUL' if os.name == 'nt' else '/dev/null',
        format=target_container,
        **video_args,
        **{
            'pass': 1,
            'passlogfile': passlogfile,
            'an': None,  # no audio in first pass
            'aom-params': aom_params_str
        }
    )
)

# Second pass
second_pass = (
    ffmpeg
    .input(input_file)
    .output(
        output_file,
        format=target_container,
        **video_args,
        **audio_args,
        **{
            'pass': 2,
            'passlogfile': passlogfile,
            'aom-params': aom_params_str,
            'af': "pan=mono|c0=FC"
        }
    )
)

# Run the passes
first_pass.run(overwrite_output=True)
second_pass.run(overwrite_output=True)

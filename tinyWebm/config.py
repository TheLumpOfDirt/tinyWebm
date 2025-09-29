# config.py

# pass log file base name (ffmpeg will append -0.log etc.)
PASSLOGFILE = "ffmpeg2pass"


# ---- user-visible target: 10 MiB (bytes) ----
TARGET_FILESIZE_BYTES = 10 * 1024 * 1024 # 10 MiB in BYTES
TARGET_CONTAINER = "webm"
TARGET_PIX_FORMAT = "yuv420p10le"


# ---- general settings ----
DEFAULT_THREADS = 1
MAX_PASSES = 10 # safety limit


# ---- audio defaults ----
AUDIO_CODEC = "libopus"
AUDIO_VBR = "1"
AUDIO_APPLICATION = "voip"
AUDIO_FRAME_DURATION = "60"


# ---- video defaults ----
VIDEO_CODEC = "libvpx-vp9"


# ---- video tuning parameters (kept from original file) ----
VIDEO_QMIN = 30
VIDEO_QMAX = 53
VIDEO_UNDERSHOOT_PCT = 80
VIDEO_OVERSHOOT_PCT = 100
VIDEO_QCOMP = 53
VIDEO_CRF = 1
VIDEO_TUNE = "ssim"
VIDEO_QUALITY = "good"
VIDEO_CPU_USED = "3"
VIDEO_AUTO_ALT_REF = 1
VIDEO_ARNR_MAXFRAMES = 7
VIDEO_ARNR_STRENGTH = 4
VIDEO_AQ_MODE = 2
VIDEO_ROW_MT = 1
VIDEO_TILE_COLUMNS = 1
VIDEO_TILE_ROWS = 0
VIDEO_ENABLE_TPL = 1
VIDEO_PROFILE = 2
VIDEO_LAG_IN_FRAMES = 25


# default sample seconds used for quick test encode
SAMPLE_SECONDS = 5

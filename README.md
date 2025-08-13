# Introduction
A modern Python application for video watermarking with invisible watermark support.

# Getting started
## install prerequirements
### install python(use conda)
- download forge conda installer
  - https://conda-forge.org/download/
- install forge-conda
```shell

# macos-apple-chip installer scripts
chmod u+x Miniforge3-Darwin-arm64.sh

bash ./Miniforge3-Darwin-arm64.sh

# if use zsh
conda init zsh


# create new env for Python 3.11
conda create -n py311 python=3.11

# active python 3.11
conda activate py311
```

### install ffmpeg
- macos
```shell
brew install ffmpeg
```
- other platform, please download ffmpeg installer and add ffmpeg path to environment.
  - https://ffmpeg.org/download.html

## Development Setup


```shell
cd video_watermark

# Create virtual environment
conda activate py311
python -m venv .venv 
source .venv/bin/activate


# 1. 确保已安装开发模式（只需执行一次）
pip install -e .

# 2.1 直接运行（从任何目录）
python -m video_watermark.main 

#2.2 or you can also use script to execute it.
python scripts/run_watermark.py
```

### Production Installation

```bash
pip install video_watermark
```

## Usage
provide 3 ways to execute it.

### Batch add watermark for videos

```bash
# use python shell
python -m video_watermark.main

or
python scripts/run_watermark.py

# use shell script(current dir is video_watermark)
chmod u+x scripts/*.sh 
./scripts/run_watermark.sh
```

### Batch concate multi videos into single one

```bash
# use python shell
python -m video_watermark.concate

or 
python scripts/run_concate.py

# use shell script(current dir is video_watermark)
./scripts/run_concate.sh
```

### Extract audio from videos
```bash
# use python shell
python -m video_watermark.audio

or 
python scripts/run_audio.py

# use shell script(current dir is video_watermark)
./scripts/run_audio.sh
```

### Configuration

Create an `env.txt` file in your working directory:

```
VIDEO_DIR=/path/to/videos
WATERMARK_LOGO_TEXT=Jack is granted for
CURRENT_COURSE_NAME=2025-08-test-course-video
INVISIBLE_WATERMARK_STEP=14
FFMPEG_OPTIONS=-c:v h264_videotoolbox -q:v 50 -profile:v high -allow_sw 1
FFMPEG_CONCURRENCY=2
IS_SYNC_TO_BAIDU=1
REMOTE_DIR=/apps/bypy
DELETE_AFTER_UPLOAD_SUCCESS=1
```

config key and description

| key                                      | Description                                                                                                                                                                                                                   | Required | Default value | Sample value                                                            |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------------|-------------------------------------------------------------------------|
| VIDEO_DIR                     | Path to origin video dir                                                                                                                                                                                                      | YES      |               | /path/to/videos                                                         |
| WATERMARK_LOGO_TEXT                    | logo image text for videos                                                                                                                                                                                                    | YES      |               | xx is granted for                                                       |
| CURRENT_COURSE_NAME           | current batch process video course name(is required for upload to baidu pcs)                                                                                                                                                  | YES      |               | 2025-08-test-course                                                     |
| INVISIBLE_WATERMARK_STEP               | invisible watermark ratio for videos, 0-means no invisible watermark, 1-means all videos will add invisible watermark, 2-means every 2 videos will have 1 invisible watermark and the other one is only add dynamic logo text | YES      | 1             | 10                                                                      |
| FFMPEG_OPTIONS                 | ffmpeg options for use paltform hardware                                                                                                                                                                                      | Optional |               | -c:v h264_videotoolbox -q:v 50 -profile:v high -allow_sw 1  # for macos |
| FFMPEG_CONCURRENCY | ffmpeg concurrecy number                                                                                                                                                                                                      | Optional |               | 2                                                                       |
| TARGET_DIR            | path to target videos                                                                                                                                                                                                         | Optional |               |                                                                         |
| IS_SYNC_TO_BAIDU  | Weather upload to baidu pcs, 0-means not upload, 1-means upload to baidu pcs                                                                                                                                                  | Optional | 0             | 0                                                                       | 
| UPLOAD_TIMEOUT            | Upload timeout, default is 3600 seconds                                                                                                                                                                                       | Optional | 3600          | 3600                                                                    |
| REMOTE_DIR  | baidu pcs remote dir                                                                                                                                                                                                          | Optional | /apps/bypy    | /apps/bypy                                                              | 
| DELETE_AFTER_UPLOAD_SUCCESS            | Weather delete local file if upload success. 0-means not delete, 1-means delete                                                                                                                                               | Optional | 0             | 0                                                                       |

## Project Structure

```
src/
|── scripts/                 # shell and python scripts for easy use.
│   ├── run_watermark.py     # add watermark for videos.
│   └── ...
├── videowatermark/          # Main application package
│   ├── __init__.py
│   ├── main.py             # gen video watermark
│   ├── audio.py            # gen audio files
│   ├── concate.py          # concate videos
│   └── ...
└── algorithm/              # Algorithm implementations
    └── blind_watermark/    # Blind watermark algorithm
        ├── __init__.py
        ├── watermark.py
        └── ...
```

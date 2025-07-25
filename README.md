# Introduction
A modern Python application for video watermarking with invisible watermark support.

# Getting started
## environment setup

- install python(use conda)

```shell
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh

chmod u+x  Miniconda3-latest-MacOSX-arm64.sh

bash ./Miniconda3-latest-MacOSX-arm64.sh

# if use zsh
source ~/.zshrc


# create new env for Python 3.11
conda create -n py311 python=3.11

# active python 3.11
conda activate py311
```

## Development Setup


```shell
cd video_watermark

# Create virtual environment
python -m venv .venv 
source .venv/bin/activate


# 1. 确保已安装开发模式（只需执行一次）
pip install -e .

# 2. 直接运行（从任何目录）
python -m video_watermark.main 
```

### Production Installation

```bash
pip install video_watermark
```

## Usage

### Command Line

```bash
video_watermark
```

### Configuration

Create an `env.txt` file in your working directory:

```
VIDEO_DIR=/path/to/videos
TARGET_DIR=/path/to/output
IS_TEST=1
IS_SYNC_TO_BAIDU=1
```

## Project Structure

```
src/
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

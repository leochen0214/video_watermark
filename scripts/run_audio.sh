#!/bin/bash

PRG="$0"
PRGDIR=$(dirname "$PRG")
cd "$PRGDIR/.." || exit
APP_BASE=$(pwd)
VENV_PATH=$APP_BASE/.venv
echo "current path: $APP_BASE"

# check .venv dir weather exists
if [ -d "$VENV_PATH" ]; then
    echo "venv path exists: $VENV_PATH"
else
    echo "$VENV_PATH not exists"
    if conda env list | grep -qw 'py311'; then
      echo "conda env name: py311 exists"
    else
      echo "conda env name: py311 not exists, will create it"
      conda create -n py311 python=3.11
    fi
    conda run -n py311 python -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
python --version

if find . -type d -name "video_watermark.egg-info" -print -quit | grep -q .; then
    echo "video_watermark.egg-info 目录存在"
else
    echo "video_watermark.egg-info 目录不存在"
    pip install -e .
fi

python -m video_watermark.audio

echo "Done!!!!"


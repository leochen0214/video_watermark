# Introduction
This is a project to add watermark(include **invisible watermark**) to videos.

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

- project setup

```shell
cd video_watermark

python -m venv .venv 
source .venv/bin/activate


# 1. 确保已安装开发模式（只需执行一次）
pip install -e .

# 2. 直接运行（从任何目录）
python -m video_watermark.main 
```

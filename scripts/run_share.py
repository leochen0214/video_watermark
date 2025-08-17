#!/usr/bin/env python3
"""
share baidu pcs link to WeChat contact
"""
import sys
from pathlib import Path

# Add src to path for imports
p = Path(__file__)
print(p)
project_root = p.parent.parent
sys.path.insert(0, str(project_root / "src"))

from video_watermark.share import main

if __name__ == "__main__":
    main()
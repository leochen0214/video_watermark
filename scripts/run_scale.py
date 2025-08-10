#!/usr/bin/env python3
"""
Video audio processing script
"""
import sys
from pathlib import Path

# Add src to path for imports
p = Path(__file__)
print(p)
project_root = p.parent.parent
sys.path.insert(0, str(project_root / "src"))

from video_watermark.scale import main

if __name__ == "__main__":
    main()
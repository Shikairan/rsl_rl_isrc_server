#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from cases import execute

if __name__ == "__main__":
    raise SystemExit(execute('I-07', Path(__file__).resolve().parent))

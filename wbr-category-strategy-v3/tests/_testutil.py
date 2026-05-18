"""Test utility: make wbr_engine importable from any test file."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# 当前进程：让 `import wbr_engine` 工作
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 子进程（subprocess）：通过 PYTHONPATH 继承，让 scripts/*.py shim 也能 import wbr_engine
_existing = os.environ.get('PYTHONPATH', '')
_root_str = str(ROOT_DIR)
if _root_str not in _existing.split(os.pathsep):
    os.environ['PYTHONPATH'] = _root_str + (os.pathsep + _existing if _existing else '')

SCRIPTS_DIR = ROOT_DIR / 'scripts'
FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'

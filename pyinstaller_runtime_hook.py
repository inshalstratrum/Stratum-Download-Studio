"""Make the bundled PyQt6 Qt DLL directory available before QtWidgets loads."""

import os
import sys
from pathlib import Path


qt_bin = Path(sys._MEIPASS) / "PyQt6" / "Qt6" / "bin"
if qt_bin.is_dir():
    os.environ["PATH"] = f"{qt_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(qt_bin))

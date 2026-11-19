"""I-DS Download Support — Windows GUI entry point (no terminal window).

Historical source filename remains import-compatible.
"""
from stratum_download_studio import main

if __name__ == "__main__":
    raise SystemExit(main())

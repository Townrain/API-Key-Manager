"""Verify icon is embedded in the built EXE by counting PNG signatures."""
import sys
from pathlib import Path

exe_path = Path("dist/KeyHub.exe")
if not exe_path.exists():
    print(f"ERROR: {exe_path} not found")
    sys.exit(1)

data = exe_path.read_bytes()
png_sig = b"\x89PNG\r\n\x1a\n"

png_count = 0
pos = 0
while True:
    pos = data.find(png_sig, pos)
    if pos == -1:
        break
    png_count += 1
    pos += 1

print(f"PNG signatures in EXE: {png_count}")
if png_count >= 6:
    print("Icon VERIFIED: all 6 PNG frames found")
else:
    print(f"WARNING: only {png_count} PNG signatures (expected 6+)")
    sys.exit(1)

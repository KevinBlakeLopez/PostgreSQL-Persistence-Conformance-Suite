#!/bin/sh
# Copy the network guard into a virtual environment's site-packages.
# Usage: install.sh /path/to/venv
set -eu
venv=$1
site=$("$venv/bin/python" -I -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
here=$(cd "$(dirname "$0")" && pwd)
cp "$here/ppcs_netguard.py" "$here/ppcs_netguard.pth" "$site/"
"$venv/bin/python" -I -c 'import socket, ppcs_netguard; print("netguard active:", socket.socket.connect is ppcs_netguard.connect)'

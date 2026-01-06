#!/usr/bin/env python3
import time
import sys

if '--daemon' in sys.argv:
    print("Starting network monitor...")
    while True:
        time.sleep(60)
else:
    print("Network monitor script")

#!/usr/bin/env python3
import sys
from memory import main

raise SystemExit(main(["status", *sys.argv[1:]]))

#!/usr/bin/env python3
import sys
from memory import main

raise SystemExit(main(["validate", *sys.argv[1:]]))

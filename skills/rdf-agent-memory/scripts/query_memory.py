#!/usr/bin/env python3
import sys
from memory import main

raise SystemExit(main(["query", *sys.argv[1:]]))

#!/usr/bin/env python3
from subprocess import Popen
import os

FILE='./buildy.py'

process = Popen(FILE, shell=True)

current = os.path.getmtime(FILE)

while True:
  mtime = os.path.getmtime(FILE)
  if mtime != current:
    current = mtime
    process.kill()
    process = Popen(FILE, shell=True)

  
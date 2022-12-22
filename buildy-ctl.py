#!/usr/bin/env python3
from subprocess import Popen
import os

FILE='./buildy.py'

dir = 'temp/buildy'
os.makedirs(dir, exist_ok=True)
cmd = f"{FILE} -d {dir}"

process = Popen(cmd, shell=True)

current = os.path.getmtime(FILE)

while True:
  mtime = os.path.getmtime(FILE)
  if mtime != current:
    current = mtime
    process.kill()
    process.wait()
    process = Popen(cmd, shell=True)

  
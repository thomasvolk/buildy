#!/usr/bin/env python3
import requests
from subprocess import Popen

BUILDY_URL='http://localhost:9000'

def mk_repo(name, sleep_interval):
    return f"""mkdir -p temp/repos/{name} &&
cd temp/repos/{name} &&
echo "all:\n\tsleep {sleep_interval}" > Makefile &&
git init && git add --all && git commit -m"{name}" """

prepare_tests = "rm -rf temp && " + mk_repo(10, 0.01) + " && " + mk_repo(100, 0.1) + " && " + mk_repo(1000, 1)

process = Popen(prepare_tests, shell=True)
print(process.wait())

#response = requests.post()

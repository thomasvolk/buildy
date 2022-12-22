#!/usr/bin/env python3
import requests
from subprocess import Popen
import os

BUILDY_URL='http://localhost:9000'

def mk_repo(name, sleep_interval):
    return f"""mkdir -p {os.getcwd()}/temp/repos/{name} &&
cd {os.getcwd()}/temp/repos/{name} &&
echo "all:\n\tsleep {sleep_interval}" > Makefile &&
git init && git add --all && git commit -m"{name}" """

prepare_tests = f"rm -rf {os.getcwd()}/temp && " + mk_repo(10, 0.01) + " && " + mk_repo(100, 0.1) + " && " + mk_repo(1000, 1)

process = Popen(prepare_tests, shell=True)
assert 0 == process.wait()

print("test data created")

response = requests.post(f"{BUILDY_URL}/build", json={"url": f"{os.getcwd()}/temp/repos/1000"})
assert 201 == response.status_code
build_id = response.json()['id']
print(f"build created {build_id}")
response = requests.get(f"{BUILDY_URL}/build/{build_id}")
assert 200 == response.status_code
build = response.json()
print(build)

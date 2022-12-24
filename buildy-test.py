#!/usr/bin/env python3
import requests
from subprocess import Popen
import os
import time

BUILDY_URL='http://localhost:9000'

def mk_repo(name, sleep_interval):
    return f"""mkdir -p {os.getcwd()}/temp/repos/{name} &&
cd {os.getcwd()}/temp/repos/{name} &&
echo "all:\n\tsleep {sleep_interval}\n\ttouch build-complete.txt" > Makefile &&
touch {name}.txt
git init && git add --all && git commit -m"init {name}" && 
git checkout -b qa && 
touch branch-qa.txt && 
git add --all && 
git commit -m "branch qa" && 
touch tag-v1.txt && 
git add --all && 
git commit -m "tag v1" && 
git tag v1 """

prepare_tests = f"""rm -rf {os.getcwd()}/temp &&
mkdir -p {os.getcwd()}/temp/buildy &&
{mk_repo(10, 0.01)} &&
{mk_repo(100, 0.1)} &&
{mk_repo(1000, 1)}"""

process = Popen(prepare_tests, shell=True)
assert 0 == process.wait()

print("test data created")
buildy_dir= f"{os.getcwd()}/temp/buildy"

def start_build(repo):
    response = requests.post(f"{BUILDY_URL}/build", json=repo)
    assert 201 == response.status_code
    build_id = response.json()['id']
    print(f"build created {build_id}")
    response = requests.get(f"{BUILDY_URL}/build/{build_id}")
    assert 200 == response.status_code
    return response.json()

def file_exists(build, path):
    abs_path = f"{buildy_dir}/{build['id']}/{path}"
    count = 0
    while not os.path.exists(abs_path):
        time.sleep(0.1)
        count = count + 1
        if count > 200:
            return False
    return True

build = start_build({"url": f"{os.getcwd()}/temp/repos/10"})
print(build)
assert file_exists(build, "repo/build-complete.txt")

build = start_build({"url": f"{os.getcwd()}/temp/repos/100", "branch": "qa"})
print(build)
assert file_exists(build, "repo/build-complete.txt")
assert file_exists(build, "repo/branch-qa.txt")

build = start_build({"url": f"{os.getcwd()}/temp/repos/1000", "tag": "v1"})
print(build)
assert file_exists(build, "repo/build-complete.txt")
assert file_exists(build, "repo/tag-v1.txt")

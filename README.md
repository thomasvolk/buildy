# Buildy

Buildy is a simple build server that can be managed via REST api. It can clone and git repositories and build them via make.

## Run

Simple start the buildy.py script:

    ./buildy.py
    
By default buildy listen to the port 9000 - http://localhost:9000/

You need python3 to run Buildy.

Use the help option to see all programm parameters:

    ./buildy.py --help

## Use

Before you start: Buildy only works with git and will try to build your repository by simply executing make. So your repository must have a Makefile in the project root directory which includes the target "all". Here is an example:

    mkkdir myrepo
    cd myrepo
    echo "all: touch build-complete.txt" > Makefile
    git init
    git add --all
    git commit -m"init"

Start a build:

    curl -X POST http://localhost:9000/build -d '{"url": URL_TO_YOUR_REPOSITORY, "branch": OPTIONAL, "tag": OPTIONAL }'

This call returns a jsob object with the build id:

    {"id": "e8006c1d-5f7c-4edf-8c23-79974d02c909"}

Retrieve build details:

    curl http://localhost:9000/build/BUILD_ID

This call returns a json object with the build details:

    {
        "id": BUILD_ID, 
        "status": "RUNNING|SUCCESS|FAILURE", 
        "repository": 
          {
            "url": URL_TO_YOUR_REPOSITORY, 
            "branch": null|BRANCH, 
            "tag": null|TAG
          } 
    }

Retrieve build log:

    curl http://localhost:9000/build/BUILD_ID/log

This call returns a the build log in text format.

    Cloning into 'repo'... 
    done. 
    ... 

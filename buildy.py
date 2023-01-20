#!/usr/bin/env python3

__VERSION__ = '0.2.2'

from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import Popen
import json
from dataclasses import dataclass, asdict
import threading
import uuid
import tempfile
from functools import partial
import os
import datetime
import logging
from enum import Enum
from os import listdir
from os.path import isdir, join

class Status(Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"

    def __str__(self):
        return self.name

@dataclass
class Repository:
    url: str
    branch: str
    tag: str

    def __str__(self):
        result = self.url
        if self.branch:
            result += f" - branch: {self.branch}"
        if self.tag:
            result += f" - tag: {self.tag}"
        return result

class Build:
    def __init__(self, dir, repo):
        self.repo = repo 
        self.id = str(uuid.uuid4())
        self.dir = os.path.join(dir, self.id)
        cmd = f"""cd {self.dir} && git clone {self.repo.url} repo && cd repo"""
        if self.repo.tag != None:
            cmd += f" && git checkout {self.repo.tag}"
        if self.repo.branch != None:
            cmd += f" && git checkout {self.repo.branch}"

        cmd += " && make"
        os.makedirs(self.dir)
        logging.info(f"start build {self.id}")
        self.__log_file_path = f"{self.dir}/build.log"
        self.__log = open(self.__log_file_path, 'w')
        self.__process = Popen(cmd, shell=True, stderr=self.__log, stdout=self.__log)
        self.creation_time = datetime.datetime.now()

    @property
    def status(self):
        result = self.__process.poll()
        if result == None:
            return Status.RUNNING
        elif result == 0:
            return Status.SUCCESS
        else:
            return Status.FAILURE

    @property
    def dict(self):
        return {
                "id": self.id,
                "status": str(self.status),
                "repository": asdict(self.repo)
            }

    @property
    def json(self):
        return json.dumps(self.dict)

    def log(self):
        with open(self.__log_file_path, 'r') as log:
            return log.read()


class BuildCache:
    def __init__(self, max_size):
        self.__cache = dict()
        self.__sem = threading.Semaphore()
        self.__max_size = max_size

    def __getitem__(self, key):
        return self.__cache[key]

    def __setitem__(self, key, value):
        self.__sem.acquire()
        self.cleanup()
        self.__cache[key] = value
        self.__sem.release()

    def get(self, key):
        return self.__cache.get(key)

    def keys(self):
        return self.__cache.keys()

    def values(self):
        return [ i[1] for i in self.__cache_items_sorted() ]

    def __cache_items_sorted(self):
        return sorted(
                        sorted(self.__cache.items(), 
                               key=lambda i: i[1].creation_time, 
                               reverse=True),
                        key=lambda i: i[1].status == Status.RUNNING,
                        reverse=True
                     )

    def __builds_running(self):
        return len([ b for b in self.__cache.values() if b.status == Status.RUNNING])

    def cleanup(self):
        running = self.__builds_running()
        total = len(self.__cache)
        if running <= self.__max_size and total > self.__max_size:
            logging.info(f"cleanup build cache (total={total}, running={running})")
            self.__cache = { id: build for id, build in self.__cache_items_sorted()[0:(self.__max_size-1)] }


class BuildyHandler(BaseHTTPRequestHandler):
    def __init__(self, builds, dir, *args, **kwargs):
        self.dir = dir
        self.builds = builds
        super().__init__(*args, **kwargs)

    def __split_path(self):
        if self.path.endswith('/'):
            p = self.path[1:-1]
        else:
            p = self.path[1:]
        return p.split('/')

    def __send_not_found(self):
        self.send_response(404)
        self.send_header("Content-type", "application/json")
        self.end_headers()

    def __send_build_id(self, build_id):
        self.send_response(201)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps({"id": build_id}), "utf-8"))

    def __send_main_page(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        builds = "".join(
                [ f"""<tr><td><a href="build/{b.id}/log">{b.id}</a></td><td>{b.repo}</td><td>{b.creation_time}</td><td>{b.status}</td></tr>"""
                  for b in self.builds.values() ]
        )
        self.wfile.write(bytes(f"""<html>
        <head>
          <title>Buildy v{__VERSION__}</title>
          <style>
          table {{
            width: 100%;
          }}
          th {{
            text-align: left;
          }}
          td {{
            text-align: left;
          }}
          .code {{
            background: #eee;
            padding: 10px;
            font-size: 11pt;
          }}
          body {{
            background: #fff;
            color: #000;
            font-family: "Source Code Pro", monospace;
            font-size: 14pt;
            }}
          </style>
        </head>
          <body>
            <h1>Buildy v{__VERSION__}</h1>
            Buildy is a simple build server that can be managed via REST api. 
            It can clone and git repositories and build them via make.
            <h2>Current Builds</h2>
            <table>
              <tr><th>id</th><th>repository</th><th>created</th><th>status</th></tr>
              {builds}
            </table>
            <h2>Help</h2>
              Before you start: Buildy only works with git and will try to build your repository by
              simply executing make.
              So your repository must have a <strong>Makefile</strong> in the project root directory 
              which includes the target "all". Here is an example:
              <p class="code">
                mkkdir myrepo <br/>
                cd myrepo <br/>
                echo "all:\n\ttouch build-complete.txt" > Makefile <br/>
                git init <br/>
                git add --all <br/>
                git commit -m"init"
              </p>
              <h3>Start a build:</h3>
              <p class="code">
                  curl -X POST http://localhost:9000/build
                  -d '{{"url": URL_TO_YOUR_REPOSITORY, "branch": OPTIONAL, "tag": OPTIONAL }}'
              </p>
              This call returns a jsob object with the build id:
              <p class="code">{{"id": "e8006c1d-5f7c-4edf-8c23-79974d02c909"}}</p>
              <h3>Retrieve build details:</h3>
              <p class="code">
                curl http://localhost:9000/build/BUILD_ID
              </p>
              This call returns a json object with the build details:
              <p class="code">
              {{
                "id": BUILD_ID,
                "status": "RUNNING|SUCCESS|FAILURE", "repository": 
                {{"url": URL_TO_YOUR_REPOSITORY, "branch": null|BRANCH, "tag": null|TAG}}
              }}
              </p>
              <h3>Retrieve build log:</h3>
              <p class="code">
                curl http://localhost:9000/build/BUILD_ID/log
              </p>
              This call returns a the build log in text format.
              <p class="code">
                Cloning into 'repo'... <br/>
                done. <br/>
                ...
              </p>
          </body>
        </html>""", "utf-8"))

    def __send_build(self, build):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(build.json, "utf-8"))

    def __send_log(self, build):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(bytes(build.log(), "utf-8"))

    def __send_build_history(self):
        history_keys = [ {'key': k }
                         for k in listdir(self.dir) 
                         if isdir(join(self.dir, k)) and not k in self.builds.keys()
                       ]
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(history_keys), "utf-8"))

    def do_POST(self):
        path = self.__split_path()
        if(path == ['build']):
            content_length = int(self.headers['Content-Length'])
            build_setup = json.loads(self.rfile.read(content_length).decode('utf-8'))
            build = Build(self.dir,
                Repository(build_setup.get("url"), build_setup.get("branch"), build_setup.get("tag"))
            ) 
            self.builds[build.id] = build
            self.__send_build_id(build.id)
        else:
            self.__send_not_found()

    def do_GET(self):
        path = self.__split_path()
        if(path == ['']):
            self.__send_main_page()
        elif(path[0] == 'build'):
            if len(path) > 1:
                id = path[1]
                build = self.builds.get(id)
                if(build == None):
                    self.__send_not_found()
                else:
                    if len(path) == 3:
                        if path[2] == 'log':
                            self.__send_log(build)
                        else:
                            self.__send_not_found()
                    else:
                        self.__send_build(build)
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps([b.dict for b in self.builds.values()]), "utf-8"))
        elif(path[0] == 'history'):
            self.__send_build_history()
        else:
            self.__send_not_found()


if __name__ == "__main__":        
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port",
                  help="server port", default="9000")
    parser.add_option("-H", "--host", dest="host_name",
                  help="server host name", default="localhost")
    parser.add_option("-d", "--directory", dest="directory",
                  help="server directory", default=tempfile.mkdtemp("buildy"))
    parser.add_option("-c", "--cache-size", dest="cache_size",
                  help="max cache size", default="20")
    parser.add_option("--log-level", dest="loglevel",
                  help="loglevel", default="INFO")

    (options, args) = parser.parse_args()

    logging.basicConfig(
        format='%(asctime)s %(message)s', 
        level=getattr(logging, options.loglevel.upper())
        )

    hostName = options.host_name
    serverPort = int(options.port)
    build_folder = options.directory

    builds = BuildCache(int(options.cache_size))

    handler = partial(BuildyHandler, builds, build_folder)
    webServer = HTTPServer((hostName, serverPort), handler)
    logging.info(f"Buildy server v{__VERSION__} started http://{hostName}:{serverPort} - dir: {build_folder}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        webServer.server_close()
        logging.info("Buildy server stopped")
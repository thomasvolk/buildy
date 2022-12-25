#!/usr/bin/env python3

__VERSION__ = '0.1'

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
    def running(self):
        running = self.__process.poll() == None
        if not running:
            self.__log.close()
        return running

    @property
    def dict(self):
        return {
                "id": self.id,
                "running": self.running,
                "repository": asdict(self.repo)
            }

    @property
    def json(self):
        return json.dumps(self.dict)

    def log(self):
        with open(self.__log_file_path, 'r') as log:
            return log.read()


class BuildManager:
    def __init__(self):
        self.__cache = dict()
        self.__sem = threading.Semaphore()

    def __getitem__(self, key):
        return self.__cache[key]

    def __setitem__(self, key, value):
        self.__sem.acquire()
        self.cleanup()
        self.__cache[key] = value
        self.__sem.release()

    def get(self, key):
        return self.__cache.get(key)

    def values(self):
        return self.__cache.values()

    def cleanup(self):
        logging.info(f"cleanup build cache")
        self.__cache = { id: build for id, build in self.__cache.items() if build.running}


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
                [ f"""<tr><td><a href="/build/{b.id}/log">{b.id}</a></td><td>{b.repo}</td><td>{b.creation_time}</td><td>{b.running}</td></tr>"""
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
          body {{
            font-family: "Source Code Pro", monospace;
            font-size: 14pt;
            }}
          </style>
        </head>
          <body>
            <h1>Buildy v{__VERSION__}</h1>
            <table>
              <tr><th>id</th><th>repository</th><th>created</th><th>running</th></tr>
              {builds}
            </table>
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

    builds = BuildManager()

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
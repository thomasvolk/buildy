#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import Popen
import json
from dataclasses import dataclass, asdict
import uuid
import tempfile

builds = dict()

@dataclass
class Repository:
    url: str
    branch: str
    tag: str

class Build:
    def __init__(self, repo):
        self.repo = repo 
        self.__process = Popen('echo "start process $$"; sleep 20; echo "end process $$"', shell=True)
        self.id = str(uuid.uuid4())

    @property
    def running(self):
        return self.__process.poll() == None

    @property
    def json(self):
        return json.dumps(
            {
                "pid": self.id,
                "running": self.running,
                "repository": asdict(self.repo)
            }
        )

class BuildyServer(BaseHTTPRequestHandler):
    def __split_path(self):
        return self.path[1:].split('/')

    def do_POST(self):
        path = self.__split_path()
        if(path == ['build']):
            content_length = int(self.headers['Content-Length'])
            build_setup = json.loads(self.rfile.read(content_length).decode('utf-8'))
            self._start_build(build_setup)
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()

    def _start_build(self, build_setup):
        self.send_response(201)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        build = Build(Repository(build_setup.get("url"), build_setup.get("banch"), build_setup.get("tag"))) 
        builds[build.id] = build
        self.wfile.write(bytes(json.dumps({"id": build.id}), "utf-8"))

    def do_GET(self):
        path = self.__split_path()
        if(path == ['']):
            pass
        elif(path[0] == 'build'):
            self._get_build(path[1])
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()

    def _get_build(self, id):
        build = builds.get(id)
        if(build == None):
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(build.json, "utf-8"))


hostName = "localhost"
serverPort = 9000
build_folder = tempfile.mkdtemp("buildy")

if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), BuildyServer)
    print("Buildy server started http://%s:%s" % (hostName, serverPort))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import Popen
import json
from dataclasses import dataclass, asdict
import uuid
import tempfile
from functools import partial
import os
import datetime

@dataclass
class Repository:
    url: str
    branch: str
    tag: str

class Build:
    def __init__(self, dir, repo):
        self.repo = repo 
        self.id = str(uuid.uuid4())
        self.dir = os.path.join(dir, self.id)
        cmd = f"""cd {self.dir} && git clone {self.repo.url} ."""
        if self.repo.tag != None:
            cmd += f" && git checkout {self.repo.tag}"
        if self.repo.branch != None:
            cmd += f" && git checkout {self.repo.branch}"

        cmd += " && make"
        os.makedirs(self.dir)
        self.__process = Popen(cmd, shell=True)
        self.creation_time = datetime.datetime.now()

    @property
    def running(self):
        return self.__process.poll() == None


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
        build = Build(self.dir,
          Repository(build_setup.get("url"), build_setup.get("branch"), build_setup.get("tag"))
        ) 
        self.builds[build.id] = build
        self.wfile.write(bytes(json.dumps({"id": build.id}), "utf-8"))

    def do_GET(self):
        path = self.__split_path()
        if(path == ['']):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            builds = "".join(
                [ f"<tr><td>{b.id}</td><td>{b.repo.url}</td><td>{b.creation_time}</td><td>{b.running}</td></tr>"
                  for b in self.builds.values() ]
            )
            self.wfile.write(bytes(f"""<html>
            <head>
              <title>Buildy</title>
              <style>
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
              <h1>Buildy</h1>
              <table>
                <tr><th>id</th><th>url</th><th>created</th><th>running</th></tr>
                {builds}
              </table>
            </body>
            </html>""", "utf-8"))
        elif(path[0] == 'build'):
            if len(path) > 1:
                self._get_build(path[1])
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(bytes(json.dumps([b.dict for b in self.builds.values()]), "utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()

    def _get_build(self, id):
        build = self.builds.get(id)
        if(build == None):
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(build.json, "utf-8"))


if __name__ == "__main__":        
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port",
                  help="server port", default="9000")
    parser.add_option("-H", "--host", dest="host_name",
                  help="server host name", default="localhost")
    parser.add_option("-d", "--directory", dest="directory",
                  help="server directory", default=tempfile.mkdtemp("buildy"))

    (options, args) = parser.parse_args()

    hostName = options.host_name
    serverPort = int(options.port)
    build_folder = options.directory

    builds = dict()

    handler = partial(BuildyHandler, builds, build_folder)
    webServer = HTTPServer((hostName, serverPort), handler)
    print(f"Buildy server started http://{hostName}:{serverPort} - dir: {build_folder}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        webServer.server_close()
        print("Buildy server stopped")
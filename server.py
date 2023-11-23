from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Lock

l = Lock()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith("/sneed/"): return
        id = self.path.split("/sneed/")[1]
        data = self.rfile.read(int(self.headers["Content-Length"]))
        with l and open(f"log.{id}.jsonl", "ab") as f:
            f.write(data)
            f.write(bytes("\n", "utf8"))
        self.send_response(200)
        self.send_header("Content-Length", "3")
        self.send_header("Access-Control-Allow-Origin", "https://discord.com")
        self.end_headers()
        self.wfile.write(bytes("K.\n", "utf8"))

print("started server at port 6969")
ThreadingHTTPServer(('', 6969), Handler).serve_forever()

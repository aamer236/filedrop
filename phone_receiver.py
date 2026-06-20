#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import html
import mimetypes
import socket
import time
import urllib.parse


UPLOAD_DIR = Path("uploads")
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024


def local_ip_addresses():
    addresses = set()
    hostname = socket.gethostname()

    try:
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addresses.add(item[4][0])
    except socket.gaierror:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    return sorted(ip for ip in addresses if not ip.startswith("127."))


def unique_path(directory, filename):
    safe_name = Path(filename).name.strip() or "uploaded_file"
    target = directory / safe_name

    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    counter = 1

    while True:
        candidate = directory / f"{stem}_{timestamp}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def parse_content_disposition(header):
    parts = [part.strip() for part in header.split(";")]
    values = {}

    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip().lower()] = value.strip().strip('"')

    return values


def parse_multipart(body, content_type):
    marker = "boundary="
    if marker not in content_type:
        raise ValueError("missing multipart boundary")

    boundary = content_type.split(marker, 1)[1].split(";", 1)[0].strip().strip('"')
    delimiter = b"--" + boundary.encode()
    files = []

    for part in body.split(delimiter):
        if not part or part == b"--":
            continue

        if part.startswith(b"\r\n"):
            part = part[2:]

        if part.endswith(b"--"):
            part = part[:-2]
        if part.endswith(b"\r\n"):
            part = part[:-2]

        header_bytes, separator, payload = part.partition(b"\r\n\r\n")
        if not separator:
            continue

        headers = {}
        for line in header_bytes.decode("utf-8", errors="replace").split("\r\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        disposition = headers.get("content-disposition", "")
        disposition_values = parse_content_disposition(disposition)
        filename = disposition_values.get("filename")

        if not filename:
            continue

        files.append((filename, payload))

    return files


class PhoneReceiverHandler(BaseHTTPRequestHandler):
    server_version = "AirdropPhoneReceiver/1.0"

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            self.send_upload_page()
            return

        if parsed.path == "/files":
            self.send_files_page()
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/upload":
            self.send_error(404, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        content_type = self.headers.get("Content-Type", "")

        if content_length <= 0:
            self.send_error(400, "Empty upload")
            return

        if content_length > MAX_UPLOAD_SIZE:
            self.send_error(413, "Upload too large")
            return

        body = self.rfile.read(content_length)

        try:
            files = parse_multipart(body, content_type)
        except ValueError as exc:
            self.send_error(400, str(exc))
            return

        if not files:
            self.send_error(400, "No files found in upload")
            return

        UPLOAD_DIR.mkdir(exist_ok=True)
        saved_files = []

        for filename, payload in files:
            target = unique_path(UPLOAD_DIR, filename)
            target.write_bytes(payload)
            saved_files.append(target)
            print(f"saved {target} ({len(payload)} bytes)")

        self.send_response(303)
        self.send_header("Location", f"/files?saved={len(saved_files)}")
        self.end_headers()

    def send_upload_page(self):
        content = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Airdrop Receiver</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #101418; color: #eef2f5; }
    main { width: min(92vw, 520px); }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { color: #a9b4bf; line-height: 1.5; }
    form { margin-top: 24px; display: grid; gap: 14px; }
    input, button, a { font: inherit; }
    input[type=file] { padding: 18px; border: 1px dashed #4b6478; border-radius: 10px; width: 100%; box-sizing: border-box; }
    button, a { border: 0; border-radius: 10px; padding: 14px 16px; background: #32d583; color: #08120d; font-weight: 700; text-align: center; text-decoration: none; }
    a { display: block; margin-top: 10px; background: #26313a; color: #eef2f5; }
  </style>
</head>
<body>
  <main>
    <h1>Send files to laptop</h1>
    <p>Select files from your phone. They will be saved on the laptop in the <code>uploads/</code> folder.</p>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="files" multiple required>
      <button type="submit">Upload</button>
    </form>
    <a href="/files">View uploaded files</a>
  </main>
</body>
</html>
"""
        self.send_html(content)

    def send_files_page(self):
        UPLOAD_DIR.mkdir(exist_ok=True)
        files = sorted(UPLOAD_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
        saved = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("saved", ["0"])[0]
        escaped_items = []

        for path in files:
            stat = path.stat()
            size = f"{stat.st_size:,} bytes"
            escaped_items.append(f"<li>{html.escape(path.name)} <span>{size}</span></li>")

        message = ""
        if saved != "0":
            message = f"<p class='ok'>Saved {html.escape(saved)} file(s).</p>"

        content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Uploaded Files</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; background: #101418; color: #eef2f5; }}
    main {{ width: min(92vw, 680px); margin: 40px auto; }}
    h1 {{ margin: 0 0 16px; }}
    .ok {{ color: #32d583; }}
    ul {{ list-style: none; padding: 0; display: grid; gap: 10px; }}
    li {{ display: flex; justify-content: space-between; gap: 16px; padding: 14px; background: #182028; border-radius: 10px; }}
    span {{ color: #a9b4bf; }}
    a {{ display: inline-block; margin-top: 16px; color: #32d583; }}
  </style>
</head>
<body>
  <main>
    <h1>Uploaded files</h1>
    {message}
    <ul>{''.join(escaped_items) or '<li>No files uploaded yet.</li>'}</ul>
    <a href="/">Upload more</a>
  </main>
</body>
</html>
"""
        self.send_html(content)

    def send_html(self, content):
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    parser = argparse.ArgumentParser(description="Receive files from an Android phone over Wi-Fi.")
    parser.add_argument("--host", default="0.0.0.0", help="host/IP to bind to")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on")
    args = parser.parse_args()

    UPLOAD_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), PhoneReceiverHandler)

    print(f"saving uploads to: {UPLOAD_DIR.resolve()}")
    print("open one of these URLs on your Android phone while on the same Wi-Fi:")
    for ip in local_ip_addresses():
        print(f"  http://{ip}:{args.port}")
    print(f"local test URL: http://127.0.0.1:{args.port}")
    print("press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping receiver")
    finally:
        server.server_close()


if __name__ == "__main__":
    mimetypes.init()
    main()

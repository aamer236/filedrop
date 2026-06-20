#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
import argparse
import hmac
import html
import json
import mimetypes
import re
import secrets
import socket
import ssl
import subprocess
import time
import urllib.parse

UPLOAD_DIR = Path("uploads")
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024
SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._ -]+")
CONFIG_PATH = Path("config.json")

# Premium UI Templates
LOGIN_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connect - AirDrop Share</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-color: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.15);
      --danger: #ef4444;
      font-family: 'Outfit', system-ui, -apple-system, sans-serif;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at 50% 50%, #111827 0%, var(--bg-color) 100%);
      color: var(--text-main);
      overflow-x: hidden;
      box-sizing: border-box;
    }}
    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 24px;
      padding: 40px 30px;
      width: min(92vw, 400px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35), 0 0 50px var(--accent-glow);
      text-align: center;
      box-sizing: border-box;
      transition: all 0.3s ease;
    }}
    .card:hover {{
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.45), 0 0 60px rgba(16, 185, 129, 0.25);
    }}
    .icon {{
      font-size: 48px;
      margin-bottom: 20px;
      display: inline-block;
      animation: float 4s ease-in-out infinite;
    }}
    @keyframes float {{
      0%, 100% {{ transform: translateY(0); }}
      50% {{ transform: translateY(-8px); }}
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #fff 30%, #a7f3d0 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    p {{
      color: var(--text-muted);
      font-size: 15px;
      line-height: 1.6;
      margin: 0 0 30px;
    }}
    .input-group {{
      margin-bottom: 24px;
      text-align: left;
    }}
    label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 8px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    input[type="password"] {{
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      background: rgba(31, 41, 55, 0.5);
      color: var(--text-main);
      box-sizing: border-box;
      font-size: 16px;
      transition: all 0.2s ease;
    }}
    input:focus {{
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }}
    button {{
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 12px;
      background: var(--accent);
      color: #064e3b;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
    }}
    button:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
    }}
    button:active {{
      transform: translateY(0);
    }}
    .error {{
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.25);
      color: #fca5a5;
      padding: 12px;
      border-radius: 12px;
      margin-bottom: 20px;
      font-size: 14px;
      text-align: left;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">🔒</div>
    <h1>AirDrop Share</h1>
    <p>Enter the access token or passcode to connect to the laptop.</p>
    {error_html}
    <form method="post" action="/login">
      <div class="input-group">
        <label for="token">Passcode or Token</label>
        <input type="password" id="token" name="token" placeholder="Enter token" required autofocus autocomplete="off">
      </div>
      <button type="submit">Unlock Server</button>
    </form>
  </div>
</body>
</html>
"""

UPLOAD_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AirDrop Share - Send Files</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-color: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.15);
      --accent-secondary: #06b6d4;
      font-family: 'Outfit', system-ui, -apple-system, sans-serif;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at 50% 50%, #111827 0%, var(--bg-color) 100%);
      color: var(--text-main);
      overflow-y: auto;
      padding: 20px 0;
      box-sizing: border-box;
    }}
    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 24px;
      padding: 30px;
      width: min(92vw, 500px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35), 0 0 50px rgba(6, 182, 212, 0.05);
      box-sizing: border-box;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }}
    .logo-area {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .logo-icon {{
      font-size: 28px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 800;
      background: linear-gradient(135deg, #fff 40%, var(--accent-secondary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .badge {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      padding: 6px 12px;
      border-radius: 30px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .badge-secure {{
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.2);
    }}
    .drop-zone {{
      border: 2px dashed rgba(255, 255, 255, 0.15);
      border-radius: 16px;
      padding: 40px 20px;
      text-align: center;
      cursor: pointer;
      background: rgba(31, 41, 55, 0.3);
      transition: all 0.23s ease;
      position: relative;
    }}
    .drop-zone:hover, .drop-zone.dragover {{
      border-color: var(--accent);
      background: rgba(16, 185, 129, 0.04);
      transform: scale(1.01);
    }}
    .drop-icon {{
      font-size: 40px;
      margin-bottom: 12px;
      display: inline-block;
      transition: transform 0.3s ease;
    }}
    .drop-zone:hover .drop-icon {{
      transform: translateY(-4px);
    }}
    .drop-text-primary {{
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 6px;
    }}
    .drop-text-secondary {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    input[type="file"] {{
      display: none;
    }}
    .file-list-container {{
      margin-top: 20px;
      max-height: 180px;
      overflow-y: auto;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      background: rgba(0, 0, 0, 0.2);
      display: none;
    }}
    .file-list-container::-webkit-scrollbar {{
      width: 6px;
    }}
    .file-list-container::-webkit-scrollbar-thumb {{
      background: rgba(255, 255, 255, 0.15);
      border-radius: 3px;
    }}
    .file-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 14px;
    }}
    .file-item:last-child {{
      border-bottom: none;
    }}
    .file-name {{
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 70%;
    }}
    .file-size {{
      color: var(--text-muted);
      font-size: 12px;
    }}
    .upload-btn {{
      width: 100%;
      padding: 15px;
      border: none;
      border-radius: 14px;
      background: linear-gradient(135deg, var(--accent) 0%, #059669 100%);
      color: #064e3b;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-top: 20px;
      box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2);
      display: none;
    }}
    .upload-btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 22px rgba(16, 185, 129, 0.4);
    }}
    .progress-container {{
      margin-top: 20px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 10px;
      overflow: hidden;
      display: none;
      border: 1px solid var(--card-border);
    }}
    .progress-bar {{
      height: 12px;
      background: linear-gradient(90deg, var(--accent) 0%, var(--accent-secondary) 100%);
      width: 0%;
      transition: width 0.1s linear;
    }}
    .progress-info {{
      display: flex;
      justify-content: space-between;
      margin-top: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
    }}
    .links-area {{
      margin-top: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid var(--card-border);
      padding-top: 16px;
    }}
    a {{
      color: var(--accent-secondary);
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      transition: color 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    a:hover {{
      color: #22d3ee;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="logo-area">
        <span class="logo-icon">🚀</span>
        <h1>AirDrop Share</h1>
      </div>
      <span class="badge badge-secure">
        <span style="display:inline-block; width:6px; height:6px; background:#10b981; border-radius:50%"></span>
        {security_label}
      </span>
    </div>
    
    <div class="drop-zone" id="drop-zone">
      <span class="drop-icon">📤</span>
      <div class="drop-text-primary">Drag & drop files here</div>
      <div class="drop-text-secondary">or click to browse from device</div>
      <input type="file" id="file-input" name="files" multiple>
    </div>

    <div class="file-list-container" id="file-list-container">
      <div id="file-list"></div>
    </div>

    <button class="upload-btn" id="upload-btn">Upload Files</button>

    <div class="progress-container" id="progress-container">
      <div class="progress-bar" id="progress-bar"></div>
      <div class="progress-info">
        <span id="progress-status">Uploading...</span>
        <span id="progress-percent">0%</span>
      </div>
    </div>

    <div class="links-area">
      <a href="{files_url}">📂 View Files</a>
      <a href="/logout" style="color:var(--text-muted); font-size:12px">Lock Session</a>
    </div>
  </div>

  <script>
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const fileListContainer = document.getElementById('file-list-container');
    const fileList = document.getElementById('file-list');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');

    let selectedFiles = [];

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', handleFileSelection);

    ['dragenter', 'dragover'].forEach(eventName => {{
      dropZone.addEventListener(eventName, (e) => {{
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('dragover');
      }}, false);
    }});

    ['dragleave', 'drop'].forEach(eventName => {{
      dropZone.addEventListener(eventName, (e) => {{
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('dragover');
      }}, false);
    }});

    dropZone.addEventListener('drop', (e) => {{
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files.length > 0) {{
        fileInput.files = files;
        handleFileSelection();
      }}
    }});

    function formatBytes(bytes) {{
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }}

    function handleFileSelection() {{
      selectedFiles = Array.from(fileInput.files);
      if (selectedFiles.length === 0) {{
        fileListContainer.style.display = 'none';
        uploadBtn.style.display = 'none';
        return;
      }}

      fileList.innerHTML = '';
      selectedFiles.forEach(file => {{
        const item = document.createElement('div');
        item.className = 'file-item';
        
        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = file.name;
        
        const size = document.createElement('span');
        size.className = 'file-size';
        size.textContent = formatBytes(file.size);
        
        item.appendChild(name);
        item.appendChild(size);
        fileList.appendChild(item);
      }});

      fileListContainer.style.display = 'block';
      uploadBtn.style.display = 'block';
      
      progressContainer.style.display = 'none';
      progressBar.style.width = '0%';
      progressPercent.textContent = '0%';
      progressBar.style.backgroundColor = '';
    }}

    uploadBtn.addEventListener('click', () => {{
      if (selectedFiles.length === 0) return;

      const formData = new FormData();
      selectedFiles.forEach(file => {{
        formData.append('files', file);
      }});

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '{upload_action_url}', true);

      xhr.upload.addEventListener('progress', (e) => {{
        if (e.lengthComputable) {{
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          progressBar.style.width = percentComplete + '%';
          progressPercent.textContent = percentComplete + '%';
          progressStatus.textContent = `Uploading (${{formatBytes(e.loaded)}} / ${{formatBytes(e.total)}})...`;
        }}
      }});

      xhr.onload = function() {{
        if (xhr.status >= 200 && xhr.status < 400) {{
          progressStatus.textContent = 'Upload complete! Redirecting...';
          setTimeout(() => {{
            window.location.href = '/files?saved=' + selectedFiles.length;
          }}, 600);
        }} else {{
          progressStatus.textContent = 'Upload failed. Error ' + xhr.status;
          progressBar.style.backgroundColor = '#ef4444';
        }}
      }};

      xhr.onerror = function() {{
        progressStatus.textContent = 'Upload error. Network error.';
        progressBar.style.backgroundColor = '#ef4444';
      }};

      uploadBtn.style.display = 'none';
      progressContainer.style.display = 'block';
      progressStatus.textContent = 'Starting upload...';

      xhr.send(formData);
    }});
  </script>
</body>
</html>
"""

FILES_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Uploaded Files - AirDrop Share</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-color: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #10b981;
      --accent-secondary: #06b6d4;
      font-family: 'Outfit', system-ui, -apple-system, sans-serif;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at 50% 50%, #111827 0%, var(--bg-color) 100%);
      color: var(--text-main);
      overflow-y: auto;
      padding: 40px 0;
      box-sizing: border-box;
    }}
    .card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 24px;
      padding: 30px;
      width: min(92vw, 580px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35), 0 0 50px rgba(6, 182, 212, 0.05);
      box-sizing: border-box;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 800;
      background: linear-gradient(135deg, #fff 40%, var(--accent-secondary) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .ok-message {{
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #34d399;
      padding: 12px 16px;
      border-radius: 12px;
      margin-bottom: 20px;
      font-size: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      animation: fadeIn 0.3s ease;
    }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(-4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .file-list {{
      display: grid;
      gap: 12px;
      max-height: 400px;
      overflow-y: auto;
      padding-right: 4px;
    }}
    .file-list::-webkit-scrollbar {{
      width: 6px;
    }}
    .file-list::-webkit-scrollbar-track {{
      background: rgba(255, 255, 255, 0.02);
      border-radius: 30px;
    }}
    .file-list::-webkit-scrollbar-thumb {{
      background: rgba(255, 255, 255, 0.15);
      border-radius: 30px;
    }}
    .file-list::-webkit-scrollbar-thumb:hover {{
      background: rgba(255, 255, 255, 0.3);
    }}
    .file-card {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.04);
      border-radius: 14px;
      transition: all 0.2s ease;
    }}
    .file-card:hover {{
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.08);
      transform: translateX(2px);
    }}
    .file-details {{
      display: flex;
      align-items: center;
      gap: 12px;
      max-width: 75%;
    }}
    .file-icon {{
      font-size: 24px;
    }}
    .file-info {{
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }}
    .file-name {{
      font-weight: 600;
      font-size: 15px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: var(--text-main);
    }}
    .file-meta {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    .empty-state {{
      text-align: center;
      padding: 40px 0;
      color: var(--text-muted);
      font-size: 15px;
    }}
    .empty-icon {{
      font-size: 48px;
      margin-bottom: 12px;
      display: block;
    }}
    .btn-action {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 20px;
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
      border-radius: 12px;
      font-weight: 600;
      font-size: 14px;
      text-decoration: none;
      transition: all 0.2s ease;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .btn-action:hover {{
      background: rgba(255, 255, 255, 0.12);
      transform: translateY(-1px);
    }}
    .btn-primary {{
      background: var(--accent);
      color: #064e3b;
      border: none;
    }}
    .btn-primary:hover {{
      background: #34d399;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
    }}
    .footer-actions {{
      display: flex;
      justify-content: space-between;
      margin-top: 24px;
      border-top: 1px solid var(--card-border);
      padding-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>Uploaded Files</h1>
      <span style="font-size:13px; color:var(--text-muted); font-weight: 600;">{total_count} items</span>
    </div>

    {message_html}

    <div class="file-list">
      {file_items}
    </div>

    <div class="footer-actions">
      <a href="/" class="btn-action btn-primary">➕ Upload More</a>
      <a href="/logout" class="btn-action">🔒 Lock Session</a>
    </div>
  </div>
</body>
</html>
"""


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


def sanitize_file_name(filename):
    safe_name = Path(filename).name.strip() or "uploaded_file"
    safe_name = SAFE_NAME_PATTERN.sub("_", safe_name)
    safe_name = safe_name.lstrip(".") or "uploaded_file"
    return safe_name[:180]


def unique_path(directory, filename):
    safe_name = sanitize_file_name(filename)
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


def get_file_icon(name):
    suffix = Path(name).suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".heic"]:
        return "🖼️"
    elif suffix in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
        return "🎥"
    elif suffix in [".mp3", ".wav", ".ogg", ".m4a", ".flac"]:
        return "🎵"
    elif suffix in [".zip", ".tar", ".gz", ".rar", ".7z"]:
        return "📦"
    elif suffix in [".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".md"]:
        return "📄"
    elif suffix in [".py", ".cpp", ".h", ".json", ".sh", ".js", ".css", ".html"]:
        return "⚙️"
    return "📁"


def generate_certificates(certfile, keyfile):
    cert_path = Path(certfile)
    key_path = Path(keyfile)
    if not cert_path.exists() or not key_path.exists():
        print(f"SSL certificate or key missing. Generating self-signed TLS certs...")
        try:
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes", "-days", "365",
                "-keyout", str(key_path), "-out", str(cert_path),
                "-subj", "/CN=airdrop-local"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Generated certificates: {certfile} & {keyfile}")
        except Exception as e:
            print(f"Error generating certs using OpenSSL: {e}")
            raise


def load_or_create_config(config_path=CONFIG_PATH):
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                if "token" not in config:
                    config["token"] = secrets.token_urlsafe(24)
                if "port" not in config:
                    config["port"] = 8080
                if "host" not in config:
                    config["host"] = "0.0.0.0"
                if "insecure_http" not in config:
                    config["insecure_http"] = False
                with open(config_path, "w") as fw:
                    json.dump(config, fw, indent=2)
                return config
        except Exception as e:
            print(f"Error reading {config_path}: {e}. Re-creating default configuration.")

    config = {
        "token": secrets.token_urlsafe(24),
        "port": 8080,
        "host": "0.0.0.0",
        "insecure_http": False
    }
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving {config_path}: {e}")
    return config


class PhoneReceiverHandler(BaseHTTPRequestHandler):
    server_version = "AirDropPhoneReceiver/3.0"

    def log_message(self, format, *args):
        # Silence default log messages slightly or print in simple format
        print(f"{self.client_address[0]} - {format % args}")

    def get_cookie_token(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        try:
            cookie = SimpleCookie(cookie_header)
            if "session_token" in cookie:
                return cookie["session_token"].value
        except Exception:
            pass
        return None

    def is_authenticated(self):
        # 1. Check Query parameter
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        url_token = query.get("token", [""])[0]
        expected = self.server.upload_token
        
        if url_token and hmac.compare_digest(url_token, expected):
            return True
            
        # 2. Check Cookie
        cookie_token = self.get_cookie_token()
        if cookie_token and hmac.compare_digest(cookie_token, expected):
            return True
            
        return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        url_token = query.get("token", [""])[0]
        expected = self.server.upload_token

        # If a valid token is in query parameters, save it to cookie and redirect to clean URL
        if url_token and hmac.compare_digest(url_token, expected):
            self.send_response(303)
            cookie_str = f"session_token={expected}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000"
            if self.server.using_https:
                cookie_str += "; Secure"
            self.send_header("Set-Cookie", cookie_str)
            
            # Rebuild path without token query param
            new_query = {k: v for k, v in query.items() if k != "token"}
            new_query_str = urllib.parse.urlencode(new_query, doseq=True)
            clean_path = parsed.path
            if new_query_str:
                clean_path += "?" + new_query_str
            self.send_header("Location", clean_path)
            self.end_headers()
            return

        # Logout handling
        if parsed.path == "/logout":
            self.send_response(303)
            # Expire cookie
            cookie_str = "session_token=deleted; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            if self.server.using_https:
                cookie_str += "; Secure"
            self.send_header("Set-Cookie", cookie_str)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # Authentication filter
        if not self.is_authenticated():
            if parsed.path == "/login":
                self.send_login_page()
            else:
                # Redirect to login
                self.send_response(303)
                self.send_header("Location", "/login")
                self.end_headers()
            return

        # Authenticated requests
        if parsed.path == "/":
            self.send_upload_page()
            return

        if parsed.path == "/files":
            self.send_files_page()
            return

        if parsed.path == "/login":
            # Already authenticated, redirect to home
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        # Login request handler
        if parsed.path == "/login":
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8", errors="ignore")
            post_data = urllib.parse.parse_qs(body)
            entered_token = post_data.get("token", [""])[0]
            
            expected = self.server.upload_token
            if hmac.compare_digest(entered_token, expected):
                self.send_response(303)
                cookie_str = f"session_token={expected}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000"
                if self.server.using_https:
                    cookie_str += "; Secure"
                self.send_header("Set-Cookie", cookie_str)
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self.send_login_page(error="Invalid passcode or token.")
            return

        # File upload requires authentication
        if not self.is_authenticated():
            self.send_error(403, "Authentication required")
            return

        if parsed.path != "/upload":
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

        # AJAX requests expect a simple success status or redirect URL
        self.send_response(200)
        self.send_security_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True, "count": len(saved_files)}).encode("utf-8"))

    def send_login_page(self, error=""):
        error_html = ""
        if error:
            error_html = f'<div class="error">{html.escape(error)}</div>'
        content = LOGIN_PAGE_TEMPLATE.format(error_html=error_html)
        self.send_html(content)

    def send_upload_page(self):
        security_label = "HTTPS SECURE" if self.server.using_https else "HTTP INSECURE"
        upload_action_url = "/upload"
        files_url = "/files"

        content = UPLOAD_PAGE_TEMPLATE.format(
            security_label=security_label,
            upload_action_url=upload_action_url,
            files_url=files_url
        )
        self.send_html(content)

    def send_files_page(self):
        UPLOAD_DIR.mkdir(exist_ok=True)
        files = sorted(UPLOAD_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
        saved = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("saved", ["0"])[0]
        
        escaped_items = []
        for path in files:
            if not path.is_file():
                continue
            stat = path.stat()
            size = stat.st_size
            size_formatted = f"{size:,} bytes"
            if size >= 1024*1024*1024:
                size_formatted = f"{size / (1024*1024*1024):.2f} GB"
            elif size >= 1024*1024:
                size_formatted = f"{size / (1024*1024):.2f} MB"
            elif size >= 1024:
                size_formatted = f"{size / 1024:.2f} KB"

            icon = get_file_icon(path.name)
            escaped_items.append(f"""
            <div class="file-card">
              <div class="file-details">
                <span class="file-icon">{icon}</span>
                <div class="file-info">
                  <span class="file-name" title="{html.escape(path.name)}">{html.escape(path.name)}</span>
                  <span class="file-meta">{html.escape(size_formatted)}</span>
                </div>
              </div>
            </div>
            """)

        message_html = ""
        if saved != "0":
            message_html = f"""
            <div class="ok-message">
              <span>✅</span> Saved {html.escape(saved)} file(s) successfully!
            </div>
            """

        content = FILES_PAGE_TEMPLATE.format(
            total_count=len(escaped_items),
            message_html=message_html,
            file_items="".join(escaped_items) or '<div class="empty-state"><span class="empty-icon">📂</span>No files uploaded yet.</div>',
        )
        self.send_html(content)

    def send_html(self, content):
        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_security_headers()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")


def main():
    global UPLOAD_DIR

    parser = argparse.ArgumentParser(description="Receive files from an Android phone over Wi-Fi.")
    parser.add_argument("--host", help="host/IP to bind to (overrides config)")
    parser.add_argument("--port", type=int, help="port to listen on (overrides config)")
    parser.add_argument("--upload-dir", default=str(UPLOAD_DIR), help="directory where uploads are saved")
    parser.add_argument("--token", help="upload token/passcode (overrides config)")
    parser.add_argument("--certfile", help="TLS certificate file for HTTPS")
    parser.add_argument("--keyfile", help="TLS private key file for HTTPS")
    parser.add_argument("--insecure-http", action="store_true", help="allow plain HTTP without TLS")
    args = parser.parse_args()

    UPLOAD_DIR = Path(args.upload_dir)
    UPLOAD_DIR.mkdir(exist_ok=True)

    # Load persistent configuration or create default
    config = load_or_create_config()

    # Resolve settings (CLI overrides Config)
    host = args.host or config.get("host", "0.0.0.0")
    port = args.port or config.get("port", 8080)
    token = args.token or config.get("token")

    # If the token is updated via CLI, save it back to config
    if args.token and args.token != config.get("token"):
        config["token"] = args.token
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    if bool(args.certfile) != bool(args.keyfile):
        parser.error("--certfile and --keyfile must be used together")

    using_https = not (args.insecure_http or config.get("insecure_http", False))
    certfile = args.certfile
    keyfile = args.keyfile

    if using_https:
        if not certfile:
            certfile = "cert.pem"
        if not keyfile:
            keyfile = "key.pem"
        # Automatically generate certs if they don't exist
        generate_certificates(certfile, keyfile)

    server = ThreadingHTTPServer((host, port), PhoneReceiverHandler)
    server.upload_token = token
    server.using_https = using_https

    scheme = "https" if using_https else "http"

    if using_https:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certfile=certfile, keyfile=keyfile)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        except Exception as e:
            print(f"Error starting HTTPS: {e}")
            print("Fallback: Please verify your cert.pem and key.pem certificates, or run with --insecure-http.")
            return

    print(f"Saving uploads to: {UPLOAD_DIR.resolve()}")
    if not using_https:
        print("WARNING: Running over plain HTTP. Use only on trusted local networks.")
        
    print(f"Configuration file: {CONFIG_PATH.resolve()}")
    print(f"Access Token: {token}")
    print("----------------------------------------------------------------------")
    print("Open one of these URLs on your phone to connect (cookie will remember you):")
    for ip in local_ip_addresses():
        print(f"  {scheme}://{ip}:{port}/?token={token}")
        print(f"  Or simply visit: {scheme}://{ip}:{port}/ and log in")
    print("----------------------------------------------------------------------")
    print(f"Local test URL: {scheme}://127.0.0.1:{port}/?token={token}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping receiver")
    finally:
        server.server_close()


if __name__ == "__main__":
    mimetypes.init()
    main()

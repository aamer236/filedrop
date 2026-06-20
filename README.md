# filedrop

A secure, self-hosted file transfer tool. Send files from your phone to your laptop over Wi-Fi with a beautiful web interface, HTTPS encryption, and persistent session authentication.

## Features

- **Premium Web UI** — Gorgeous dark glassmorphic interface with drag-and-drop upload, progress bars, and file-type icons
- **Cookie-Based Authentication** — Log in once with a passcode; your session persists for a year
- **Auto-Generated HTTPS** — Self-signed TLS certificates are created automatically on first run
- **Persistent Configuration** — Settings (token, port, host) are saved in `config.json`
- **Background Service** — Runs as a systemd user service — always on, auto-restarts on failure
- **ngrok Support** — Expose over a trusted public HTTPS URL for sharing with others

## Quick Start

### 1. Clone and run

```bash
git clone https://github.com/yourusername/filedrop.git
cd filedrop
python3 phone_receiver.py
```

On first run, the server will:
- Generate a `config.json` with a random access token
- Generate self-signed TLS certificates (`cert.pem` & `key.pem`)
- Print the access URL to your terminal

### 2. Connect from your phone

Open the printed URL on your phone while on the same Wi-Fi network:

```
https://<laptop-ip>:8080/?token=<your-token>
```

Or visit `https://<laptop-ip>:8080/` and enter the token on the login page.

> **Note:** Your browser will show a certificate warning for the self-signed cert. Tap **Advanced → Proceed** to continue. This only needs to be done once per device.

Files are saved to the `uploads/` directory.

### 3. Change the passcode

Edit `config.json` and set `token` to something easy to remember:

```json
{
  "token": "my-simple-pin",
  "port": 8080,
  "host": "0.0.0.0",
  "insecure_http": false
}
```

## Run as a Background Service (systemd)

Create `~/.config/systemd/user/airdrop.service`:

```ini
[Unit]
Description=Airdrop Phone Receiver Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/filedrop
ExecStart=/usr/bin/python3 -u /path/to/filedrop/phone_receiver.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Then enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now airdrop.service
```

To keep it running even after logout:

```bash
loginctl enable-linger $USER
```

## Expose Over Public HTTPS (ngrok)

To share with people outside your local network using a trusted HTTPS URL:

1. Sign up at [ngrok.com](https://ngrok.com) and add your authtoken:
   ```bash
   npx ngrok config add-authtoken <YOUR_TOKEN>
   ```

2. Set `"insecure_http": true` in `config.json` (ngrok handles TLS)

3. Start the tunnel:
   ```bash
   npx ngrok http 8080
   ```

4. Share the generated `https://xxxx.ngrok-free.app` URL with anyone.

## CLI Options

```
python3 phone_receiver.py [OPTIONS]

--host HOST          Host/IP to bind to (overrides config)
--port PORT          Port to listen on (overrides config)
--upload-dir DIR     Directory where uploads are saved (default: uploads/)
--token TOKEN        Access token/passcode (overrides config)
--certfile FILE      TLS certificate file for HTTPS
--keyfile FILE       TLS private key file for HTTPS
--insecure-http      Allow plain HTTP without TLS
```

## Build (C++ client/server)

For the legacy TCP file transfer:

```bash
g++ -std=c++17 -Wall -Wextra -pedantic server.cpp -o server
g++ -std=c++17 -Wall -Wextra -pedantic client.cpp -o client
```

```bash
./server              # Start receiver
./client <file> [ip]  # Send a file (defaults to 127.0.0.1)
```

# filedrop

Simple TCP file transfer over port `8080`.

## Android to laptop

Run the receiver on your laptop:

```bash
python3 phone_receiver.py
```

Open the printed `http://<laptop-ip>:8080` URL on your Android phone while both devices are on the same Wi-Fi. Pick files in the browser and upload them. Files are saved into:

```text
uploads/
```

If port `8080` is busy:

```bash
python3 phone_receiver.py --port 9090
```

## Build

```bash
g++ -std=c++17 -Wall -Wextra -pedantic server.cpp -o server
g++ -std=c++17 -Wall -Wextra -pedantic client.cpp -o client
```

## Use

Start the receiver:

```bash
./server
```

Send a file from another terminal:

```bash
./client <file_path> [server_ip]
```

If `server_ip` is omitted, the client sends to `127.0.0.1`.
The server saves incoming files as `received_<original_filename>`.

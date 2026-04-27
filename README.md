# Reliable HTTP Over UDP

A simple Python project that serves HTTP-style requests over a custom reliable UDP transport.

The transport layer adds reliability features on top of UDP, including a three-way handshake, checksums, stop-and-wait delivery, retransmission on timeout, duplicate handling, message chunking/reassembly, and graceful connection teardown.

## Project Structure

```text
.
├── server_main.py              # Starts the HTTP server over RUDP
├── client_main.py              # Sends sample HTTP requests to the server
├── browser_proxy.py            # Bridges normal browser TCP requests to the RUDP server
├── src/
│   ├── application/            # HTTP parser, client, and server logic
│   └── transport/              # Reliable UDP packet, checksum, socket, and network simulator
├── tests/                      # Transport and core tests
└── www/                        # Static HTML files served by the server
```

This project uses only the Python standard library for the application code.

## Running the Project

Start the RUDP HTTP server:

```bash
python server_main.py
```

In another terminal, run the sample client:

```bash
python client_main.py
```

The client sends example `GET`, `POST`, and unsupported-method requests to `127.0.0.1:8080`.

## Browser Proxy

Browsers speak HTTP over TCP, so use the proxy to forward browser requests to the RUDP server.

Start the server:

```bash
python server_main.py
```

Start the proxy in another terminal:

```bash
python browser_proxy.py
```

Then open:

```text
http://127.0.0.1:8081
```

## Running Tests

You can run individual test scripts directly, for example:

```bash
python tests/test_core.py
python tests/test_transport.py
```

## Notes

- The default server address is `127.0.0.1:8080`.
- Static files are served from the `www/` directory.
- `src/transport/network_sim.py` can simulate packet loss, corruption, and duplication for reliability testing.

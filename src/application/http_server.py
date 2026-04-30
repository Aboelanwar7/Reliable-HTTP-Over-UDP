import os
import socket
import threading
import queue
import time
from src.application.http_parser import HTTPParser
from src.transport.rudp_socket import RUDPSocket


class VirtualSocket:
    """
    A wrapper that mimics a standard Python socket.
    Instead of reading from the network, it reads from a thread-safe memory queue.
    """

    def __init__(self, real_socket, packet_queue):
        self.real_socket = real_socket
        self.queue = packet_queue
        self.timeout = 2.0

    def settimeout(self, t):
        self.timeout = t

    def gettimeout(self):
        return self.timeout

    def recvfrom(self, bufsize):
        try:
            # Block until the Dispatcher pushes a packet into this queue
            return self.queue.get(timeout=self.timeout)
        except queue.Empty:
            # Mimic standard socket timeout behavior perfectly
            raise socket.timeout("timed out")

    def sendto(self, data, addr):
        # Outbound traffic goes straight through the central real socket
        self.real_socket.sendto(data, addr)

    def bind(self, addr):
        pass  # The real socket is already bound by the dispatcher

    def close(self):
        pass  # Worker threads don't close the main server socket


class HTTPServer:
    def __init__(self, host, port, document_root="../../www"):
        self.addr = (host, port)
        self.document_root = document_root
        self.sessions = {}  # Maps Client IP/Port to their specific Queue
        self.sessions_lock = threading.Lock()  # Ensures thread safety for the dictionary
        self.session_timeout = 60 # Seconds before an idle connection is killed
        self.max_queue_size = 500 # Max packets allowed in a queue

    def run(self):
        # Create the ONE true central UDP socket
        central_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        central_socket.bind(self.addr)

        print(f"[Server] Dispatcher / Multiplexer listening on {self.addr[0]}:{self.addr[1]}")
        threading.Thread(target=self.reaper_loop, daemon=True).start()

        # The Main Dispatcher Loop
        while True:
            try:
                # Receive ALL traffic hitting the server
                data, client_addr = central_socket.recvfrom(4096)
                current_time = time.time()

                with self.sessions_lock:
                    if client_addr not in self.sessions:
                        # NEW CLIENT DETECTED (SYN Packet)
                        print(f"[Server] New connection from {client_addr}. Spinning up worker thread.")

                        # Create a dedicated memory queue for this client
                        client_queue = queue.Queue(maxsize=self.max_queue_size)
                        self.sessions[client_addr] = {
                            'queue': client_queue,
                            'last_active': current_time
                        }

                        # Push the initial SYN packet into the queue
                        client_queue.put((data, client_addr))

                        # Spawn the dedicated worker thread
                        worker = threading.Thread(
                            target=self.worker_loop,
                            args=(central_socket, client_queue, client_addr),
                            daemon=True
                        )
                        worker.start()
                    else:
                        try:
                            # EXISTING CLIENT: Route the packet to their specific queue
                            self.sessions[client_addr]['queue'].put_nowait((data, client_addr))
                            self.sessions[client_addr]['last_active'] = current_time
                        except queue.Full:
                            # DoS Protection: Drop the packet, don't crash the server
                            print(f"[Server] Warning: Queue full for {client_addr}. Dropping packet.")

            except Exception as e:
                print(f"[Server] Dispatcher error: {e}")

    def reaper_loop(self):
        """
        The Garbage Collector.
        Wakes up every 30 seconds, scans all active sessions, and deletes
        memory for any client that hasn't sent a packet in 60 seconds
        """
        while True:
            time.sleep(30)
            current_time = time.time()
            stale_clients = []

            with self.sessions_lock:
                for addr, session_data in self.sessions.items():
                    if current_time - session_data['last_active'] > self.session_timeout:
                        stale_clients.append(addr)

                for addr in stale_clients:
                    del self.sessions[addr]
                    print(f"[Reaper] Reclaimed memory. Deleted abandoned session for {addr}")

    def worker_loop(self, central_socket, client_queue, client_addr):
        """Dedicated thread for handling a specific client's RUDP & HTTP state."""
        thread_id = threading.get_ident()

        # Setup RUDP with Dependency Injection
        rudp_session = RUDPSocket()
        # Overwrite the default socket with Virtual Queue Socket
        rudp_session.sock = VirtualSocket(central_socket, client_queue)

        try:
            # Perform the 3-Way Handshake
            rudp_session.accept()

            # Receive the full HTTP payload reliably
            raw_request = rudp_session.recv()
            if not raw_request:
                return

            req_msg = HTTPParser.parse(raw_request)
            print(f"\n[Thread-{thread_id}] Processing {req_msg.method} request for {req_msg.path}")

            # Route request and send response
            response_bytes = self.handle_request(req_msg)
            rudp_session.send(response_bytes)

        except Exception as e:
            print(f"[Thread-{thread_id}] Error handling request: {e}")
        finally:
            # Teardown
            rudp_session.close()

            # Safely remove this client's queue from the Dispatcher's memory
            with self.sessions_lock:
                if client_addr in self.sessions:
                    del self.sessions[client_addr]

            print(f"[Thread-{thread_id}] Session closed and memory cleared for {client_addr}")

    def handle_request(self, req_msg) -> bytes:
        if req_msg.method == "GET":
            safe_path = os.path.normpath(req_msg.path).lstrip('/')
            if not safe_path or safe_path == "":
                safe_path = "index.html"

            file_path = os.path.join(self.document_root, safe_path)

            if os.path.exists(file_path) and os.path.isfile(file_path):
                content_type = HTTPParser.get_mime_type(file_path)

                with open(file_path, 'rb') as f:
                    content = f.read()
                    headers = {"Content-Type": content_type}
                    return HTTPParser.build_response(200, "OK", body=content, headers=headers)
            else:
                error_body = "<html><body><h1>404 Not Found</h1></body></html>"
                return HTTPParser.build_response(404, "NOT FOUND", body=error_body, headers={"Content-Type": "text/html"})

        elif req_msg.method == "POST":
            print(f"[Server] POST payload: {req_msg.body}")
            success_body = f"<html><body><h1>POST Data Received Successfully</h1><p>Your POST data was {req_msg.body}</p></body></html>"
            return HTTPParser.build_response(200, "OK", body=success_body, headers={"Content-Type": "text/html"})

        else:
            return HTTPParser.build_response(400, "BAD REQUEST", body="Unknown Method", headers={"Content-Type": "text/html"})
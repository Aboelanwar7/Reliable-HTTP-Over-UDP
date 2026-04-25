import os
from src.application.http_parser import HTTPParser
from src.transport.rudp_socket import RUDPSocket

class HTTPServer:
    def __init__(self, host, port, document_root="../../www"):
        self.addr = (host, port)
        self.document_root = document_root

    def run(self):
        print(f"HTTP Server starting on {self.addr[0]}:{self.addr[1]}")

        while True:
            # Initialize a fresh socket for each new connection attempt
            server_socket = RUDPSocket()
            server_socket.bind(self.addr)

            try:
                # Wait for the 3-way handshake to complete
                _, client_address = server_socket.accept()

                # Receive the full application payload
                raw_request = server_socket.recv()
                if not raw_request:
                    continue

                req_msg = HTTPParser.parse(raw_request)
                print(f"\n[Server] Received request: {req_msg.method} request for {req_msg.path}")

                # Route the request and generate bytes to send back
                response_bytes = self.handle_request(req_msg)

                # Send the response reliably
                server_socket.send(response_bytes)

            except Exception as e:
                print(f"[Server] Error handling request: {e}")
            finally:
                # Initialize graceful teardown (FIN, FIN-ACK)
                server_socket.close()

    def handle_request(self, req_msg) -> bytes:
        if req_msg.method == "GET":
            safe_path = os.path.normpath(req_msg.path).lstrip('/')
            if not safe_path or safe_path == "":
                safe_path = "index.html"

            file_path = os.path.join(self.document_root, safe_path)

            if os.path.exists(file_path) and os.path.isfile(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return HTTPParser.build_response(200, "OK", body=content)
            else:
                error_body = "<html><body><h1>404 Not Found</h1></body></html>"
                return HTTPParser.build_response(404, "NOT FOUND", body=error_body)

        elif req_msg.method == "POST":
            print(f"[Server] POST payload: {req_msg.body}")
            success_body = f"<html><body><h1>POST Data Received Successfully</h1><p>Your POST data was {req_msg.body}</p></body></html>"
            return HTTPParser.build_response(200, "OK", body=success_body)

        else:
            return HTTPParser.build_response(400, "BAD REQUEST", body="Unknown Method")
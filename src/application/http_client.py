from src.application.http_parser import HTTPParser
from src.transport.rudp_socket import RUDPSocket

class HTTPClient:
    def __init__(self, server_ip, server_port):
        self.server_addr = (server_ip, server_port)

    def send_request(self, method: str, path: str, body: str = ""):
        client_socket = RUDPSocket()

        try:
            print(f"\n[Client] Connecting to {self.server_addr[0]}:{self.server_addr[1]}...")
            client_socket.connect(self.server_addr)

            # Build and send the request
            req_bytes = HTTPParser.build_request(method, path, body)
            print(f"[Client] Sending {method} {path}...")
            client_socket.send(req_bytes)

            # Wait for the response
            print("[Client] Waiting for response...")
            raw_response = client_socket.recv()

            if raw_response:
                response_msg = HTTPParser.parse(raw_response)
                print("-" * 40)
                print(f"Status: {response_msg.version} {response_msg.status_code} {response_msg.status_phrase}")
                print("Headers:")
                for k, v in response_msg.headers.items():
                    print(f"  {k}: {v}")
                print(f"\nBody:\n{response_msg.body}")
                print("-" * 40)
            else:
                print("[Client] Received empty response.")

        except Exception as e:
            print(f"[Client] Error during communication: {e}")
        finally:
            print("[Client] Closing connection.")
            client_socket.close()
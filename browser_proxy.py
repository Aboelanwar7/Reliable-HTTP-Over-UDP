import socket
from src.transport.rudp_socket import RUDPSocket

def start_proxy(tcp_port=8081, rudp_server_ip='127.0.0.1', rudp_server_port=8080):
    proxy_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    proxy_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    proxy_tcp.bind(('127.0.0.1', tcp_port))
    proxy_tcp.listen(5)
    print(f"[Proxy] Listening for standard browser TCP connections on http://127.0.0.1:{tcp_port}")

    while True:
        # Wait for browser to connect
        client_tcp, addr = proxy_tcp.accept()
        print(f"\n[Proxy] Browser connected from {addr}")

        try:
            raw_request = client_tcp.recv(4096)
            if not raw_request:
                client_tcp.close()
                continue

            print("[Proxy] Received HTTP request from browser. Forwarding to RUDP Server...")

            rudp_client = RUDPSocket()
            rudp_client.connect((rudp_server_ip, rudp_server_port))
            rudp_client.send(raw_request)

            print("[Proxy] Waiting for response from RUDP Server...")
            raw_response = rudp_client.recv()

            if raw_response:
                print("[Proxy] Forwarding response back to browser.")
                client_tcp.sendall(raw_response)

            rudp_client.close()

        except Exception as e:
            print(f"[Proxy] Error handling browser request: {e}")
        finally:
            client_tcp.close()

if __name__ == "__main__":
    start_proxy()

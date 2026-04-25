import threading
import time

from src.transport.rudp_socket import RUDPSocket



def run_server():
    server_socket = RUDPSocket(loss_rate=0.2, corruption_rate=0.1, duplicate_rate=0.1)
    server_socket.bind(("127.0.0.1", 8080))
    server_socket.accept()

    data = server_socket.recv()
    print("Server received:", data.decode(errors="replace"))

    server_socket.send(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK")
    server_socket.close()


def run_client():
    client_socket = RUDPSocket(loss_rate=0.2, corruption_rate=0.1, duplicate_rate=0.1)
    client_socket.connect(("127.0.0.1", 8080))

    request = b"GET /index.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
    client_socket.send(request)

    response = client_socket.recv()
    print("Client received:", response.decode(errors="replace"))
    client_socket.close()


if __name__ == "__main__":
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.2)
    run_client()
    thread.join(timeout=5)
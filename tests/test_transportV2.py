import threading
import time

from src.transport.checksum import calculate_checksum, verify_checksum
from src.transport.packet import Packet
from src.transport.rudp_socket import RUDPSocket


def test_checksum_determinism():
    print("--- Running test_checksum_determinism ---")
    payload = b"Reliable UDP Data"
    chk1 = calculate_checksum(payload)
    chk2 = calculate_checksum(payload)

    if chk1 == chk2:
        print("  [PASS] Checksums matched perfectly.\n")
    else:
        print(f"  [FAIL] Checksum mismatch: {chk1} != {chk2}\n")


def test_packet_pack_unpack():
    print("--- Running test_packet_pack_unpack ---")
    original_pkt = Packet(seq_num=100, ack_num=0, flags=1, payload=b"Payload")
    raw_bytes = original_pkt.to_bytes()
    unpacked_pkt = Packet.from_bytes(raw_bytes)

    if unpacked_pkt.seq_num == 100 and unpacked_pkt.payload == b"Payload":
        print("  [PASS] Packet correctly packed and unpacked.\n")
    else:
        print(f"  [FAIL] Packet mismatch! Seq: {unpacked_pkt.seq_num}, Data: {unpacked_pkt.payload}\n")


def test_corrupted_packet_rejection():
    print("--- Running test_corrupted_packet_rejection ---")
    pkt = Packet(seq_num=1, ack_num=0, flags=0, payload=b"Valid Data")
    raw_bytes = bytearray(pkt.to_bytes())

    # Invert a byte in the payload to simulate network corruption
    raw_bytes[-1] ^= 0xFF

    if not verify_checksum(bytes(raw_bytes)):
        print("  [PASS] System successfully caught and rejected corrupted packet.\n")
    else:
        print("  [FAIL] System incorrectly accepted a corrupted packet!\n")


def test_transmission_with_loss_and_corruption():
    print("--- Running test_transmission_with_loss_and_corruption ---")
    server_addr = ('127.0.0.1', 50000)
    test_payload = b"End-to-End Transmission Test"

    server_sock = RUDPSocket(loss_rate=0.3, corruption_rate=0.3)
    server_sock.bind(server_addr)
    client_sock = RUDPSocket(loss_rate=0.3, corruption_rate=0.3)

    # Use a dictionary to capture the thread's result safely
    server_result = {"data": None}

    def server_listen():
        connected_sock, _ = server_sock.accept()
        server_result["data"] = connected_sock.recv()
        connected_sock.close()

    server_thread = threading.Thread(target=server_listen)
    server_thread.start()

    time.sleep(0.1)  # Allow server time to bind

    try:
        client_sock.connect(server_addr)
        client_sock.send(test_payload)
        client_sock.close()
    except Exception as e:
        print(f"  [FAIL] Client crashed during transmission: {e}\n")

    server_thread.join(timeout=5.0)

    if server_thread.is_alive():
        print("  [FAIL] Server thread hung! Transmission failed due to timeouts.\n")
    elif server_result["data"] == test_payload:
        print("  [PASS] Transmission succeeded despite 30% drop and corruption rates.\n")
    else:
        print(f"  [FAIL] Received data mismatch: {server_result['data']}\n")


def test_bidirectional_connection():
    print("--- Running test_bidirectional_connection ---")

    server_result = {"data": None}
    client_result = {"data": None}

    def run_server():
        server_socket = RUDPSocket(loss_rate=0.2, corruption_rate=0.1)
        server_socket.bind(("127.0.0.1", 8080))
        server_socket.accept()

        server_result["data"] = server_socket.recv()
        server_socket.send(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK")
        server_socket.close()

    def run_client():
        client_socket = RUDPSocket(loss_rate=0.2, corruption_rate=0.1)
        client_socket.connect(("127.0.0.1", 8080))

        client_socket.send(b"GET /index.html HTTP/1.0\r\nHost: localhost\r\n\r\n")
        client_result["data"] = client_socket.recv()

        time.sleep(1)
        client_socket.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    time.sleep(0.2)

    try:
        run_client()
    except Exception as e:
        print(f"  [FAIL] Client encountered an error: {e}")

    thread.join(timeout=10)

    if thread.is_alive():
        print("  [FAIL] Server thread hung during bidirectional test.\n")
        return

    # Evaluate the results captured by both sockets
    server_passed = b"GET /index.html" in server_result["data"] if server_result["data"] else False
    client_passed = b"200 OK" in client_result["data"] if client_result["data"] else False

    if server_passed and client_passed:
        print("  [PASS] Client and Server successfully exchanged messages.\n")
    else:
        print("  [FAIL] Message exchange failed.")
        print(f"         Server received: {server_result['data']}")
        print(f"         Client received: {client_result['data']}\n")


if __name__ == '__main__':
    print("   STARTING TRANSPORT LAYER TESTS")

    test_checksum_determinism()
    test_packet_pack_unpack()
    test_corrupted_packet_rejection()
    test_transmission_with_loss_and_corruption()
    test_bidirectional_connection()

    print("   TESTING COMPLETE")
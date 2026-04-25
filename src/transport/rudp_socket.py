import socket
from collections import deque
from typing import Optional, Tuple
from src.transport.checksum import verify_checksum
from src.transport.network_sim import NetworkSimulator
from src.transport.packet import Packet

class RUDPSocket:
    """
    Reliable UDP socket using:
    - 3-way handshake: SYN, SYN-ACK, ACK
    - stop-and-wait reliable transfer
    - checksum validation
    - timeout and retransmission
    - duplicate packet handling
    - graceful FIN teardown
    - chunking and reassembly for large messages
    """

    DEFAULT_TIMEOUT = 2.0
    DEFAULT_BUFFER_SIZE = 2048
    MAX_RETRIES = 10

    def __init__(
        self,
        loss_rate: float = 0.0,
        corruption_rate: float = 0.0,
        duplicate_rate: float = 0.0,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)

        self.timeout = timeout
        self.simulator = NetworkSimulator(
            loss_rate=loss_rate,
            corruption_rate=corruption_rate,
            duplicate_rate=duplicate_rate,
        )

        self.target_address: Optional[Tuple[str, int]] = None
        self.seq_num = 0
        self.expected_seq = 0
        self.closed = False
        self.pending_received_packets = deque()

    def _buffer_received_packet(self, packet: Packet, already_acked: bool) -> None:
        self.pending_received_packets.append((packet, already_acked))

    def bind(self, address: Tuple[str, int]) -> None:
        self.sock.bind(address)

    def _next_seq(self) -> None:
        self.seq_num = 1 - self.seq_num

    def _next_expected_seq(self) -> None:
        self.expected_seq = 1 - self.expected_seq

    def _raw_send(self, raw_bytes: bytes, address: Tuple[str, int]) -> None:
        duplicate = self.simulator.get_queued_duplicate()
        if duplicate is not None:
            self.sock.sendto(duplicate, address)

        if self.simulator.should_drop():
            print("[SIM] Packet dropped")
            return

        raw_bytes = self.simulator.maybe_corrupt(raw_bytes)
        self.simulator.maybe_duplicate(raw_bytes)
        self.sock.sendto(raw_bytes, address)

    def _send_packet(self, packet: Packet, address: Optional[Tuple[str, int]] = None) -> None:
        if self.closed:
            raise RuntimeError("Cannot send using a closed RUDPSocket")

        destination = address or self.target_address
        if destination is None:
            raise RuntimeError("Target address is not set")

        self._raw_send(packet.to_bytes(), destination)

    def _receive_valid_packet(self, timeout: Optional[float] = None) -> Tuple[Packet, Tuple[str, int]]:
        previous_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)

        try:
            while True:
                raw_data, addr = self.sock.recvfrom(self.DEFAULT_BUFFER_SIZE)

                if self.target_address is not None and addr != self.target_address:
                    continue

                if not verify_checksum(raw_data):
                    print("[DROP] Corrupted packet received")
                    continue

                try:
                    packet = Packet.from_bytes(raw_data)
                except ValueError:
                    print("[DROP] Malformed packet received")
                    continue

                return packet, addr
        finally:
            if timeout is not None:
                self.sock.settimeout(previous_timeout)

    def connect(self, address: Tuple[str, int]) -> None:
        """
        Client-side handshake.
        """
        self.target_address = address
        syn = Packet(seq_num=self.seq_num, flags=Packet.SYN)

        for _ in range(self.MAX_RETRIES):
            self._send_packet(syn)
            try:
                packet, addr = self._receive_valid_packet()
                if packet.has_flag(Packet.SYN) and packet.has_flag(Packet.ACK) and packet.ack_num == self.seq_num:
                    self.target_address = addr
                    final_ack = Packet(seq_num=self.seq_num, ack_num=packet.seq_num, flags=Packet.ACK)
                    self._send_packet(final_ack)
                    self._next_seq()
                    # FIX: We must expect the NEXT sequence number from the server
                    self.expected_seq = 1 - packet.seq_num
                    print("Connection established")
                    return
            except socket.timeout:
                print("SYN timeout, retransmitting")

        raise TimeoutError("Failed to establish connection")

    def accept(self) -> Tuple["RUDPSocket", Tuple[str, int]]: # Server-side handshake.

        print("Waiting for connection")
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(None)

        try:
            while True:
                packet, addr = self._receive_valid_packet(timeout=None)
                if packet.has_flag(Packet.SYN):
                    self.target_address = addr
                    client_seq = packet.seq_num
                    server_seq = self.seq_num
                    syn_ack = Packet(seq_num=server_seq, ack_num=client_seq, flags=Packet.SYN | Packet.ACK)
                    self._send_packet(syn_ack)
                    break
        finally:
            self.sock.settimeout(old_timeout)

        for _ in range(self.MAX_RETRIES):
            try:
                packet, addr = self._receive_valid_packet()

                # case 1: Normal ACK received
                if packet.has_flag(Packet.ACK) and not packet.has_flag(Packet.DATA) and packet.ack_num == self.seq_num:
                    self._next_seq()
                    self.expected_seq = 1 - client_seq
                    print(f"Connection established with {addr}")
                    return self, addr

                # case 2: IMPLICIT ACK via DATA
                if packet.has_flag(Packet.DATA):
                    print("Received DATA during handshake. Handshake complete implicitly.")
                    self._next_seq()
                    self.expected_seq = 1 - client_seq
                    if packet.seq_num == self.expected_seq:
                        ack = Packet(ack_num=packet.seq_num, flags=Packet.ACK)
                        self._send_packet(ack)
                        self._buffer_received_packet(packet, already_acked=True)
                    print(f"Connection established implicitly with {addr}")
                    return self, addr

                # case 3: Client re-sent SYN
                if packet.has_flag(Packet.SYN):
                    self._send_packet(syn_ack)

            except socket.timeout:
                self._send_packet(syn_ack)

        raise TimeoutError("Handshake failed while waiting for final ACK")

    def _send_one_reliable_packet(self, packet: Packet) -> None:  #Send one packet using stop-and-wait until its ACK is received.

        for _ in range(self.MAX_RETRIES):
            self._send_packet(packet)
            print(f"Sent packet seq={packet.seq_num}, flags={packet.flags}")

            try:
                incoming_packet, _ = self._receive_valid_packet()

                # Case 1: Normal ACK for our packet
                if incoming_packet.has_flag(Packet.ACK) and incoming_packet.ack_num == packet.seq_num:
                    print(f"Received ACK={incoming_packet.ack_num}")
                    return

                # Case 2: Peer sent DATA while we were waiting for ACK
                if incoming_packet.has_flag(Packet.DATA):
                    if incoming_packet.seq_num == self.expected_seq:
                        print(f"Received DATA while waiting for ACK. ACKing seq={incoming_packet.seq_num} and buffering.")
                        ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                        self._send_packet(ack)
                        self._buffer_received_packet(incoming_packet, already_acked=True)
                        continue
                    else:
                        print(f"Received duplicate DATA seq={incoming_packet.seq_num}. Resending ACK.")
                        duplicate_ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                        self._send_packet(duplicate_ack)

                # Case 3: Peer sent FIN while we were waiting
                elif incoming_packet.has_flag(Packet.FIN):
                    print(f"Received FIN while waiting for ACK. ACKing FIN={incoming_packet.seq_num}")
                    fin_ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                    self._send_packet(fin_ack)
                    self.closed = True
                    return

                # Case 4: Peer sent SYN or SYN-ACK (Handshake retransmission)
                elif incoming_packet.has_flag(Packet.SYN):
                    print("Received SYN/SYN-ACK while waiting for ACK. Peer missed handshake ACK. Resending.")
                    handshake_ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                    self._send_packet(handshake_ack)

                else:
                    print("Received invalid or unrelated packet while waiting for ACK.")

            except socket.timeout:
                print("Timeout waiting for ACK, retransmitting")

        raise TimeoutError(f"Packet seq={packet.seq_num} was not acknowledged")

    def send(self, data: bytes) -> None:  # Send a full message reliably and large messages split into chunks.

        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes or str")

        chunks = [data[i : i + Packet.MAX_PAYLOAD_SIZE] for i in range(0, len(data), Packet.MAX_PAYLOAD_SIZE)]
        if not chunks:
            chunks = [b""]

        for index, chunk in enumerate(chunks):
            flags = Packet.DATA
            if index == len(chunks) - 1:
                flags |= Packet.END

            packet = Packet(seq_num=self.seq_num, flags=flags, payload=chunk)
            self._send_one_reliable_packet(packet)
            self._next_seq()

    def recv(self) -> bytes: # Keeps receiving chunks until the END flag is seen.

        message = bytearray()

        while True:
            # Check the buffer first
            if self.pending_received_packets:
                buffered = self.pending_received_packets.popleft()
                if isinstance(buffered, tuple):
                    packet, already_acked = buffered
                else:
                    packet = buffered
                    already_acked = True
                print(f"Processing buffered packet seq={packet.seq_num}")
            else:
                try:
                    packet, _ = self._receive_valid_packet()
                    already_acked = False
                except socket.timeout:
                    continue

            # Handle Teardown
            if packet.has_flag(Packet.FIN):
                if not already_acked:
                    ack = Packet(ack_num=packet.seq_num, flags=Packet.ACK)
                    self._send_packet(ack)
                self.closed = True
                return b""

            # Ignore non-data packets in the receive loop
            if not packet.has_flag(Packet.DATA):
                continue

            # Handle Expected Data
            if packet.seq_num == self.expected_seq:
                message.extend(packet.payload)

                if not already_acked:
                    ack = Packet(ack_num=packet.seq_num, flags=Packet.ACK)
                    self._send_packet(ack)
                    print(f"Received expected seq={packet.seq_num}, ACK sent")

                self._next_expected_seq()

                if packet.has_flag(Packet.END):
                    return bytes(message)

            # Handle Duplicate Data (Peer lost our previous ACK)
            else:
                if not already_acked:
                    duplicate_ack = Packet(ack_num=packet.seq_num, flags=Packet.ACK)
                    self._send_packet(duplicate_ack)
                    print(f"Duplicate seq={packet.seq_num}, ACK resent")

    def close(self) -> None: # Reliable close: sends FIN, waits for ACK.

        if self.closed:
            return

        fin = Packet(seq_num=self.seq_num, flags=Packet.FIN)
        close_timeout = min(self.timeout, 0.2)

        for _ in range(self.MAX_RETRIES):
            self._send_packet(fin)
            print(f"Sent FIN seq={fin.seq_num}")

            try:
                incoming_packet, _ = self._receive_valid_packet(timeout=close_timeout)

                # Normal teardown
                if incoming_packet.has_flag(Packet.ACK) and incoming_packet.ack_num == fin.seq_num:
                    print("FIN acknowledged. Closing cleanly.")
                    break

                #  Simultaneous close detected
                elif incoming_packet.has_flag(Packet.FIN):
                    print("Received peer's FIN. ACKing and terminating immediately.")
                    fin_ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                    self._send_packet(fin_ack)
                    break

                elif incoming_packet.has_flag(Packet.DATA):
                    print(f"Received DATA during close. ACKing seq={incoming_packet.seq_num}")
                    data_ack = Packet(ack_num=incoming_packet.seq_num, flags=Packet.ACK)
                    self._send_packet(data_ack)

            except socket.timeout:
                print("Timeout waiting for FIN ACK, retransmitting FIN")
        else:
            print("FIN was not acknowledged; closing socket anyway.")

        self.closed = True
        self.sock.close()

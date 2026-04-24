import struct
from dataclasses import dataclass
from typing import ClassVar

from src.transport.checksum import calculate_checksum


# If this file is separated, use:
# from .checksum import calculate_checksum


@dataclass
class Packet:
    """
    Packet format:

    0                   1                   2                   3
    +-------------------+-------------------+-------------------+
    | seq_num: 1 byte   | ack_num: 1 byte   | flags: 1 byte     |
    +-------------------+-------------------+-------------------+
    | checksum: 2 bytes | length: 2 bytes                       |
    +-------------------+---------------------------------------+
    | payload: variable length                                  |
    +-----------------------------------------------------------+

    ACK semantics in this implementation:
    - ack_num means: "I successfully received packet with sequence number ack_num".
    - Stop-and-wait only uses sequence numbers 0 and 1.
    """

    SYN: ClassVar[int] = 0b00000001
    ACK: ClassVar[int] = 0b00000010
    FIN: ClassVar[int] = 0b00000100
    DATA: ClassVar[int] = 0b00001000
    END: ClassVar[int] = 0b00010000  # Last data chunk in a message

    HEADER_FORMAT: ClassVar[str] = "!BBBxHH"
    HEADER_SIZE: ClassVar[int] = struct.calcsize(HEADER_FORMAT)
    MAX_PAYLOAD_SIZE: ClassVar[int] = 900  # Safe under common MTU after UDP/IP headers

    seq_num: int = 0
    ack_num: int = 0
    flags: int = 0
    payload: bytes = b""
    checksum: int = 0

    def __post_init__(self):
        if isinstance(self.payload, str):
            self.payload = self.payload.encode("utf-8")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes or str")
        if len(self.payload) > self.MAX_PAYLOAD_SIZE:
            raise ValueError(f"payload too large: max is {self.MAX_PAYLOAD_SIZE} bytes")
        self.seq_num &= 0xFF
        self.ack_num &= 0xFF
        self.flags &= 0xFF

    def has_flag(self, flag: int) -> bool:
        return (self.flags & flag) != 0

    def _pack_header(self, checksum: int) -> bytes:
        return struct.pack(
            self.HEADER_FORMAT,
            self.seq_num,
            self.ack_num,
            self.flags,
            checksum,
            len(self.payload),
        )

    def to_bytes(self) -> bytes:
        header_with_zero_checksum = self._pack_header(0)
        self.checksum = calculate_checksum(header_with_zero_checksum + self.payload)
        return self._pack_header(self.checksum) + self.payload

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> "Packet":
        if len(raw_bytes) < cls.HEADER_SIZE:
            raise ValueError("Packet too small to contain header")

        header = raw_bytes[: cls.HEADER_SIZE]
        seq_num, ack_num, flags, checksum, payload_len = struct.unpack(cls.HEADER_FORMAT, header)

        expected_total_len = cls.HEADER_SIZE + payload_len
        if len(raw_bytes) != expected_total_len:
            raise ValueError("Packet length does not match header payload length")

        payload = raw_bytes[cls.HEADER_SIZE : expected_total_len]
        packet = cls(seq_num=seq_num, ack_num=ack_num, flags=flags, payload=payload)
        packet.checksum = checksum
        return packet
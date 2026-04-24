import random
from collections import deque
from typing import Optional


class NetworkSimulator:
    """
    Simulates unreliable network behavior:
    - packet loss
    - packet corruption
    - packet duplication

    Reordering is not very meaningful in strict stop-and-wait because only one
    data packet is in flight, but duplicate packets are useful for testing ACK loss.
    """

    def __init__(
        self,
        loss_rate: float = 0.0,
        corruption_rate: float = 0.0,
        duplicate_rate: float = 0.0,
    ):
        self.loss_rate = self._validate_rate(loss_rate, "loss_rate")
        self.corruption_rate = self._validate_rate(corruption_rate, "corruption_rate")
        self.duplicate_rate = self._validate_rate(duplicate_rate, "duplicate_rate")
        self.duplicate_queue = deque()

    @staticmethod
    def _validate_rate(rate: float, name: str) -> float:
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0")
        return rate

    def should_drop(self) -> bool:
        return random.random() < self.loss_rate

    def maybe_corrupt(self, packet_bytes: bytes) -> bytes:
        if packet_bytes and random.random() < self.corruption_rate:
            byte_array = bytearray(packet_bytes)
            index = random.randrange(len(byte_array))
            bit = 1 << random.randrange(8)
            byte_array[index] ^= bit
            return bytes(byte_array)
        return packet_bytes

    def maybe_duplicate(self, packet_bytes: bytes) -> None:
        if random.random() < self.duplicate_rate:
            self.duplicate_queue.append(packet_bytes)

    def get_queued_duplicate(self) -> Optional[bytes]:
        if self.duplicate_queue:
            return self.duplicate_queue.popleft()
        return None

def calculate_checksum(data: bytes) -> int:
    """
    Calculate the 16-bit Internet checksum.

    This is used for error detection. While sending, the checksum field in the
    packet header must be zero. While verifying, the checksum field contains the
    received checksum, and a valid packet should produce 0.
    """
    if len(data) % 2 == 1:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
        total = (total & 0xFFFF) + (total >> 16)  # wrap carry

    return (~total) & 0xFFFF


def verify_checksum(packet_bytes: bytes) -> bool:
    """
    Verify the checksum of a complete received packet.
    If the packet is valid, calculate_checksum(packet_bytes) returns 0.
    """
    return calculate_checksum(packet_bytes) == 0
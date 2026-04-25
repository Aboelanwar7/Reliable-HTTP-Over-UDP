def calculate_checksum(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
        total = (total & 0xFFFF) + (total >> 16)  # wrap carry

    return (~total) & 0xFFFF


def verify_checksum(packet_bytes: bytes) -> bool:
    return calculate_checksum(packet_bytes) == 0
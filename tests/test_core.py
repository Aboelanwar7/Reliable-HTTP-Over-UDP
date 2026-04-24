from src.transport.checksum import calculate_checksum, verify_checksum
from src.transport.packet import Packet


def test_checksum():
    data = b"Hello Reliable World"

    # 1. Calculate the checksum of the raw data
    csum = calculate_checksum(data)

    # 2. Append the checksum (simulate a packet that includes it)
    # We use big-endian to match network byte order
    packet_with_csum = data + csum.to_bytes(2, byteorder='big')

    # 3. If the math is correct, verifying the whole block MUST return True
    assert verify_checksum(packet_with_csum) == True

    # 4. Let's also test a deliberate corruption by changing the checksum slightly
    corrupted_packet = data + (csum - 1).to_bytes(2, byteorder='big')
    assert verify_checksum(corrupted_packet) == False

    print("✅ Checksum math works perfectly.")


def test_packet_serialization():
    original_pkt = Packet(seq_num=1, ack_num=0, flags=Packet.SYN | Packet.ACK, payload=b"Test")

    # to_bytes() automatically calculates and embeds the checksum into the header
    raw_bytes = original_pkt.to_bytes()

    # Verify the entire raw byte string mathematically
    assert verify_checksum(raw_bytes) == True

    # Unpack it to ensure the data survived
    decoded_pkt = Packet.from_bytes(raw_bytes)

    assert decoded_pkt.seq_num == 1
    assert decoded_pkt.flags == (Packet.SYN | Packet.ACK)
    assert decoded_pkt.payload == b"Test"

    print("✅ Packet serialization and deserialization works.")


if __name__ == "__main__":
    test_checksum()
    test_packet_serialization()
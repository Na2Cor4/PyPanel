import socket
import struct
from typing import Final

from config import HEIGHT, WIDTH


MAGIC: Final[bytes] = b"PYPN"
PAYLOAD_SIZE: Final[int] = WIDTH * HEIGHT // 8
PACKET_SIZE: Final[int] = 4 + 2 + 2 + PAYLOAD_SIZE


class UdpFrameSender:
    def __init__(self, host: str, port: int) -> None:
        self.address = (host, port)
        self.frame_id = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        self.sock.close()

    def send(self, framebuffer: bytes) -> None:
        if len(framebuffer) != PAYLOAD_SIZE:
            raise ValueError(f"framebuffer must be {PAYLOAD_SIZE} bytes")

        header = MAGIC + struct.pack("<HH", self.frame_id, PAYLOAD_SIZE)
        packet = header + framebuffer

        try:
            self.sock.sendto(packet, self.address)
        except OSError as exc:
            print(f"UDP send failed: {exc}")

        self.frame_id = (self.frame_id + 1) & 0xFFFF

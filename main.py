import argparse
import time

from config import ESP_HOST, ESP_PORT, FPS
from renderer import render_frame, render_test_pattern
from sensors import PanelStats
from udp_sender import UdpFrameSender


def _sleep_until_next_frame(started_at: float) -> None:
    delay = max(0.0, (1.0 / FPS) - (time.monotonic() - started_at))
    time.sleep(delay)


def _run_panel() -> None:
    stats = PanelStats()
    sender = UdpFrameSender(ESP_HOST, ESP_PORT)

    try:
        while True:
            started_at = time.monotonic()
            frame = render_frame(stats.read_all())
            sender.send(frame)
            _sleep_until_next_frame(started_at)
    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        sender.close()
        stats.close()


def _run_test_pattern() -> None:
    sender = UdpFrameSender(ESP_HOST, ESP_PORT)
    frame = render_test_pattern()

    try:
        while True:
            started_at = time.monotonic()
            sender.send(frame)
            _sleep_until_next_frame(started_at)
    except KeyboardInterrupt:
        print("Exiting.")
    finally:
        sender.close()


def _print_sensors() -> None:
    stats = PanelStats()
    try:
        stats.print_cpu_sensors()
    finally:
        stats.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send PyPanel frames to an ESP OLED receiver."
    )
    parser.add_argument(
        "--test-pattern", action="store_true", help="send a static OLED test pattern"
    )
    parser.add_argument(
        "--print-sensors", action="store_true", help="print CPU clock and power sensors"
    )
    args = parser.parse_args()

    if args.print_sensors:
        _print_sensors()
    elif args.test_pattern:
        _run_test_pattern()
    else:
        _run_panel()


if __name__ == "__main__":
    main()

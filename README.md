# PyPanel

Windows host renders PC hardware stats into a 128x64 monochrome SSD1306 framebuffer and sends it to an ESP8266/ESP32 over UDP.

The ESP only receives full framebuffer packets and displays them. It does not render text or parse hardware data.

# Features

- CPU usage, temperature, power
- GPU usage, temperature, power
- RAM used
- Large HH:MM time display
- 128x64 monochrome OLED output
- UDP full-frame protocol
- No GUI
- No compression
- No delta frames

## Python setup

powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

## PyPanel

A small Windows hardware monitor that renders CPU/GPU/RAM stats into a 128x64 SSD1306 framebuffer and streams it to an ESP8266/ESP32 over UDP.

The ESP only receives full framebuffer packets and displays them. It does not render text or parse hardware data.

## Features

- CPU/GPU usage, temperature, and power
- RAM used
- Large HH:MM time display
- 128x64 monochrome OLED output
- Simple UDP full-frame protocol
- No GUI, no compression, no delta frames

## Notes

This project is currently tuned for my own Windows desktop with an NVIDIA GPU.

The ESP firmware has Vancouver time hardcoded.

Built with AI assistance and manually tested on my own hardware.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py

## Edit config.py before running:

ESP_HOST = "192.168.x.x"
ESP_PORT = 4210
FPS = 2

## For ESP Wi-Fi setup, copy secrets.h.example to secrets.h and fill in your Wi-Fi name and password.

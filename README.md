# Colors Machine

This repository consolidates the software for the Colors Machine project, which automates military bugle calls (First Call, Colors, Retreat, Taps) using two ESP32 microcontrollers, a ds321 time module, and I2S audio board.
## Directory Structure

-   `controller/`: Source code for the MicroPython-based ESP32-S3 controller. This device handles timekeeping (NTP + DS3231), sunset calculations, and triggers the audio player via UART.
-   `mp3_player/`: Source code for the Arduino/PlatformIO-based ESP32 MP3 player. This device plays audio files from an SD card when triggered.
-   `audio_monitor.py`: A Python script to run on a host machine (e.g., Raspberry Pi or Linux device) to record audio output for verification/monitoring.
-   `sunset_data.csv`: Sunset time data used by both the controller and the audio monitor. Each row is a date and the time of sunset for that date (starting on 2025-12-01 and ending on 2026-05-31 for a specific location). The time is in minutes since midnight UTC. This tuple format saves space in the controller flash.

## Setup Instructions

### Controller (ESP32-S3)
1.  Navigate to `controller/`.
2.  Upload the contents to your ESP32-S3 using a tool like `pymakr`, `mpremote`, or `thonny`.
3.  `wifi.dat` will be saved on the esp32-s3 controller internal flash, configured for your network. The access point mode of the controller will require you to either select an ssid and enter password to store in wifi.dat or opt to set time manually.

### MP3 Player (ESP32)
1.  Navigate to `mp3_player/`.
2.  Open the project in VSCode with PlatformIO (pioarduino).
3.  Build and upload the firmware to your ESP32.
4.  Ensure an SD card with the required MP3 files (`/star_spangled_banner.mp3`, `/carry_on.mp3`, `/retreat.mp3`, `/taps.mp3`, `/first_call.mp3`) is inserted.

### Audio Monitor
1.  Ensure `audio-recorder` is installed on your system (`sudo apt install audio-recorder` on Debian/Ubuntu).
2.  Run the monitor script:
    ```bash
    python3 audio_monitor.py
    ```
    It will automatically trigger recordings 10 seconds before each scheduled event.

## Usage
The system runs automatically. The controller calculates event times based on the schedule and sunset data, sends UART signals to the MP3 player, and the MP3 player plays the corresponding audio. The `audio_monitor.py` script independently tracks these times to record the output for verification.

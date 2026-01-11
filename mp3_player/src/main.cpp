/*
  Plays MP3 file from microSD card
  Uses MAX98357 I2S Amplifier Module
  Uses ESP32-audioI2S Library - https://github.com/schreibfaul1/ESP32-audioI2S
  *
  Default microSD Card connections (can be changed):
  ---------------------------------
 * SD Card | ESP32
 *    D2       12
 *    D3       13
 *    CMD      15
 *    VSS      GND
 *    VDD      3.3V
 *    CLK      14
 *    VSS      GND
 *    D0       2  (add 1K pull up after flashing)
 *    D1       4
 // If you want to change the pin assignment or you get an error that some pins
    // are not assigned on ESP32-S3/ESP32-P4 uncomment this block and the
 appropriate
    // line depending if you want to use 1-bit or 4-bit line.
    // Please note that ESP32 does not allow pin change and setPins() will
 always fail.
    //if(! SD_MMC.setPins(clk, cmd, d0)){
    //if(! SD_MMC.setPins(clk, cmd, d0, d1, d2, d3)){
    //    Serial.println("Pin change failed!");
    //    return;
    //}
*/

// Include required libraries
#include "Arduino.h"
#include "Audio.h"
#include "FS.h"
#include "SD_MMC.h"

// I2S Connections
#define I2S_DOUT 19
#define I2S_BCLK 26
#define I2S_LRC 25

// Button (wire between BUTTON_PIN and GND)
#define BUTTON_PIN_1 5
#define BUTTON_PIN_2 18
#define BUTTON_PIN_3 23
#define BUTTON_PIN_4 13
#define BUTTON_PIN_5 33
#define BUTTON_PIN_6 27

#define LONG_PRESS_MS 1000
#define DEBOUNCE_MS 50

#define RX_PIN 21 // Connect to TX (pin 41) of the MicroPython ESP32
#define TX_PIN 22 // Connect to RX (pin 38) of the MicroPython ESP32

// Baud rate must match the sender's baud rate
const long baud_rate = 9600;

// Create Audio object
Audio audio;

// Define specific sequences
const char *sequence_btn1[] = {"/star_spangled_banner.mp3", "/carry_on.mp3"};
const int SEQUENCE_BTN1_LEN = sizeof(sequence_btn1) / sizeof(sequence_btn1[0]);

const char *sequence_btn4[] = {"/retreat.mp3", "/carry_on.mp3"};
const int SEQUENCE_BTN4_LEN = sizeof(sequence_btn4) / sizeof(sequence_btn4[0]);

// Global state for current playback sequence
const char **currentActiveSequence = nullptr;
int currentActiveSequenceIndex = 0;
int currentActiveSequenceLength = 0;
bool isPlayingASequence = false;
bool trackWasRunning = false; // Still needed for detecting end of a track

// Structure to hold button state and configuration
struct Button {
  int pin;
  const char *direct_mp3_file; // For buttons that play a single file
  const char **sequence_ptr;   // Pointer to a sequence array
  int sequence_len;            // Length of the sequence
  bool is_sequence_starter; // Flag to indicate if this button starts a sequence

  unsigned long lastDebounceTime;
  bool lastRawState;
  bool stableState;
};

// Array of buttons
Button buttons[] = {{BUTTON_PIN_1, nullptr, sequence_btn1, SEQUENCE_BTN1_LEN,
                     true, 0, HIGH, HIGH}, // Button 1 starts sequence 1
                    {BUTTON_PIN_2, "/taps.mp3", nullptr, 0, false, 0, HIGH,
                     HIGH}, // Button 2 plays taps directly
                    {BUTTON_PIN_3, "/first_call.mp3", nullptr, 0, false, 0,
                     HIGH, HIGH}, // Button 3 plays first_call directly
                    {BUTTON_PIN_4, nullptr, sequence_btn4, SEQUENCE_BTN4_LEN,
                     true, 0, HIGH, HIGH}, // Button 4 starts sequence 2
                    // Button 5 stops playback on any press
                    {BUTTON_PIN_5, nullptr, nullptr, 0, false, 0, HIGH, HIGH},
                    {BUTTON_PIN_6, nullptr, nullptr, 0, false, 0, HIGH, HIGH}};
const int NUM_BUTTONS = sizeof(buttons) / sizeof(buttons[0]);

// Helper to play the next track in the current sequence
void playNextInSequence() {
  if (isPlayingASequence && currentActiveSequence &&
      currentActiveSequenceIndex < currentActiveSequenceLength) {
    Serial.print("Playing sequence track: ");
    Serial.println(currentActiveSequence[currentActiveSequenceIndex]);
    audio.stopSong();
    delay(50);
    audio.connecttoFS(SD_MMC,
                      currentActiveSequence[currentActiveSequenceIndex]);
    trackWasRunning =
        audio.isRunning(); // Update trackWasRunning for the new song
  } else {
    // Sequence finished or invalid state
    isPlayingASequence = false;
    currentActiveSequence = nullptr;
    Serial.println("Sequence finished or invalid state.");
  }
}

// Helper to start audio playback based on button configuration
void startAudioPlayback(Button &btn) {
  audio.stopSong(); // Stop any current song before starting a new one
  delay(50);        // Small delay for audio library to settle

  if (btn.is_sequence_starter) {
    currentActiveSequence = btn.sequence_ptr;
    currentActiveSequenceLength = btn.sequence_len;
    currentActiveSequenceIndex = 0;
    isPlayingASequence = true;
    playNextInSequence(); // Start the first song in the sequence
  } else {
    // Direct play
    Serial.print("Playing direct track: ");
    Serial.println(btn.direct_mp3_file);
    audio.connecttoFS(SD_MMC, btn.direct_mp3_file);
    isPlayingASequence = false;      // Not playing a sequence
    currentActiveSequence = nullptr; // Clear sequence state
    trackWasRunning =
        audio.isRunning(); // Update trackWasRunning for the new song
  }
}

void setup() {

  if (!SD_MMC.begin("/sdcard",
                    true)) { // true to use 1-bit mode to free up pins 4, 12, 13
    Serial.println("Card Mount Failed");
    return;
  }
  uint8_t cardType = SD_MMC.cardType();

  if (cardType == CARD_NONE) {
    Serial.println("No SD_MMC card attached");
    return;
  }

  Serial.print("SD_MMC Card Type: ");
  if (cardType == CARD_MMC) {
    Serial.println("MMC");
  } else if (cardType == CARD_SD) {
    Serial.println("SDSC");
  } else if (cardType == CARD_SDHC) {
    Serial.println("SDHC");
  } else {
    Serial.println("UNKNOWN");
  }

  // Start Serial Port
  Serial.begin(115200);
  delay(1000);
  // Check for PSRAM
  if (psramFound()) {
    Serial.println("PSRAM is available!");
    Serial.print("PSRAM size (bytes): ");
    Serial.println(ESP.getPsramSize());
  } else {
    Serial.println("No PSRAM detected.");
    // flush serial buffer and reset device
    Serial.flush();
    delay(1000);
    ESP.restart(); // this program only works with PSRAM - requirment of audio
                   // library
  }

  // Setup I2S
  audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);

  // Set Volume
  audio.setVolume(5);

  // Setup buttons
  pinMode(BUTTON_PIN_1, INPUT_PULLUP);
  pinMode(BUTTON_PIN_2, INPUT_PULLUP);
  pinMode(BUTTON_PIN_3, INPUT_PULLUP);
  pinMode(BUTTON_PIN_4, INPUT_PULLUP);
  pinMode(BUTTON_PIN_5, INPUT_PULLUP);
  pinMode(BUTTON_PIN_6, INPUT_PULLUP);

  // Serial.println("ESP32 UART Receiver (C++)");
  Serial.println("-------------------------");

  // Start the second serial port for communication with the other ESP32
  // Format: begin(baud_rate, config, RX_PIN, TX_PIN)
  Serial2.begin(baud_rate, SERIAL_8N1, RX_PIN, TX_PIN);
}

void loop() {
  audio.loop();

  for (int i = 0; i < NUM_BUTTONS; i++) {
    Button &btn = buttons[i]; // Use reference to modify the struct in the array

    // Read button (active LOW)
    bool raw = digitalRead(btn.pin);

    // Debounce
    if (raw != btn.lastRawState) {
      btn.lastDebounceTime = millis();
      btn.lastRawState = raw;
    }

    if ((millis() - btn.lastDebounceTime) > DEBOUNCE_MS) {
      if (raw != btn.stableState) {
        btn.stableState = raw;
        if (btn.stableState == LOW) {
          // Button pressed
          if (btn.pin == BUTTON_PIN_6) {
            Serial.println("Button 6 Switch ON -> Toggle");
            Serial2.println("Auto_Sunset_ON");
          }
        } else {
          // Button released

          if (btn.pin == BUTTON_PIN_6) {
            Serial.println("Button 6 Switch OFF -> Toggle");
            Serial2.println("Auto_Sunset_OFF");
          } else if (btn.pin == BUTTON_PIN_5) {
            // Long press: stop any currently playing audio
            Serial.println("Stop button detected. Stopping audio.");
            Serial2.println("Press_Stop");
            audio.stopSong();
            isPlayingASequence = false;      // Ensure sequence mode is off
            currentActiveSequence = nullptr; // Clear sequence state
          } else {
            // Short press: play its associated MP3 or start its sequence
            startAudioPlayback(btn);
            switch (btn.pin) // switch expression
            {
            case BUTTON_PIN_1:
              Serial2.println("BTN-Star_Spangled_Banner");
              break;
            case BUTTON_PIN_2:
              Serial2.println("BTN-TAPS");
              break;
            case BUTTON_PIN_3:
              Serial2.println("BTN-First_Call");
              break;
            case BUTTON_PIN_4:
              Serial2.println("BTN-Retreat");
              break;
            }
          }
        }
      }
    }
  }

  // Advance sequence when a track finishes (detect falling edge)
  if (isPlayingASequence) {
    bool nowRunning = audio.isRunning();
    if (trackWasRunning && !nowRunning) { // Track just finished
      currentActiveSequenceIndex++;
      if (currentActiveSequenceIndex < currentActiveSequenceLength) {
        playNextInSequence();
      } else {
        // Sequence finished
        isPlayingASequence = false;
        currentActiveSequence = nullptr;
        Serial.println("Sequence completed.");
      }
    }
    trackWasRunning = nowRunning;
  }
  // Check if there is data available to read on Serial2
  if (Serial2.available()) {
    // Read the incoming string until a newline character is received
    String received_data = Serial2.readStringUntil('\n');

    // Remove any leading/trailing whitespace
    received_data.trim();
    Serial.print("Received data: ");
    // Process the received data
    switch (int(received_data[0])) // switch expression
    {
    case 48:                          // 48 is ASCII for '0'
      startAudioPlayback(buttons[0]); // Simulate Button 1 press
      break;
    case 49:
      startAudioPlayback(buttons[1]); // Simulate Button 2 press
      break;
    case 50:
      startAudioPlayback(buttons[2]); // Simulate Button 3 press
      break;
    case 51:
      startAudioPlayback(buttons[3]); // Simulate Button 4 press
      break;
    }

    // Print the received data to the Serial Monitor
    Serial.println(received_data);
    Serial2.flush();
    Serial2.println("ACK"); // Send an acknowledgment back to the sender
  }
}
#include <Arduino.h>
#include <Wire.h>
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <string.h>
#include <time.h>

#if !__has_include("secrets.h")
#error "Missing secrets.h. Copy esp8266_oled_receiver/secrets.h.example to esp8266_oled_receiver/secrets.h and set WIFI_SSID/WIFI_PASSWORD."
#endif

#include "secrets.h"

constexpr uint8_t OLED_WIDTH = 128;
constexpr uint8_t OLED_HEIGHT = 64;
constexpr int OLED_RESET = -1;
constexpr uint8_t OLED_ADDR = 0x3C;

constexpr uint16_t UDP_PORT = 4210;
constexpr uint16_t FRAMEBUFFER_SIZE = OLED_WIDTH * OLED_HEIGHT / 8;
constexpr uint16_t HEADER_SIZE = 8;
constexpr uint16_t PACKET_SIZE = HEADER_SIZE + FRAMEBUFFER_SIZE;
constexpr uint32_t HOST_FRAME_TIMEOUT_MS = 10000;
constexpr uint32_t STATUS_REFRESH_MS = 1000;

const uint8_t MAGIC[4] = {'P', 'Y', 'P', 'N'};
const char TZ_VANCOUVER[] = "PST8PDT,M3.2.0,M11.1.0";

Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);
WiFiUDP udp;

uint8_t packetBuffer[PACKET_SIZE];
uint32_t lastFrameMillis = 0;
uint32_t lastStatusMillis = 0;
bool showingStatusScreen = true;

static uint16_t readLe16(const uint8_t *p) {
  return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
}

static void drainCurrentPacket() {
  uint8_t discard[32];
  while (udp.available() > 0) {
    udp.read(discard, sizeof(discard));
  }
}

static String fitText(const String &text, uint8_t maxChars) {
  if (text.length() <= maxChars) {
    return text;
  }
  return text.substring(0, maxChars);
}

static String ssidLine(uint8_t maxChars) {
  const String prefix = F("SSID: ");
  const uint8_t ssidChars = maxChars > prefix.length() ? maxChars - prefix.length() : 0;
  return prefix + fitText(String(WIFI_SSID), ssidChars);
}

static void drawStatusBorder() {
  display.drawRect(0, 0, OLED_WIDTH, OLED_HEIGHT, SSD1306_WHITE);
}

static void formatVancouverTime(char *buffer, size_t size) {
  time_t now = time(nullptr);
  if (now < 1600000000) {
    snprintf(buffer, size, "--:--");
    return;
  }

  struct tm localTime;
  localtime_r(&now, &localTime);
  snprintf(buffer, size, "%02d:%02d", localTime.tm_hour, localTime.tm_min);
}

static void setupTime() {
  setenv("TZ", TZ_VANCOUVER, 1);
  tzset();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

static void showConnectingScreen() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  drawStatusBorder();
  display.setCursor(3, 4);
  display.print(F("PyPanel RX"));
  display.setCursor(3, 18);
  display.print(F("Connecting WiFi"));
  display.setCursor(3, 32);
  display.print(ssidLine(20));
  display.display();
}

static void showConnectedScreen(const IPAddress &ip) {
  char timeText[6];
  formatVancouverTime(timeText, sizeof(timeText));

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  drawStatusBorder();
  display.setCursor(3, 4);
  display.print(F("PyPanel RX"));
  display.setCursor(3, 16);
  display.print(F("IP: "));
  display.print(ip);
  display.setCursor(3, 28);
  display.print(ssidLine(20));

  display.setTextSize(2);
  display.setCursor(34, 46);
  display.print(timeText);
  display.display();

  showingStatusScreen = true;
  lastStatusMillis = millis();
}

static void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print(F("Connecting to Wi-Fi"));
  Serial.print(F(" SSID: "));
  Serial.println(WIFI_SSID);

  showConnectingScreen();

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }

  Serial.println();
  Serial.print(F("Wi-Fi connected. IP: "));
  Serial.println(WiFi.localIP());

  setupTime();
  showConnectedScreen(WiFi.localIP());
}

static void handlePacket() {
  const int packetSize = udp.parsePacket();
  if (packetSize <= 0) {
    return;
  }

  if (packetSize != PACKET_SIZE) {
    Serial.printf("Bad packet size: %d, expected %u\n", packetSize, static_cast<unsigned>(PACKET_SIZE));
    drainCurrentPacket();
    return;
  }

  const int bytesRead = udp.read(packetBuffer, PACKET_SIZE);
  if (bytesRead != PACKET_SIZE) {
    Serial.printf("UDP read failed: read %d bytes, expected %u\n", bytesRead, static_cast<unsigned>(PACKET_SIZE));
    drainCurrentPacket();
    return;
  }

  if (memcmp(packetBuffer, MAGIC, sizeof(MAGIC)) != 0) {
    Serial.println(F("Bad magic, expected PYPN"));
    return;
  }

  const uint16_t frameId = readLe16(packetBuffer + 4);
  const uint16_t payloadSize = readLe16(packetBuffer + 6);
  if (payloadSize != FRAMEBUFFER_SIZE) {
    Serial.printf("Bad payload size in frame %u: %u, expected %u\n",
                  static_cast<unsigned>(frameId),
                  static_cast<unsigned>(payloadSize),
                  static_cast<unsigned>(FRAMEBUFFER_SIZE));
    return;
  }

  memcpy(display.getBuffer(), packetBuffer + HEADER_SIZE, FRAMEBUFFER_SIZE);
  display.display();
  lastFrameMillis = millis();
  showingStatusScreen = false;
}

static void updateStatusScreenIfIdle() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  const uint32_t now = millis();
  const bool hostTimedOut = lastFrameMillis == 0 || now - lastFrameMillis >= HOST_FRAME_TIMEOUT_MS;
  if (!hostTimedOut) {
    return;
  }

  if (!showingStatusScreen || now - lastStatusMillis >= STATUS_REFRESH_MS) {
    showConnectedScreen(WiFi.localIP());
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println(F("PyPanel ESP8266 OLED receiver starting"));

  Wire.begin(D2, D1);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println(F("SSD1306 init failed"));
    while (true) {
      delay(1000);
    }
  }

  connectWiFi();

  if (!udp.begin(UDP_PORT)) {
    Serial.println(F("UDP listen failed"));
    while (true) {
      delay(1000);
    }
  }

  Serial.printf("Listening UDP port %u, packet size %u\n",
                static_cast<unsigned>(UDP_PORT),
                static_cast<unsigned>(PACKET_SIZE));
}

void loop() {
  handlePacket();
  updateStatusScreenIfIdle();
  yield();
}

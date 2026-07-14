#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoWebsockets.h>
#include <driver/i2s.h>

using namespace websockets;

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* WS_URL    = "wss://your-app.onrender.com/ws";

#define MIC_SCK 14
#define MIC_WS  15
#define MIC_SD  32
#define MIC_GAIN_SHIFT 11

#define OLED_W 128
#define OLED_H 64
#define OLED_ADDR 0x3C

#define SAMPLE_RATE 16000
#define FRAME_SAMPLES 512

Adafruit_SSD1306 display(OLED_W, OLED_H, &Wire, -1);
WebsocketsClient client;

enum Emotion { EMO_BOOT, EMO_LISTEN, EMO_THINK, EMO_SPEAK, EMO_HAPPY, EMO_SAD };
Emotion emotion = EMO_BOOT;
bool playing = false;
String statusText = "starting";
String lastText = "";

void initMic() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {
    .bck_io_num = MIC_SCK,
    .ws_io_num = MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = MIC_SD
  };
  i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pins);
}

void initDac() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX | I2S_MODE_DAC_BUILT_IN),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_MSB,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, NULL);
  i2s_set_dac_mode(I2S_DAC_CHANNEL_BOTH_EN);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void playChunk(const uint8_t* bytes, size_t len) {
  size_t n = len / 2;
  const int16_t* in = (const int16_t*)bytes;
  static uint16_t buf[512 * 2];
  size_t i = 0;
  while (i < n) {
    size_t m = min((size_t)512, n - i);
    for (size_t k = 0; k < m; k++) {
      uint16_t u = (uint16_t)((int32_t)in[i + k] + 32768);
      buf[2 * k] = u;
      buf[2 * k + 1] = u;
    }
    size_t written;
    i2s_write(I2S_NUM_0, buf, m * 2 * sizeof(uint16_t), &written, portMAX_DELAY);
    i += m;
  }
}

String extractText(const String& j) {
  int k = j.indexOf("\"text\"");
  if (k < 0) return "";
  int c = j.indexOf(':', k);
  int q = j.indexOf('"', c);
  if (q < 0) return "";
  String out;
  bool esc = false;
  for (int i = q + 1; i < (int)j.length(); i++) {
    char ch = j[i];
    if (esc) { out += (ch == 'n') ? ' ' : ch; esc = false; }
    else if (ch == '\\') esc = true;
    else if (ch == '"') break;
    else out += ch;
  }
  return out;
}

void onMessage(WebsocketsMessage msg) {
  if (msg.isBinary()) {
    if (playing) playChunk((const uint8_t*)msg.c_str(), msg.length());
    return;
  }
  String d = msg.data();
  if (d.indexOf("play_start") >= 0) {
    playing = true;
    emotion = EMO_SPEAK;
    statusText = "speaking";
  } else if (d.indexOf("play_end") >= 0) {
    playing = false;
    emotion = EMO_HAPPY;
    statusText = "listening";
    lastText = "";
    i2s_zero_dma_buffer(I2S_NUM_0);
  } else if (d.indexOf("\"transcript\"") >= 0) {
    lastText = extractText(d);
    emotion = EMO_THINK;
    statusText = "thinking";
  } else if (d.indexOf("\"reply\"") >= 0) {
    lastText = extractText(d);
  }
}

void drawEye(int x, int y, int w, int h, int px, int py, bool blink) {
  if (blink) {
    display.fillRoundRect(x, y + h / 2 - 2, w, 4, 2, SSD1306_WHITE);
    return;
  }
  display.fillRoundRect(x, y, w, h, 5, SSD1306_WHITE);
  display.fillRoundRect(x + w / 2 - 4 + px, y + h / 2 - 4 + py, 8, 8, 2, SSD1306_BLACK);
}

void drawMouth(Emotion e) {
  int cx = 64, my = 40;
  if (e == EMO_SPEAK) {
    int f = (millis() / 120) % 3;
    int mh = 3 + f * 5;
    display.fillRoundRect(cx - 12, my - mh / 2, 24, mh, 3, SSD1306_WHITE);
  } else if (e == EMO_THINK) {
    int d = (millis() / 350) % 4;
    for (int i = 0; i < d; i++) display.fillCircle(cx - 12 + i * 12, my, 2, SSD1306_WHITE);
  } else if (e == EMO_HAPPY) {
    display.drawLine(cx - 12, my - 2, cx, my + 5, SSD1306_WHITE);
    display.drawLine(cx, my + 5, cx + 12, my - 2, SSD1306_WHITE);
  } else if (e == EMO_SAD) {
    display.drawLine(cx - 12, my + 5, cx, my - 2, SSD1306_WHITE);
    display.drawLine(cx, my - 2, cx + 12, my + 5, SSD1306_WHITE);
  } else {
    display.drawFastHLine(cx - 8, my, 16, SSD1306_WHITE);
  }
}

void drawBottom() {
  display.drawFastHLine(4, 47, 120, SSD1306_WHITE);
  String t = lastText.length() ? lastText : statusText;
  int w = t.length() * 6;
  int y = 52;
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  if (w <= 120) {
    display.setCursor((128 - w) / 2, y);
    display.print(t);
  } else {
    int span = w + 30;
    int off = (millis() / 40) % span;
    display.setCursor(6 - off, y);
    display.print(t);
    display.setCursor(6 - off + span, y);
    display.print(t);
  }
}

void drawFace() {
  display.clearDisplay();
  display.drawRoundRect(0, 0, 128, 64, 6, SSD1306_WHITE);

  bool blink = (millis() % 3200) < 160;
  int ey = 14, eh = 20;
  int px = 0, py = 0;
  if (emotion == EMO_THINK) { py = -4; px = ((millis() / 300) % 2) ? 3 : -3; }
  else if (emotion == EMO_SAD) py = 3;
  else if (emotion == EMO_BOOT) blink = true;

  drawEye(26, ey, 26, eh, px, py, blink);
  drawEye(76, ey, 26, eh, px, py, blink);
  drawMouth(emotion);
  drawBottom();
  display.display();
}

void renderTick() {
  static uint32_t last = 0;
  if (millis() - last < 60) return;
  last = millis();
  drawFace();
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  emotion = EMO_SAD;
  statusText = "wifi...";
  while (WiFi.status() != WL_CONNECTED) {
    renderTick();
    delay(100);
  }
}

void connectServer() {
  client.setInsecure();
  client.onMessage(onMessage);
  emotion = EMO_SAD;
  statusText = "server...";
  while (!client.connect(WS_URL)) {
    renderTick();
    delay(500);
  }
  emotion = EMO_HAPPY;
  statusText = "listening";
}

void setup() {
  Wire.begin(21, 22);
  display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  display.clearDisplay();
  display.display();
  emotion = EMO_BOOT;
  statusText = "connecting";
  renderTick();

  initMic();
  initDac();
  connectWiFi();
  connectServer();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!client.available()) connectServer();
  client.poll();

  if (!playing) {
    static int32_t raw[FRAME_SAMPLES];
    static int16_t out[FRAME_SAMPLES];
    size_t bytesRead = 0;
    i2s_read(I2S_NUM_1, raw, sizeof(raw), &bytesRead, 20 / portTICK_PERIOD_MS);
    int n = bytesRead / 4;
    for (int i = 0; i < n; i++) out[i] = raw[i] >> MIC_GAIN_SHIFT;
    if (n > 0) client.sendBinary((const char*)out, n * 2);
  }

  renderTick();
}

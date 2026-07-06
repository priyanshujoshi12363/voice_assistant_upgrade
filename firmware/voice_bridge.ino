#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <driver/i2s.h>

using namespace websockets;

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* WS_URL = "wss://your-app.onrender.com/ws";

#define MIC_SD 4
#define MIC_WS 5
#define MIC_SCK 6
#define SPK_DIN 7
#define SPK_BCLK 15
#define SPK_LRC 16
#define LED_PIN 48

#define SAMPLE_RATE 16000
#define FRAME_SAMPLES 1280
#define MIC_GAIN_SHIFT 11

WebsocketsClient client;
volatile bool playing = false;

void setupMic() {
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
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
}

void setupSpeaker() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 6,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {
    .bck_io_num = SPK_BCLK,
    .ws_io_num = SPK_LRC,
    .data_out_num = SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pins);
}

void onMessage(WebsocketsMessage msg) {
  if (msg.isBinary()) {
    if (playing) {
      size_t written;
      i2s_write(I2S_NUM_1, msg.c_str(), msg.length(), &written, portMAX_DELAY);
    }
    return;
  }
  String d = msg.data();
  if (d.indexOf("play_start") >= 0) {
    playing = true;
    digitalWrite(LED_PIN, HIGH);
  } else if (d.indexOf("play_end") >= 0) {
    playing = false;
    digitalWrite(LED_PIN, LOW);
  }
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }
}

void connectServer() {
  client.setInsecure();
  client.onMessage(onMessage);
  while (!client.connect(WS_URL)) {
    delay(1000);
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  setupMic();
  setupSpeaker();
  connectWiFi();
  connectServer();
}

void loop() {
  if (!client.available()) {
    connectServer();
  }
  client.poll();

  if (!playing) {
    static int32_t raw[FRAME_SAMPLES];
    static int16_t out[FRAME_SAMPLES];
    size_t bytesRead = 0;
    i2s_read(I2S_NUM_0, raw, sizeof(raw), &bytesRead, 20 / portTICK_PERIOD_MS);
    int n = bytesRead / 4;
    for (int i = 0; i < n; i++) {
      out[i] = raw[i] >> MIC_GAIN_SHIFT;
    }
    if (n > 0) {
      client.sendBinary((const char*)out, n * 2);
    }
  }
}

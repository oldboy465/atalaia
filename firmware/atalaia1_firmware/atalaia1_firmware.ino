#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

// -------------------------------------------------------------
// DEFINIÇÃO DE HARDWARE E PINOS
// -------------------------------------------------------------
#define DHTPIN 4
#define LED_PULSE_PIN 18
#define LED_WIFI_PIN  19

#define PWM_FREQ 5000
#define PWM_RES  8

#define LED_STANDBY_BRIGHTNESS 25
#define LED_PEAK_BRIGHTNESS    255

// -------------------------------------------------------------
// REDE LOCAL PRÓPRIA (ACCESS POINT DEDICADO E RESOLUÇÃO mDNS)
// -------------------------------------------------------------
const char* AP_SSID = "atalaia1";
const char* AP_PASS = "82506920";
const char* MDNS_HOST = "atalaia1"; // Permite acesso por http://atalaia1.local

IPAddress local_ip(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

// -------------------------------------------------------------
// PERSISTÊNCIA EM FLASH (LittleFS)
// -------------------------------------------------------------
#define BUFFER_CAPACITY 7200
#define STORAGE_FILE "/atalaia_buffer.bin"
#define BOOT_FILE    "/boot_count.txt"

struct SensorData {
  float temperature;
  float humidity;
  uint32_t uptime_sec;
  uint32_t session_id;
};

size_t bufferCount = 0;
uint32_t currentBootSession = 1;

WebServer server(80);

float currentTemp = 0.0f;
float currentHumidity = 0.0f;
unsigned long lastSensorRead = 0;
const unsigned long READ_INTERVAL = 5000;

// Estado de Operação: Ativo (true) ou Suspenso/Dormindo (false)
bool isNodeAwake = true;

// LED Pulse sem bloqueio FreeRTOS
bool isPulsing = false;
int pulseBrightness = LED_STANDBY_BRIGHTNESS;
int pulseDirection = 15;
unsigned long lastPulseStep = 0;

void startPulse() {
  if (!isNodeAwake) return;
  isPulsing = true;
  pulseBrightness = LED_STANDBY_BRIGHTNESS;
  pulseDirection = 15;
}

void updatePulse() {
  if (!isPulsing) return;

  unsigned long now = millis();
  if (now - lastPulseStep >= 12) {
    lastPulseStep = now;
    pulseBrightness += pulseDirection;

    if (pulseBrightness >= LED_PEAK_BRIGHTNESS) {
      pulseBrightness = LED_PEAK_BRIGHTNESS;
      pulseDirection = -15;
    } else if (pulseBrightness <= LED_STANDBY_BRIGHTNESS) {
      pulseBrightness = LED_STANDBY_BRIGHTNESS;
      isPulsing = false;
    }
    ledcWrite(LED_PULSE_PIN, pulseBrightness);
  }
}

// -------------------------------------------------------------
// SISTEMA DE ARQUIVOS
// -------------------------------------------------------------
void initStorage() {
  if (!LittleFS.begin(true)) {
    Serial.println("[LittleFS] Erro ao montar particao.");
    return;
  }

  if (LittleFS.exists(BOOT_FILE)) {
    File fb = LittleFS.open(BOOT_FILE, "r");
    if (fb) {
      String str = fb.readString();
      currentBootSession = str.toInt() + 1;
      fb.close();
    }
  }
  File fbWrite = LittleFS.open(BOOT_FILE, "w");
  if (fbWrite) {
    fbWrite.print(currentBootSession);
    fbWrite.close();
  }
  Serial.printf("[SESSAO] Inicializando Sessao #%u\n", currentBootSession);

  if (LittleFS.exists(STORAGE_FILE)) {
    File f = LittleFS.open(STORAGE_FILE, "r");
    if (f) {
      bufferCount = f.size() / sizeof(SensorData);
      f.close();
      Serial.printf("[LittleFS] %u registros preservados na Flash.\n", (unsigned int)bufferCount);
    }
  } else {
    File f = LittleFS.open(STORAGE_FILE, "w");
    if (f) f.close();
    bufferCount = 0;
  }
}

void saveSampleToFlash(const SensorData &sample) {
  if (bufferCount >= BUFFER_CAPACITY) return;

  File f = LittleFS.open(STORAGE_FILE, "a");
  if (f) {
    f.write((const uint8_t*)&sample, sizeof(SensorData));
    f.close();
    bufferCount++;
  }
}

void clearFlashStorage() {
  if (LittleFS.exists(STORAGE_FILE)) {
    LittleFS.remove(STORAGE_FILE);
  }
  File f = LittleFS.open(STORAGE_FILE, "w");
  if (f) f.close();
  bufferCount = 0;

  currentBootSession = 1;
  File fb = LittleFS.open(BOOT_FILE, "w");
  if (fb) {
    fb.print("1");
    fb.close();
  }
  Serial.println("[LittleFS] Armazenamento reiniciado.");
}

// -------------------------------------------------------------
// LEITURA CALIBRADA DO SENSOR (40 BITS)
// -------------------------------------------------------------
bool sampleDHTSensor(float &outTemp, float &outHum) {
  uint8_t data[5] = {0, 0, 0, 0, 0};

  pinMode(DHTPIN, OUTPUT);
  digitalWrite(DHTPIN, LOW);
  delay(20);
  digitalWrite(DHTPIN, HIGH);
  delayMicroseconds(30);
  pinMode(DHTPIN, INPUT_PULLUP);

  noInterrupts();

  unsigned long timeout = micros();
  while (digitalRead(DHTPIN) == HIGH) {
    if (micros() - timeout > 100) { interrupts(); return false; }
  }

  timeout = micros();
  while (digitalRead(DHTPIN) == LOW) {
    if (micros() - timeout > 100) { interrupts(); return false; }
  }

  timeout = micros();
  while (digitalRead(DHTPIN) == HIGH) {
    if (micros() - timeout > 100) { interrupts(); return false; }
  }

  for (int i = 0; i < 40; i++) {
    timeout = micros();
    while (digitalRead(DHTPIN) == LOW) {
      if (micros() - timeout > 100) { interrupts(); return false; }
    }

    unsigned long tStart = micros();
    while (digitalRead(DHTPIN) == HIGH) {
      if (micros() - tStart > 120) break;
    }
    unsigned long duration = micros() - tStart;

    if (duration > 45) {
      data[i / 8] |= (1 << (7 - (i % 8)));
    }
  }

  interrupts();

  uint8_t checksum = (uint8_t)(data[0] + data[1] + data[2] + data[3]);
  if (data[4] != checksum) return false;

  float hum = ((data[0] << 8) | data[1]) * 0.1f;
  float temp = (((data[2] & 0x7F) << 8) | data[3]) * 0.1f;
  if (data[2] & 0x80) temp = -temp;

  if (temp < 0.0f || temp > 60.0f || hum < 5.0f || hum > 100.0f) return false;

  outTemp = temp;
  outHum = hum;
  return true;
}

// -------------------------------------------------------------
// TEMPLATE HTML EMBARCADO (LEVE COM BOTÃO RUDIMENTAR DE LIGAR/DESLIGAR)
// -------------------------------------------------------------
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Atalaia v1.2</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
    body{background:#060b13;color:#f1f5f9;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px}
    .card{background:#0e1a2d;border:1px solid #1e3a5f;border-radius:18px;width:100%;max-width:400px;padding:22px;box-shadow:0 15px 30px rgba(0,0,0,0.5)}
    .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1e3a5f;padding-bottom:12px;margin-bottom:16px}
    .badge{padding:4px 9px;border-radius:20px;font-size:0.7rem;font-weight:700}
    .badge-on{background:rgba(16,185,129,0.2);color:#34d399;border:1px solid #10b981}
    .badge-off{background:rgba(239,68,68,0.2);color:#f87171;border:1px solid #ef4444}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
    .metric{background:#081220;border:1px solid #172a45;padding:14px;border-radius:12px;text-align:center}
    .metric h3{font-size:0.68rem;color:#94a3b8;text-transform:uppercase;margin-bottom:4px}
    .val{font-size:1.8rem;font-weight:700}
    .temp{color:#38bdf8}
    .hum{color:#34d399}
    .unit{font-size:0.8rem;color:#94a3b8}
    .btn-toggle{width:100%;padding:10px;margin-bottom:16px;border-radius:8px;border:none;font-size:0.85rem;font-weight:700;cursor:pointer;color:#ffffff}
    .btn-wake{background:#059669}
    .btn-sleep{background:#dc2626}
    .footer{font-size:0.72rem;color:#64748b;text-align:center;line-height:1.6;border-top:1px solid #172a45;padding-top:12px}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div>
        <h2 style="font-size:1.1rem;font-weight:700;">Atalaia v1.2</h2>
        <p style="font-size:0.72rem;color:#64748b;">http://atalaia1.local</p>
      </div>
      <span class="badge badge-on" id="stateBadge">Operando</span>
    </div>

    <!-- BOTÃO RUDIMENTAR DE LIGAR/DESLIGAR -->
    <button id="btnPower" class="btn-toggle btn-sleep" onclick="toggleNodePower()">Suspender Nó</button>

    <div class="grid">
      <div class="metric">
        <h3>Temperatura</h3>
        <div class="val temp" id="valTemp">--<span class="unit"> °C</span></div>
      </div>
      <div class="metric">
        <h3>Umidade</h3>
        <div class="val hum" id="valHum">--<span class="unit"> %</span></div>
      </div>
    </div>
    <div class="footer">
      <p id="sessionInfo">Sessão: #--</p>
      <p id="uptime">Tempo Ativo: 00h 00m 00s</p>
      <p id="bufferStatus">Flash: 0 / 7200 Amostras</p>
    </div>
  </div>
  <script>
    let nodeAwakeState = true;

    async function updateTelemetry() {
      try {
        const res = await fetch('/api/current');
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('valTemp').innerHTML = data.temperature.toFixed(1) + '<span class="unit"> °C</span>';
        document.getElementById('valHum').innerHTML = data.humidity.toFixed(1) + '<span class="unit"> %</span>';
        document.getElementById('sessionInfo').innerText = `Sessão Atual: #${data.session_id}`;
        
        const hrs = Math.floor(data.uptime_seconds / 3600);
        const mins = Math.floor((data.uptime_seconds % 3600) / 60);
        const secs = data.uptime_seconds % 60;
        document.getElementById('uptime').innerText = `Uptime: ${hrs}h ${mins}m ${secs}s`;
        document.getElementById('bufferStatus').innerText = `Flash: ${data.buffer_count} / 7200 Amostras`;
        
        nodeAwakeState = data.node_awake;
        renderPowerUI(nodeAwakeState);
      } catch(err) {}
    }

    function renderPowerUI(isAwake) {
      const b = document.getElementById('stateBadge');
      const btn = document.getElementById('btnPower');
      if (isAwake) {
        b.className = 'badge badge-on';
        b.innerText = 'Ativo';
        btn.className = 'btn-toggle btn-sleep';
        btn.innerText = 'Suspender Nó (Desligar)';
      } else {
        b.className = 'badge badge-off';
        b.innerText = 'Standby';
        btn.className = 'btn-toggle btn-wake';
        btn.innerText = 'Ativar Nó (Ligar)';
      }
    }

    async function toggleNodePower() {
      const endpoint = nodeAwakeState ? '/api/shutdown' : '/api/wakeup';
      try {
        await fetch(endpoint, { method: 'POST' });
        updateTelemetry();
      } catch(e) {}
    }

    setInterval(updateTelemetry, 3000);
    updateTelemetry();
  </script>
</body>
</html>
)rawliteral";

// -------------------------------------------------------------
// SETUP
// -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);

  ledcAttach(LED_PULSE_PIN, PWM_FREQ, PWM_RES);
  ledcWrite(LED_PULSE_PIN, LED_STANDBY_BRIGHTNESS);

  pinMode(LED_WIFI_PIN, OUTPUT);
  digitalWrite(LED_WIFI_PIN, LOW);

  pinMode(DHTPIN, INPUT_PULLUP);

  initStorage();

  // Modo Ponto de Acesso (AP) Dedicado
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  WiFi.softAP(AP_SSID, AP_PASS, 1);

  // Inicializa o mDNS para responder a http://atalaia1.local
  if (MDNS.begin(MDNS_HOST)) {
    Serial.println("[mDNS] Respondedor ativado: http://atalaia1.local");
    MDNS.addService("http", "tcp", 80);
  }

  Serial.println("[WIFI AP] Atalaia1 operando em 192.168.4.1 e atalaia1.local");

  // Rota Principal (HTML Embutido Leve)
  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html", INDEX_HTML);
  });

  // Telemetria em Tempo Real
  server.on("/api/current", HTTP_GET, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    StaticJsonDocument<384> doc;
    doc["temperature"] = currentTemp;
    doc["humidity"] = currentHumidity;
    doc["uptime_seconds"] = (uint32_t)(esp_timer_get_time() / 1000000ULL);
    doc["connected_clients"] = WiFi.softAPgetStationNum();
    doc["buffer_count"] = bufferCount;
    doc["session_id"] = currentBootSession;
    doc["node_awake"] = isNodeAwake;

    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  });

  // Exportação dos Registros em Lote da Flash
  server.on("/api/export", HTTP_GET, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");

    File f = LittleFS.open(STORAGE_FILE, "r");
    if (!f) {
      server.send(200, "application/json", "{\"count\":0,\"data\":[]}");
      return;
    }

    size_t count = f.size() / sizeof(SensorData);
    server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    server.send(200, "application/json", "{\"count\":" + String(count) + ",\"data\":[");

    SensorData item;
    size_t i = 0;
    while (f.read((uint8_t*)&item, sizeof(SensorData)) == sizeof(SensorData)) {
      String jsonItem = "";
      if (i > 0) jsonItem += ",";
      jsonItem += "{\"t\":" + String(item.temperature, 2) +
                  ",\"h\":" + String(item.humidity, 2) +
                  ",\"u\":" + String(item.uptime_sec) +
                  ",\"s\":" + String(item.session_id) + "}";
      server.sendContent(jsonItem);
      i++;
    }
    f.close();

    server.sendContent("]}");
  });

  // Limpeza de Buffer
  server.on("/api/clear", HTTP_POST, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    clearFlashStorage();
    server.send(200, "application/json", "{\"status\":\"flash_buffer_cleared\"}");
  });

  // Comando de Desligar Nó (Suspensão de Sensores & Economia de Energia sem derrubar Wi-Fi)
  server.on("/api/shutdown", HTTP_POST, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    isNodeAwake = false;
    ledcWrite(LED_PULSE_PIN, 0);
    server.send(200, "application/json", "{\"status\":\"node_sleeping\",\"message\":\"No colocado em Standby de economia.\"}");
  });

  // Comando de Ligar Nó (Ativação e retomada imediata de amostras)
  server.on("/api/wakeup", HTTP_POST, []() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    isNodeAwake = true;
    ledcWrite(LED_PULSE_PIN, LED_STANDBY_BRIGHTNESS);
    lastSensorRead = 0; // Força leitura na próxima iteração do loop
    server.send(200, "application/json", "{\"status\":\"node_awake\",\"message\":\"No sensorial ativado com sucesso.\"}");
  });

  server.begin();
  Serial.println("Servidor Atalaia v1.2 operacional.");
}

// -------------------------------------------------------------
// LOOP PRINCIPAL
// -------------------------------------------------------------
void loop() {
  server.handleClient();

  // Se o nó estiver acordado, executa os efeitos de pulso e leituras normais
  if (isNodeAwake) {
    updatePulse();

    // LED D19: Aceso quando o notebook/celular estiver conectado ao AP
    if (WiFi.softAPgetStationNum() > 0) {
      digitalWrite(LED_WIFI_PIN, HIGH);
    } else {
      digitalWrite(LED_WIFI_PIN, LOW);
    }

    unsigned long now = millis();
    if (now - lastSensorRead >= READ_INTERVAL) {
      lastSensorRead = now;

      float t = 0.0f;
      float h = 0.0f;
      bool ok = sampleDHTSensor(t, h);

      if (ok) {
        currentTemp = t;
        currentHumidity = h;

        SensorData sample;
        sample.temperature = t;
        sample.humidity = h;
        sample.uptime_sec = (uint32_t)(esp_timer_get_time() / 1000000ULL);
        sample.session_id = currentBootSession;

        saveSampleToFlash(sample);

        Serial.printf("[S#%u] Temp: %.1f C | Umid: %.1f %% | Flash: %u/7200\n",
                      currentBootSession, t, h, (unsigned int)bufferCount);

        startPulse();
      }
    }
  } else {
    // Nó em Standby: LEDs desligados para poupar bateria
    digitalWrite(LED_WIFI_PIN, LOW);
    ledcWrite(LED_PULSE_PIN, 0);
    delay(5); // Alivia a CPU mantendo o servidor web e o rádio Wi-Fi responsivos para o despertar
  }
}
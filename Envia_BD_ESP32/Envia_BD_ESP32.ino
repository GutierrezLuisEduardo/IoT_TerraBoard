#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <DHT_U.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ==== Sensores ====
// DHT11 - Temperatura y humedad
  #define DHTTYPE DHT11
  int DHTPIN = 21, sensorPin = 34;
  DHT_Unified dht(DHTPIN, DHTTYPE);
  int PINVERDE = 22, PINAMARILLO = 19, PINROJO = 2; // Pines de LEDs
  uint32_t delayMS;

  // HW-038 - Nivel de agua
  int nivelBajo = 0, nivelMedio = 0, nivelAlto = 0; // Valores calibrados
  const unsigned long CONFIRM_TIMEOUT = 20000UL; // 20 segundos de espera

  // Variables de control de temperatura
  int tR = 24, variation = 1, cnt = 0;
  bool dU = false, encendido = false;

// ==== Valores de conexión con servidor ===
  const char *ssid = "", *password = ""; // WIFI
  const char* serverURL = "TU_PROPIA_URL/datos";  // URL de ngrok hacia el endpoint de datos

  // Variables para control de envío
  unsigned long previousMillis = 0, intervaloEnvio = 6000;  // 6 segundos

// ===== FUNCIONES DEL SENSOR DE NIVEL DE AGUA =====
int readSensor() {
  delay(10);
  long total = 0;
  const int num = 10;
  for (int i = 0; i < num; i++) {
    total += analogRead(sensorPin);
    delay(40);
  }
  return (int)(total / num);
}
int clasificarAgua(int menor, int medio, int alto) {
  int valor = readSensor();

  if (valor <= menor) return 0;  // Nivel bajo
  else if (valor <= medio) return 1;  // Nivel medio
  else return 2;  // Nivel alto
}

// FUNCIÓN calibrarUnNivel() - Lectura interactiva con timeout
int calibrarUnNivel(const char* mensaje) {
  Serial.println("Coloca el sensor en el " + String(mensaje) + "/n");
  Serial.println("Escribe '1' en el monitor serial para continuar (" + String(CONFIRM_TIMEOUT/1000) + "s) ...");

  
  while (Serial.available()) Serial.read(); // limpiar buffer previo

  unsigned long start = millis();
  bool confirmado = false;
  while (millis() - start < CONFIRM_TIMEOUT) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == '1') { confirmado = true; break; }
    }
    delay(10);
  }

  if (!confirmado) Serial.println("No se confirmó en tiempo. Se usará medición automática.");
  else Serial.println("Confirmado, midiendo...");

  // === NUEVO MÉTODO: 5 mediciones, cada una promediada ===
  long total = 0;
  const int numMediciones = 5;

  for (int i = 0; i < numMediciones; i++) {
    int lectura = readSensor();     // ya promedia 10 lecturas
    total += lectura;

    Serial.println("Medición "+ String(i + 1) + " (promedio interno): " + String(lectura));
    delay(200);
  }

  int promedio = (int)(total / numMediciones);

  Serial.println(">> Promedio FINAL del nivel: " + String(promedio) + "/n");

  while (Serial.available()) Serial.read(); // limpiar buffer
  return promedio;
}

// FUNCIÓN calibrarNiveles()
void calibrarNiveles(int *bajo, int *medio, int *alto) {
  Serial.println("===== INICIADO EL PROCESO DE CALIBRACIÓN DEL SENSOR DE NIVEL =====\n");
  *bajo  = calibrarUnNivel("1er tercio (poca agua)");
  *medio = calibrarUnNivel("2do tercio (medio)");
  *alto  = calibrarUnNivel("3er tercio (lleno)");
  Serial.println("===== SENSOR DE NIVEL CALIBRADO =====");
}

// ===== ENVÍO DE DATOS AL SERVIDOR MEDIANTE HTTP =====
void enviarDatosAServidor(float temperatura, float humedad, int nivel_agua, bool boolean) {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/x-www-form-urlencoded");
    
    // Preparar los datos en formato requerido por el servidor
    String datos = "temp=" + String(temperatura, 2) + 
                  "&hum=" + String(humedad, 2) + "&nivel_agua=" + String(nivel_agua) + "&estabilidad=" + (boolean ? "1" : "0");;
    
    Serial.println("Enviando datos al servidor...");
    Serial.println("Datos: temp="+String(temperatura)+", hum="+String(humedad)+", nivel_agua="+String(nivel_agua)+", estabilidad="+String(boolean));
    
    int httpResponseCode = http.POST(datos);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Respuesta del servidor: "+String(response));
      
      if (httpResponseCode == 200) Serial.println("Datos enviados correctamente al servidor");
      else Serial.println("Error en la respuesta del servidor: " + String(httpResponseCode));

    } else Serial.println("Error en la conexión HTTP: " + String(httpResponseCode));
    
    http.end();
  } else Serial.println("Error: No hay conexión WiFi");
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  // Configuración del ADC
  analogReadResolution(12);
  analogSetPinAttenuation(sensorPin, ADC_11db);

  // Pines de LEDs
  pinMode(PINVERDE, OUTPUT);
  pinMode(PINAMARILLO, OUTPUT);
  pinMode(PINROJO, OUTPUT);
  pinMode(sensorPin, INPUT);

  // Conexión WiFi
  Serial.println("Conectando a WiFi " + String(ssid));
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("@");
  }
  Serial.println("\nWiFi conectado!\nIP del ESP32: "+String( WiFi.localIP()));

  // Inicializar DHT
  dht.begin();
  sensor_t sensor;
  dht.temperature().getSensor(&sensor);
  delayMS = sensor.min_delay/1000;

  // Calibración del sensor de nivel
  calibrarNiveles(&nivelBajo, &nivelMedio, &nivelAlto);  // Mantener la función de calibración original
  Serial.println("Bajo: " + String(nivelBajo) + "Medio:" + String(nivelMedio) + "Alto: " + String(nivelAlto));
  Serial.println("Iniciando operación normal con envío de datos cada 6 segundos...\n");
}

void loop() {
  unsigned long currentMillis = millis();
  
  // Verificar si han pasado 6 segundos para enviar los datos
  if (currentMillis - previousMillis >= intervaloEnvio) {
    previousMillis = currentMillis;
    
    // Lectura de temperatura y humedad
    sensors_event_t tempEvent, humEvent;
    dht.temperature().getEvent(&tempEvent);
    dht.humidity().getEvent(&humEvent);
    
    float temperatura = 0.0, humedad = 0.0;
    int nivel_agua = -1;
    
    if (!isnan(tempEvent.temperature)) temperatura = tempEvent.temperature;
    if (!isnan(humEvent.relative_humidity)) humedad = humEvent.relative_humidity;
    nivel_agua = clasificarAgua(nivelBajo, nivelMedio, nivelAlto)*50; // Determinar el nivel de agua

    enviarDatosAServidor(temperatura, humedad, nivel_agua, dU); // Enviar los datos al servidor
  }
  
  // Control de LEDs basado en temperatura (mantiene la funcionalidad original)
  sensors_event_t tempEvent;
  dht.temperature().getEvent(&tempEvent);
  
  if (!isnan(tempEvent.temperature)) {
    float temp = tempEvent.temperature;
    if (temp > tR+variation || temp < tR-variation) {
      digitalWrite(PINVERDE, LOW);
      digitalWrite(PINROJO, HIGH);
      if (dU) cnt = 6;
      dU = false;
    } else {
      digitalWrite(PINROJO, LOW);
      digitalWrite(PINVERDE, HIGH);
      if (!dU) cnt = 6;
      dU = true;
    }
  }
  
  // Parpadeo del LED amarillo
  if (cnt > 0) {
    encendido = !encendido;
    digitalWrite(PINAMARILLO, encendido ? HIGH : LOW);
    cnt--;
  } else if (cnt == 0) digitalWrite(PINAMARILLO, LOW);
}

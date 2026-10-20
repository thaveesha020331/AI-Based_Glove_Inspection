// =====================================================
// ESP32-C3 COMPONENT 3
// SERIAL SENSOR + RELAY STATUS
// =====================================================

#include <Arduino.h>

// -----------------------------------------------------
// SENSOR PINS
// -----------------------------------------------------

#define VERIFY_SENSOR_1  0
#define VERIFY_SENSOR_2  10

#define SPEED_SENSOR_1   1
#define SPEED_SENSOR_2   3

// -----------------------------------------------------
// RELAY PINS
// -----------------------------------------------------

#define RELAY_1  5
#define RELAY_2  6
#define RELAY_3  7
#define RELAY_4  4

// -----------------------------------------------------
// LOGIC
// -----------------------------------------------------

// E18-D80NK sensors
#define SENSOR_ACTIVE LOW

// Your relay module
#define RELAY_ON  LOW
#define RELAY_OFF HIGH

// -----------------------------------------------------
// SERIAL UPDATE INTERVAL
// -----------------------------------------------------

const unsigned long STATUS_INTERVAL_MS = 100;
const unsigned long SORT_ACTUATION_DELAY_MS = 0;
const unsigned long SORT_RELAY_PULSE_MS = 500;

unsigned long previousStatusTime = 0;

bool defectPulsePending = false;
bool orientationPulsePending = false;
bool defectRelayActive = false;
bool orientationRelayActive = false;
unsigned long defectDueAt = 0;
unsigned long orientationDueAt = 0;
unsigned long defectOffAt = 0;
unsigned long orientationOffAt = 0;


// =====================================================
// SENSOR FUNCTION
// =====================================================

bool sensorDetected(int pin) {
  const int FILTER_SAMPLES = 5;
  const int FILTER_THRESHOLD = 5;
  int activeCount = 0;
  for (int index = 0; index < FILTER_SAMPLES; index++) {
    if (digitalRead(pin) == SENSOR_ACTIVE) {
      activeCount++;
    }
    if (index < FILTER_SAMPLES - 1) {
      delayMicroseconds(300);
    }
  }
  return activeCount >= FILTER_THRESHOLD;
}


// =====================================================
// RELAY FUNCTION
// =====================================================

bool relayIsOn(int pin) {
  return digitalRead(pin) == RELAY_ON;
}


void setRelay(int relayPin, bool state) {

  if (state) {
    digitalWrite(relayPin, RELAY_ON);
  }
  else {
    digitalWrite(relayPin, RELAY_OFF);
  }
}


void allRelaysOff() {

  setRelay(RELAY_1, false);
  setRelay(RELAY_2, false);
  setRelay(RELAY_3, false);
  setRelay(RELAY_4, false);
  defectPulsePending = false;
  orientationPulsePending = false;
  defectRelayActive = false;
  orientationRelayActive = false;
}


// R1 = damaged-glove reject, R2 = wrong-orientation reject.
// The delayed, non-blocking pulse lets serial telemetry continue normally.
void scheduleSortPulse(bool defective) {
  unsigned long dueAt = millis() + SORT_ACTUATION_DELAY_MS;
  if (defective) {
    // A damaged glove always uses the damage bin; cancel a not-yet-fired
    // orientation command for the same inspection window.
    orientationPulsePending = false;
    defectPulsePending = true;
    defectDueAt = dueAt;
  }
  else {
    orientationPulsePending = true;
    orientationDueAt = dueAt;
  }
}


void updateSortPulses() {
  unsigned long now = millis();

  if (defectPulsePending && (long)(now - defectDueAt) >= 0) {
    defectPulsePending = false;
    defectRelayActive = true;
    defectOffAt = now + SORT_RELAY_PULSE_MS;
    setRelay(RELAY_1, true);
  }
  if (orientationPulsePending && (long)(now - orientationDueAt) >= 0) {
    orientationPulsePending = false;
    orientationRelayActive = true;
    orientationOffAt = now + SORT_RELAY_PULSE_MS;
    setRelay(RELAY_2, true);
  }
  if (defectRelayActive && (long)(now - defectOffAt) >= 0) {
    defectRelayActive = false;
    setRelay(RELAY_1, false);
  }
  if (orientationRelayActive && (long)(now - orientationOffAt) >= 0) {
    orientationRelayActive = false;
    setRelay(RELAY_2, false);
  }
}


// =====================================================
// SEND STATUS AS JSON
// =====================================================

void sendStatusSerial() {

  bool s1 = sensorDetected(SPEED_SENSOR_1);
  bool s2 = sensorDetected(SPEED_SENSOR_2);

  bool v1 = sensorDetected(VERIFY_SENSOR_1);
  bool v2 = sensorDetected(VERIFY_SENSOR_2);

  bool r1 = relayIsOn(RELAY_1);
  bool r2 = relayIsOn(RELAY_2);
  bool r3 = relayIsOn(RELAY_3);
  bool r4 = relayIsOn(RELAY_4);


  Serial.print("{");

  Serial.print("\"type\":\"c3_status\",");

  Serial.print("\"uptime_ms\":");
  Serial.print(millis());
  Serial.print(",");


  // ---------------- SENSOR DATA ----------------

  Serial.print("\"sensors\":{");

  Serial.print("\"speed_s1\":");
  Serial.print(s1 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"speed_s2\":");
  Serial.print(s2 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"verify_v1\":");
  Serial.print(v1 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"verify_v2\":");
  Serial.print(v2 ? "true" : "false");

  Serial.print("},");


  // ---------------- RELAY DATA ----------------

  Serial.print("\"relays\":{");

  Serial.print("\"relay1\":");
  Serial.print(r1 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"relay2\":");
  Serial.print(r2 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"relay3\":");
  Serial.print(r3 ? "true" : "false");
  Serial.print(",");

  Serial.print("\"relay4\":");
  Serial.print(r4 ? "true" : "false");

  Serial.print("}");

  Serial.println("}");
}


// =====================================================
// SERIAL COMMAND PROCESSING
// =====================================================
// Optional:
// Allows relay testing from PC.
//
// Commands:
//
// R1_ON
// R1_OFF
// R2_ON
// R2_OFF
// R3_ON
// R3_OFF
// R4_ON
// R4_OFF
// ALL_OFF
// DEFECT_PULSE
// ORIENTATION_PULSE
// CAMERA_LIGHT_ON / CAMERA_LIGHT_OFF
// WARNING_ON / WARNING_OFF
//
// =====================================================

void processSerialCommand() {

  if (!Serial.available()) {
    return;
  }

  String command = Serial.readStringUntil('\n');

  command.trim();


  if (command == "R1_ON") {

    setRelay(RELAY_1, true);

  }
  else if (command == "R1_OFF") {

    setRelay(RELAY_1, false);

  }
  else if (command == "R2_ON") {

    setRelay(RELAY_2, true);

  }
  else if (command == "R2_OFF") {

    setRelay(RELAY_2, false);

  }
  else if (command == "R3_ON") {

    setRelay(RELAY_3, true);

  }
  else if (command == "R3_OFF") {

    setRelay(RELAY_3, false);

  }
  else if (command == "R4_ON") {

    setRelay(RELAY_4, true);

  }
  else if (command == "R4_OFF") {

    setRelay(RELAY_4, false);

  }
  else if (command == "ALL_OFF") {

    allRelaysOff();
  }
  else if (command == "DEFECT_PULSE") {
    scheduleSortPulse(true);
  }
  else if (command == "ORIENTATION_PULSE") {
    scheduleSortPulse(false);
  }
  else if (command == "CAMERA_LIGHT_ON") {
    setRelay(RELAY_3, true);
  }
  else if (command == "CAMERA_LIGHT_OFF") {
    setRelay(RELAY_3, false);
  }
  else if (command == "WARNING_ON") {
    setRelay(RELAY_4, true);
  }
  else if (command == "WARNING_OFF") {
    setRelay(RELAY_4, false);
  }
}


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  Serial.setTimeout(20);
  delay(500);


  // ---------------- Sensors ----------------

  pinMode(SPEED_SENSOR_1, INPUT);
  pinMode(SPEED_SENSOR_2, INPUT);

  pinMode(VERIFY_SENSOR_1, INPUT);
  pinMode(VERIFY_SENSOR_2, INPUT);


  // ---------------- Relays ----------------

  pinMode(RELAY_1, OUTPUT);
  pinMode(RELAY_2, OUTPUT);
  pinMode(RELAY_3, OUTPUT);
  pinMode(RELAY_4, OUTPUT);


  // Safe startup
  allRelaysOff();


  Serial.println(
    "{\"type\":\"system\",\"status\":\"ready\"}"
  );
}


// =====================================================
// LOOP
// =====================================================

void loop() {

  // Receive optional commands from computer
  processSerialCommand();
  updateSortPulses();


  // Send status every 500 ms
  if (
    millis() - previousStatusTime
    >= STATUS_INTERVAL_MS
  ) {

    previousStatusTime = millis();

    sendStatusSerial();
  }
}

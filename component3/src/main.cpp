#include <ArduinoJson.h>
#include <WebServer.h>
#include <WiFi.h>

#include "secrets.h"
#include "sorting_controller.h"

namespace {
WebServer server(80);
SortingController sorter;

void sendError(const int code, const char* message) {
  JsonDocument response;
  response["error"] = message;
  String body;
  serializeJson(response, body);
  server.send(code, "application/json", body);
}

void handleDecision() {
  if (!server.hasArg("plain")) {
    sendError(400, "missing_json_body");
    return;
  }

  JsonDocument request;
  if (deserializeJson(request, server.arg("plain"))) {
    sendError(400, "invalid_json");
    return;
  }

  const String eventId = request["event_id"] | "";
  const String decisionValue = request["decision"] | "";
  Decision decision;
  if (!parseDecision(decisionValue, decision)) {
    sendError(422, "unknown_decision");
    return;
  }

  String error;
  if (!sorter.queueEvent(eventId, decision, error)) {
    sendError(error == "sorter_busy" ? 409 : 422, error.c_str());
    return;
  }

  JsonDocument response;
  response["event_id"] = eventId;
  response["status"] = "decision_received";
  String body;
  serializeJson(response, body);
  server.send(202, "application/json", body);
}

void handleStatus() {
  const SortEvent& event = sorter.event();
  JsonDocument response;
  response["event_id"] = event.eventId;
  response["decision"] = decisionToString(event.decision);
  response["state"] = stateToString(event.state);
  response["speed_mps"] = event.speedMps;
  response["travel_time_ms"] = event.travelTimeMs;
  response["trigger_wait_ms"] = event.triggerWaitMs;
  response["actual_destination"] = event.actualDestination;
  response["sorting_status"] = event.status;
  String body;
  serializeJson(response, body);
  server.send(200, "application/json", body);
}

void handleHealth() {
  JsonDocument response;
  response["status"] = WiFi.status() == WL_CONNECTED ? "ok" : "degraded";
  response["ip"] = WiFi.localIP().toString();
  response["uptime_ms"] = millis();
  String body;
  serializeJson(response, body);
  server.send(200, "application/json", body);
}
}  // namespace

void setup() {
  Serial.begin(115200);
  sorter.begin();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
  }
  Serial.printf("\nComponent 3 ready at http://%s\n",
                WiFi.localIP().toString().c_str());

  server.on("/decision", HTTP_POST, handleDecision);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/health", HTTP_GET, handleHealth);
  server.onNotFound([]() { sendError(404, "not_found"); });
  server.begin();
}

void loop() {
  server.handleClient();
  sorter.update();
  delay(1);
}


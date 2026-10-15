# HTTP API

The ESP32-C3 serves JSON over the local Wi-Fi network. The serial monitor
prints its assigned IP address at 115200 baud.

## Submit a decision

`POST /decision` with `Content-Type: application/json`:

```json
{
  "event_id": "GLOVE_0001",
  "decision": "DEFECTIVE"
}
```

The accepted decision values are `ACCEPT`, `DEFECTIVE`, and
`WRONG_ORIENTATION`. A valid request returns HTTP 202. The API returns 400 for
malformed JSON, 422 for invalid fields, and 409 while another glove is being
processed.

## Read status

`GET /status` returns the currently stored event and computed timing:

```json
{
  "event_id": "GLOVE_0001",
  "decision": "DEFECTIVE",
  "state": "COMPLETE",
  "speed_mps": 0.52,
  "travel_time_ms": 576.92,
  "trigger_wait_ms": 496.92,
  "actual_destination": "DEFECTIVE_BIN",
  "sorting_status": "CORRECT"
}
```

`GET /health` returns Wi-Fi status, IP address, and device uptime. The canonical
request and response schemas are under `integration/c2_c3/`.

For a manual end-to-end request:

```powershell
python component3/tools/send_decision.py http://192.168.1.120 `
  GLOVE_0001 DEFECTIVE --wait
```


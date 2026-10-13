# Component 2 to Component 3 contract

Component 2 sends one final decision per glove to `POST /decision`. The
`event_id` is the correlation key used by downstream status and analytics.

```json
{"event_id": "GLOVE_0001", "decision": "DEFECTIVE"}
```

Successful requests return HTTP 202. Invalid decisions return 422, and a new
request received during a physical sorting cycle returns 409. The PC should
retry transport failures, but it must reuse the same event ID when retrying.

The firmware's `GET /status` response follows `status.schema.json`. Component
4 should treat `COMPLETE` and `ERROR` as terminal states.


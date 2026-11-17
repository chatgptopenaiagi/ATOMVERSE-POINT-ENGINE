# Future ATOMVERSE AI integration boundary

The existing [ATOMVERSE AI](https://github.com/chatgptopenaiagi/ATOMVERSE-AI) application remains independent and unchanged. Point Engine currently runs and records on its own. No cross-application transport is claimed as implemented.

A future adapter should consume a read-only, versioned event envelope rather than reading GUI widgets or manipulating the renderer:

```json
{
  "schema": "atomverse-point-event/2",
  "entity_id": "UUID",
  "session_id": "UUID",
  "event_sequence": 123,
  "simulation_tick": 240,
  "simulation_time": 1.0,
  "utc_ns": 0,
  "monotonic_ns": 0,
  "classification": "MATHEMATICAL_SIMULATION",
  "kind": "state_snapshot",
  "payload": {}
}
```

The numeric zero timestamps above are placeholders, not measurements. The adapter must preserve the source identifiers, record schema version and capture-gap policy. Observed hardware, simulated state, derived mappings and AI interpretations keep separate classifications. Consumer applications must not convert explanations into physical measurements. Any commands returned to Point Engine must pass `validate_command` and the same bounded execution queue, with explicit operator control for model-generated proposals.

No shared credentials, model weights, private inventories or mutable database access are part of this contract. Multiple entities, remote execution and a persistent service require their own measured, versioned design before implementation.

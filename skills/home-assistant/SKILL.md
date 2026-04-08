---
name: home-assistant
description: >
  This skill should be used when the user asks to "turn on the lights",
  "check the temperature", "what's on in the house", "control the thermostat",
  "manage my dashboard", "search for entities", "run an automation",
  "set brightness", "turn off the pool light", "what lights are on",
  or any other Home Assistant smart home control or monitoring request.
  Triggers on keywords: lights, thermostat, sensor, automation, scene,
  switch, fan, climate, lock, cover, media player, dashboard, home assistant, HA.
metadata:
  version: "0.1.0"
---

# Home Assistant Control

Manage the user's Home Assistant instance "Roy Rogers" (HA 2025.6.1, timezone America/Phoenix) through three CLI tools. All tools are at `~/home/ha-tools/bin/` and load credentials from `~/home/ha-tools/.env`.

## Tool Selection

Pick the right tool for the job:

| Need | Tool | Command |
|------|------|---------|
| Quick state check | ha-api | `ha-api state <entity_id>` |
| Search entities by name | ha-api | `ha-api search <term>` |
| Call a service (lights, switches, etc.) | ha-api | `ha-api call <domain.service> <entity_id> [json]` |
| List all entities of a type | ha-api | `ha-api states <domain>` |
| Entity/device/area registry queries | ha-ws | `ha-ws entity\|device\|area list` |
| Detailed state with all attributes | ha-ws | `ha-ws state <entity_id>` |
| Service calls with named parameters | ha-ws | `ha-ws call <domain.service> entity_id=<id> key=value` |
| List available services | ha-ws | `ha-ws services [domain]` |
| Dashboard listing and export | ha-dashboard | `ha-dashboard list\|get\|export\|save` |

Use `ha-api` for simple, fast operations (single REST call). Use `ha-ws` for registry lookups, batch operations, or when you need detailed attributes.

## Interpreting Requests

When the user says something like "turn on the kitchen lights":

1. **Identify the domain** — lights, switches, fans, climate, automation, scene, etc.
2. **Find the entity** — search by name if the entity_id isn't obvious: `ha-api search kitchen`
3. **Pick the service** — `light.turn_on`, `switch.toggle`, `climate.set_temperature`, etc.
4. **Execute** — `ha-api call light.turn_on light.kitchen`

For ambiguous names, search first and confirm with the user if multiple matches exist.

## Known Areas

Living Room, Kitchen, Bedroom, Office, Master Bedroom, Parlor, Outside (Backyard)

## Common Operations

### Controlling devices

```bash
# Lights
ha-api call light.turn_on light.kitchen
ha-api call light.turn_off light.pool
ha-ws call light.turn_on entity_id=light.living_room brightness=128 color_temp=300

# Switches
ha-api call switch.turn_on switch.porch
ha-api call switch.toggle switch.garage

# Climate
ha-api call climate.set_temperature climate.thermostat '{"temperature": 72}'

# Scenes and automations
ha-api call scene.turn_on scene.movie_night
ha-api call automation.trigger automation.morning_routine
```

### Checking status

```bash
# Single entity
ha-api state light.kitchen
ha-ws state sensor.temperature_living_room   # detailed attributes

# All of a type
ha-api states light         # all lights
ha-api states binary_sensor # all binary sensors
ha-api states automation    # all automations

# Search by name
ha-api search kitchen       # anything with "kitchen"
ha-api search motion        # motion sensors
```

### History and debugging

```bash
ha-api history sensor.temperature_living_room 48  # 48h history
ha-ws search light.kitchen                        # find related entities
ha-ws info                                        # system info
```

### Dashboard management

```bash
ha-dashboard list                          # list all dashboards
ha-dashboard get                           # default dashboard config
ha-dashboard export backup.json            # save to file
ha-dashboard save modified.json            # push changes
ha-dashboard get control-panel             # specific dashboard
```

## Response Style

- After executing a command, report the result concisely: "Kitchen lights are now on" not a raw JSON dump.
- For state queries, summarize in natural language. Include specific values (brightness, temperature) when relevant.
- If a command fails, check the entity_id exists (`ha-api search <term>`) and suggest corrections.
- For `--json` output, parse it and present the relevant information naturally.

## Output Flags

Append `--json` to any command for raw JSON (useful for parsing). Append `--quiet` for minimal output (just the value). Default output is human-readable.

## Full CLI Reference

See `references/cli-reference.md` for complete command documentation including all flags, value syntax, and advanced patterns.

# Home Assistant CLI Tools — Full Reference

## ha-api (REST API)

Fast single-request tool for state checks, searches, and service calls.

### Commands

```
ha-api states [filter]                  # List entities, optional grep filter
ha-api state <entity_id>                # Single entity state (JSON)
ha-api search <term>                    # Search by name or entity_id
ha-api domains                          # List service domains
ha-api call <domain.service> [entity_id] [json]   # Call a service
ha-api attr <entity_id>                 # Get attributes only
ha-api history <entity_id> [hours]      # State history (default 24h)
ha-api get <path>                       # Raw GET /api/<path>
ha-api post <path> [json]               # Raw POST /api/<path>
```

### Service Call Examples

```bash
# Simple on/off
ha-api call light.turn_on light.kitchen
ha-api call switch.turn_off switch.porch

# With JSON data
ha-api call climate.set_temperature climate.thermostat '{"temperature": 72}'
ha-api call light.turn_on light.living_room '{"brightness": 200, "color_temp": 350}'
ha-api call media_player.play_media media_player.living_room '{"media_content_id": "...", "media_content_type": "music"}'

# Automations and scenes
ha-api call automation.trigger automation.morning_routine
ha-api call scene.turn_on scene.movie_night
```

## ha-ws (WebSocket API)

Powerful tool for registry operations, detailed state queries, and batch work.

### Entity Registry

```
ha-ws entity list                       # All entities
ha-ws entity get <entity_id>            # Single entity detail
ha-ws entity update <entity_id> name="New Name" disabled_by=null
```

### Device Registry

```
ha-ws device list                       # All devices
ha-ws device get <device_id>            # Single device
```

### Area Registry

```
ha-ws area list                         # All areas
ha-ws area create "Room Name"           # Create area
ha-ws area update <area_id> name="New Name"
ha-ws area delete <area_id>
```

### State and Services

```
ha-ws state <entity_id>                 # State + all attributes
ha-ws states [domain]                   # All states (optional domain filter)
ha-ws services [domain]                 # List available services

# Service calls with key=value syntax
ha-ws call light.turn_on entity_id=light.kitchen brightness=255
ha-ws call switch.toggle entity_id=switch.porch
ha-ws call climate.set_temperature entity_id=climate.thermostat temperature=72
```

### System

```
ha-ws config                            # HA configuration
ha-ws info                              # Version, location, timezone
ha-ws search <entity_id>               # Find related entities
ha-ws raw <msg_type> [json]             # Send any WS message
```

### Label Registry

```
ha-ws label list                        # All labels
ha-ws label create <name> [color=X icon=X description=X]
ha-ws label update <label_id> key=value
ha-ws label delete <label_id>
ha-ws label assign <entity_id> <label_id> [label_id ...]  # Add labels to entity
```

### Floor Registry

```
ha-ws floor list                        # All floors
ha-ws floor create <name> [level=X icon=X]
ha-ws floor update <floor_id> key=value
ha-ws floor delete <floor_id>
```

### Group Management

```
ha-ws group list                        # All groups with members
ha-ws group get <group_entity_id>       # Group details
ha-ws group create <object_id> name="Name" entities=a,b,c
ha-ws group remove <object_id>
```

### Scene Management

```
ha-ws scene list                        # All scenes
ha-ws scene get <scene_id>              # Scene config (via REST)
ha-ws scene create <scene_id> <json_file>  # Create from JSON file
ha-ws scene delete <scene_id>           # Delete scene
ha-ws scene activate <scene_entity_id>  # Turn on scene
ha-ws scene snapshot <entity_id> [...]  # Capture current states as JSON
ha-ws scene reload                      # Reload scenes from config
```

### Config Entries (Integrations)

```
ha-ws entries list                      # All integrations with state
ha-ws entries get <entry_id>            # Single integration details
```

### Health Audit

```
ha-ws audit summary                     # Overview: counts for all categories
ha-ws audit unavailable                 # Entities with state "unavailable"
ha-ws audit unknown                     # Entities with state "unknown"
ha-ws audit disabled                    # Disabled entities
ha-ws audit stale [hours]               # Not updated in N hours (default: 72)
ha-ws audit orphaned                    # Entities with missing device/integration
ha-ws audit dead-devices                # Devices where all entities are bad
```

### Value Syntax for ha-ws

- Strings: `name=Kitchen` or `name="Living Room"` (quote if spaces)
- Numbers: `brightness=255`
- Booleans: `hidden=true` / `hidden=false`
- Null: `disabled_by=null`
- Lists: `entities=light.one,light.two,light.three` (comma-separated)
- JSON: Pass inline `'{"key": "value"}'`

## ha-dashboard (Dashboard Management)

Remote Lovelace dashboard configuration management.

### Commands

```
ha-dashboard list                       # List all dashboards
ha-dashboard get [url_path]             # Get config JSON (default if omitted)
ha-dashboard export output.json [url_path]  # Save config to file
ha-dashboard save input.json [url_path]     # Push config to HA
```

### Dashboard Workflow

1. Export: `ha-dashboard export dashboard.json`
2. Edit `dashboard.json`
3. Push: `ha-dashboard save dashboard.json`
4. Refresh browser to see changes

## Output Flags

All tools support:
- Default: Human-readable formatted text
- `--json`: Raw JSON output (useful for piping/parsing)
- `--quiet`: Minimal output (just the value)

## Performance Notes

- `ha-api` is faster for simple queries (single HTTP request)
- `ha-ws` is more powerful for registry operations and batch work
- `ha-dashboard` works fully remote — no local file sync needed

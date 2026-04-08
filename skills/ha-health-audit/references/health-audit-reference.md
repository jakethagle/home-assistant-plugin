# Health Audit CLI Reference

## Audit Commands

```
ha-ws audit summary                   # Overview: counts for all categories
ha-ws audit unavailable               # Entities with state "unavailable"
ha-ws audit unknown                   # Entities with state "unknown"
ha-ws audit disabled                  # Entities disabled by user or integration
ha-ws audit stale [hours]             # Entities not updated in N hours (default: 72)
ha-ws audit orphaned                  # Entities referencing non-existent devices/integrations
ha-ws audit dead-devices              # Devices where ALL entities are unavailable/unknown
```

### Summary Output

```
Health Audit Summary
  Total entities:            250
  Total devices:              45
  Unavailable entities:       12
  Unknown entities:            3
  Disabled entities:           8
  Stale entities (72h+):       5
  Orphaned entities:           2
  Dead devices:                1
```

### Unavailable/Unknown/Stale Output

```
  entity_id                                            state           last_updated        friendly_name
```

### Disabled Output

```
  entity_id                                            disabled_by=user|integration    name
```

### Orphaned Output

```
  entity_id                                            reason (device/config entry not found)
```

### Dead Devices Output

```
  device_id         device_name                              (N entities)
    - entity_id (state)
    - entity_id (state)
```

## Config Entries (Integrations)

```
ha-ws entries list                    # List all integrations
ha-ws entries get <entry_id>          # Details of one integration
```

### Entries List Output

```
  entry_id          domain                    title                          state=loaded|setup_error|...
```

### Integration States

| State | Meaning |
|-------|---------|
| `loaded` | Running normally |
| `setup_error` | Failed to initialize — check config/credentials |
| `setup_retry` | Retrying after failure |
| `not_loaded` | Disabled or dependency missing |
| `failed_unload` | Could not cleanly stop |

## Cleanup Commands

### Disable entity (reversible)
```
ha-ws entity update <entity_id> disabled_by=user
```

### Re-enable entity
```
ha-ws entity update <entity_id> disabled_by=null
```

### Remove entity (permanent)
```
ha-ws entity remove <entity_id>
```

### Remove device from integration (permanent)
```
ha-ws raw config/device_registry/remove_config_entry '{"device_id": "<id>", "config_entry_id": "<entry_id>"}'
```

## Stale Threshold Guide

| Entity Type | Expected Update Frequency | Recommended Stale Threshold |
|-------------|--------------------------|----------------------------|
| Temperature/humidity sensors | Every 1-5 minutes | 1-2 hours |
| Motion/door binary sensors | On state change only | 24-72 hours (may be legitimately idle) |
| Battery level sensors | Every 1-12 hours | 24-48 hours |
| Weather entities | Every 30-60 minutes | 2-4 hours |
| Media players | On state change | 24 hours |
| Switches/lights | On state change | 24-72 hours |

## Output Flags

All commands support:
- `--json` — Raw JSON output (useful for piping/scripting)
- `--quiet` — Minimal output

---
name: ha-health-audit
description: >
  This skill should be used when the user asks about "broken entities",
  "stale devices", "unavailable entities", "cleanup entities", "dead devices",
  "orphaned entities", "health check", "audit my setup", "what's offline",
  "which devices are down", "remove stale entities", "entity cleanup",
  "what's not working", "find broken things", "troubleshoot devices",
  or any request to identify, diagnose, or clean up problematic entities and devices.
  Triggers on keywords: broken, stale, unavailable, unknown, cleanup, dead, orphaned,
  health, audit, offline, down, not working, troubleshoot, disabled.
metadata:
  version: "0.1.0"
---

# Health Audit

Identify and clean up broken, stale, and orphaned entities and devices in Home Assistant. Uses the `ha-ws` CLI tool bundled with this plugin.

## Quick Start

Run a full health check: `ha-ws audit summary`

This returns counts for every category. Then drill into specifics with `ha-ws audit <category>`.

## Audit Commands

| Command | What It Finds |
|---------|---------------|
| `ha-ws audit summary` | Overview with counts for all categories |
| `ha-ws audit unavailable` | Entities stuck in "unavailable" state |
| `ha-ws audit unknown` | Entities stuck in "unknown" state |
| `ha-ws audit disabled` | Entities disabled by user or integration |
| `ha-ws audit stale [hours]` | Entities not updated in N hours (default: 72) |
| `ha-ws audit orphaned` | Entities whose device or integration no longer exists |
| `ha-ws audit dead-devices` | Devices where ALL entities are unavailable/unknown |

## Understanding Entity States

| State | Meaning | Action |
|-------|---------|--------|
| `unavailable` | Device/integration is offline or unreachable | Check network, power, integration status |
| `unknown` | Integration is working but can't determine state | Usually temporary; persistent = investigate |
| Disabled by `user` | User intentionally disabled this entity | Leave alone unless user asks to re-enable |
| Disabled by `integration` | Integration disabled it (unsupported/broken) | Check integration docs or update |
| Stale | Entity hasn't updated in a long time | Dead battery, lost WiFi, or device removed |
| Orphaned | References a device/integration that no longer exists | Safe to remove |

## Diagnosis Workflows

### Unavailable Entity

1. Run `ha-ws audit unavailable` to get the list
2. For a specific entity, check its integration: `ha-ws entity get <entity_id> --json` to find `config_entry_id`
3. Check the integration status: `ha-ws entries list` — look for matching entry and its `state`
4. Check if other entities from the same device are also affected: `ha-ws search <entity_id>`
5. Common causes:
   - Integration down: restart it via HA UI or reload
   - Device offline: check power, WiFi, Zigbee/Z-Wave range
   - Credentials expired: re-authenticate the integration
   - HA update broke it: check release notes

### Stale Entity

1. Run `ha-ws audit stale` (defaults to 72h) or `ha-ws audit stale 24` for stricter threshold
2. Check `last_updated` via `ha-ws state <entity_id>` to see exactly when it last reported
3. Consider the entity type:
   - **Battery sensors**: may only report every few hours — 72h could be normal
   - **Temperature/humidity**: should update every few minutes
   - **Binary sensors (motion/door)**: only update on state change — may legitimately be stale
   - **Weather**: should update hourly
4. For battery devices, check battery level: `ha-api attr <entity_id>` and look for `battery_level`

### Orphaned Entity

1. Run `ha-ws audit orphaned`
2. These are safe to remove — their parent device or integration is gone
3. Disable first as a safety step: `ha-ws entity update <entity_id> disabled_by=user`
4. If confirmed safe, remove: `ha-ws entity remove <entity_id>`

### Dead Device

1. Run `ha-ws audit dead-devices` — shows devices where ALL entities are unavailable/unknown
2. Check the device details: `ha-ws device get <device_id> --json`
3. If the device is truly gone (removed from home, broken hardware):
   - Remove it via HA UI or: `ha-ws raw config/device_registry/remove_config_entry '{"device_id": "<id>", "config_entry_id": "<entry_id>"}'`
4. If the device should be working: check power, network, re-pair/re-interview

## Cleanup Actions (Safety Guide)

**Always recommend this order:**

1. **Investigate first** — Check the integration, device, and network before removing anything
2. **Disable before remove** — `ha-ws entity update <entity_id> disabled_by=user` is reversible
3. **Remove only orphans** — Entities with no parent device/integration are safe to remove
4. **Confirm with user** — Never bulk-remove without explicit approval
5. **Remove entity** — `ha-ws entity remove <entity_id>` (permanent, cannot be undone)
6. **Remove device** — `ha-ws raw config/device_registry/remove_config_entry '{"device_id": "...", "config_entry_id": "..."}'`

**Never auto-remove entities that are just unavailable** — they may come back when the device is powered on, re-paired, or the integration is restarted.

## Integration Health

Check which integrations are having problems:

```bash
ha-ws entries list          # List all integrations with their state
ha-ws entries get <id>      # Details of a specific integration
```

Integration states:
- `loaded` — Working normally
- `setup_error` — Failed to set up (check logs)
- `setup_retry` — Retrying setup
- `not_loaded` — Disabled or failed to load

## Response Style

- Present audit results grouped by severity: orphaned (safe to clean) > dead devices (investigate) > unavailable (may recover) > stale (monitor)
- For each category, give a count and actionable next steps
- When suggesting cleanup, always note what's reversible (disable) vs permanent (remove)
- If the instance looks healthy (few/no issues), say so clearly

## Full CLI Reference

See `references/health-audit-reference.md` for complete command documentation.

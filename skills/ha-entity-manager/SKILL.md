---
name: ha-entity-manager
description: >
  This skill should be used when the user asks to "rename an entity",
  "move entity to area", "assign a label", "create a group", "manage groups",
  "create a scene", "set up a scene", "snapshot current state", "organize entities",
  "manage floors", "label entities", "bulk update entities", "combine lights into a group",
  "set up movie mode", or any other entity organization, grouping, or scene management request.
  Triggers on keywords: group, scene, label, floor, organize, rename entity, move entity,
  bulk update, snapshot, assign area, entity management.
metadata:
  version: "0.1.0"
---

# Entity Manager

Organize, group, and configure Home Assistant entities using the `ha-ws` CLI tool bundled with this plugin. The tool is on PATH automatically and loads credentials from the plugin configuration.

## Tool Selection

| Need | Command |
|------|---------|
| List/create/manage labels | `ha-ws label list\|create\|update\|delete\|assign` |
| List/create/manage floors | `ha-ws floor list\|create\|update\|delete` |
| List/create/manage groups | `ha-ws group list\|get\|create\|remove` |
| List/manage scenes | `ha-ws scene list\|get\|create\|delete\|activate\|snapshot\|reload` |
| Rename entity | `ha-ws entity update <entity_id> name="New Name"` |
| Move entity to area | `ha-ws entity update <entity_id> area_id=<area_id>` |
| Assign label to entity | `ha-ws label assign <entity_id> <label_id>` |
| Find entities | `ha-api search <term>` |
| List areas | `ha-ws area list` |

## Organization Hierarchy

HA organizes things in this hierarchy: **Floors > Areas > Devices > Entities**

- **Floors** group areas (e.g., "First Floor", "Second Floor")
- **Areas** group devices (e.g., "Kitchen", "Living Room")
- **Labels** are cross-cutting tags (e.g., "critical", "battery-powered", "guest-accessible")
- **Groups** combine entities for unified control (e.g., "All Downstairs Lights")

## Workflows

### Organizing Entities

1. Check current structure: `ha-ws floor list`, `ha-ws area list`, `ha-ws label list`
2. Search for entities: `ha-api search <term>`
3. Move to area: `ha-ws entity update <entity_id> area_id=<area_id>`
4. Assign label: `ha-ws label assign <entity_id> <label_id>`

To rename: `ha-ws entity update <entity_id> name="New Friendly Name"`

### Creating Groups

Groups combine multiple entities for unified control. When you turn on a group, all members turn on.

```bash
# Create a group
ha-ws group create downstairs_lights name="Downstairs Lights" entities=light.kitchen,light.living_room,light.hallway

# List existing groups
ha-ws group list

# See group members
ha-ws group get group.downstairs_lights

# Remove a group
ha-ws group remove downstairs_lights
```

**When to use groups vs areas:**
- **Groups** = unified control (one service call affects all members)
- **Areas** = organizational (physical location, used for targeting in automations)

### Scene Management

Scenes capture a set of entity states to restore later.

**Snapshot current state (most common):**
```bash
# Capture current state of specific entities
ha-ws scene snapshot light.kitchen light.living_room climate.thermostat
# Outputs JSON scene config - save to file, then create:
ha-ws scene snapshot light.kitchen light.living_room > /tmp/scene.json
ha-ws scene create movie_night /tmp/scene.json
```

**Create from scratch:**
Write a JSON file with the scene definition:
```json
{
  "name": "Movie Night",
  "entities": {
    "light.living_room": {"state": "on", "brightness": 50, "color_temp": 400},
    "light.kitchen": {"state": "off"},
    "media_player.tv": {"state": "on"}
  }
}
```
Then: `ha-ws scene create movie_night /tmp/movie_night.json`

**Other scene operations:**
```bash
ha-ws scene list                         # List all scenes
ha-ws scene get <scene_id>               # View scene config
ha-ws scene activate scene.movie_night   # Activate a scene
ha-ws scene delete <scene_id>            # Delete a scene
ha-ws scene reload                       # Reload scenes from config
```

### Label Management

Labels tag entities across areas/devices for cross-cutting organization.

```bash
# Create labels
ha-ws label create "Battery Powered" color=yellow icon=mdi:battery
ha-ws label create "Guest Room" color=blue

# List labels
ha-ws label list

# Assign label to entity (merges with existing labels)
ha-ws label assign light.guest_bedroom <label_id>
ha-ws label assign sensor.guest_temp <label_id>

# Update/delete labels
ha-ws label update <label_id> name="New Name" color=red
ha-ws label delete <label_id>
```

### Floor Management

Floors group areas into vertical levels.

```bash
ha-ws floor list
ha-ws floor create "First Floor" level=1
ha-ws floor create "Second Floor" level=2
# Assign area to floor via area update
ha-ws area update <area_id> floor_id=<floor_id>
```

### Bulk Operations

To apply changes to many entities, combine search + iteration:

1. Find entities: `ha-api search kitchen --json`
2. For each result, apply the change: `ha-ws entity update <id> area_id=kitchen`

When the user asks to do something to "all X entities" or "everything in Y area", search first, confirm the list with the user, then iterate.

## Response Style

- After creating a group, list its members to confirm
- After creating a scene, summarize what entities/states it captures
- After assigning labels or moving entities, confirm what changed
- For bulk operations, show a count and summary, not every individual change
- When entities aren't found, suggest a search term

## Full CLI Reference

See `references/entity-manager-reference.md` for complete command documentation.

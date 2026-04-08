# Entity Manager CLI Reference

## Label Commands

```
ha-ws label list                              # List all labels
ha-ws label create <name> [color=X icon=X description=X]  # Create label
ha-ws label update <label_id> [key=value...]  # Update label properties
ha-ws label delete <label_id>                 # Delete label
ha-ws label assign <entity_id> <label_id> [label_id...]   # Add labels to entity
```

### Label Properties

- `name` — Display name
- `color` — Color for UI display (e.g., red, blue, yellow, green, purple, orange, pink, cyan, grey)
- `icon` — MDI icon (e.g., `mdi:battery`, `mdi:star`)
- `description` — Optional description text

### Label Assign Behavior

`label assign` reads the entity's current labels and merges in the new ones. It never removes existing labels. To remove a label from an entity, use `ha-ws entity update <entity_id> labels=<remaining_label_ids>` with only the labels you want to keep.

## Floor Commands

```
ha-ws floor list                              # List all floors
ha-ws floor create <name> [level=X icon=X]    # Create floor
ha-ws floor update <floor_id> [key=value...]  # Update floor
ha-ws floor delete <floor_id>                 # Delete floor
```

### Floor Properties

- `name` — Display name
- `level` — Integer level number (0 = ground, 1 = first floor above, -1 = basement)
- `icon` — MDI icon

### Assigning Areas to Floors

Use the area update command: `ha-ws area update <area_id> floor_id=<floor_id>`

## Group Commands

```
ha-ws group list                              # List all groups with members
ha-ws group get <group_entity_id>             # Show group details and members
ha-ws group create <object_id> name="X" entities=a,b,c  # Create/update group
ha-ws group remove <object_id>               # Remove a dynamic group
```

### Group Create Syntax

- `object_id` — The part after `group.` (e.g., `downstairs_lights` creates `group.downstairs_lights`)
- `name` — Friendly name (quote if spaces)
- `entities` — Comma-separated list of entity IDs (no spaces)

### Group Behavior

- Groups created via `group.set` service are dynamic and survive restarts
- Controlling a group (e.g., `light.turn_on group.my_lights`) affects all members
- Group state reflects members: "on" if any member is on, "off" if all off
- The `entity_id` attribute lists all member entities

## Scene Commands

```
ha-ws scene list                              # List all scenes
ha-ws scene get <scene_id>                    # Get scene config (REST)
ha-ws scene create <scene_id> <json_file>     # Create/update scene (REST)
ha-ws scene delete <scene_id>                 # Delete scene (REST)
ha-ws scene activate <scene_entity_id>        # Turn on a scene
ha-ws scene snapshot <entity_id> [...]        # Capture current states as scene JSON
ha-ws scene reload                            # Reload scenes from config
```

### Scene JSON Format

```json
{
  "name": "Scene Name",
  "entities": {
    "light.living_room": {
      "state": "on",
      "brightness": 128,
      "color_temp": 350
    },
    "light.kitchen": {
      "state": "off"
    },
    "climate.thermostat": {
      "state": "heat",
      "temperature": 72
    },
    "media_player.tv": {
      "state": "on",
      "volume_level": 0.3,
      "source": "HDMI 1"
    }
  }
}
```

### Scene Entity State Attributes

Attributes captured by `snapshot` (domain-dependent):

**Lights:** brightness, color_temp, rgb_color, xy_color, hs_color, color_mode
**Climate:** temperature, target_temp_high, target_temp_low, hvac_mode, fan_mode, swing_mode, preset_mode
**Media Players:** media_content_id, media_content_type, volume_level, source, sound_mode

### Scene ID vs Entity ID

- Scene ID (used in `get`, `create`, `delete`): a short identifier like `movie_night`
- Scene entity ID (used in `activate`): `scene.movie_night`

### Persistent vs Temporary Scenes

- Scenes created via `ha-ws scene create` (REST API) are **persistent** — saved to config, survive restarts
- Scenes created via `scene.create` service call are **temporary** — lost on restart
- Always use the REST approach (`ha-ws scene create`) for permanent scenes

## Output Flags

All commands support:
- `--json` — Raw JSON output
- `--quiet` — Minimal output

# Home Assistant Plugin

Control and monitor a Home Assistant instance through natural language. Wraps three CLI tools (`ha-api`, `ha-ws`, `ha-dashboard`) that provide full access to entities, services, and dashboard configuration.

## Components

| Component | Name | Purpose |
|-----------|------|---------|
| Skill | `home-assistant` | Interprets natural language requests and dispatches to the right CLI tool |

## Setup

### Prerequisites

The HA CLI tools must be installed at `~/home/ha-tools/` with credentials configured in `~/home/ha-tools/.env`:

```
HA_URL=http://homeassistant.local:8123
HA_TOKEN=your_long_lived_access_token
```

The tools directory must contain:
- `bin/ha-api` — REST API client (bash)
- `bin/ha-ws` — WebSocket client (python3)
- `bin/ha-dashboard` — Dashboard manager (python3)

Run `~/home/ha-tools/install.sh` if not already set up.

### PATH

Either add to your PATH:

```bash
export PATH="$HOME/home/ha-tools/bin:$PATH"
```

Or the skill will use full paths automatically.

## Usage Examples

Just ask naturally:

- "Turn on the kitchen lights"
- "What lights are on?"
- "Set the thermostat to 72"
- "Search for motion sensors"
- "Show me the dashboard list"
- "What's the temperature in the living room?"
- "Turn off everything in the bedroom"
- "Run the morning routine automation"
- "Export the control panel dashboard"

# Home Assistant Plugin for Claude Code

Control and monitor your Home Assistant instance using natural language through [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Turn lights on, check sensor values, manage dashboards, organize entities into groups and scenes, and audit your setup for broken devices -- all by just asking.

## Features

**3 skills** that understand natural language requests:

| Skill | What it does | Example prompts |
|-------|-------------|-----------------|
| `home-assistant` | Device control, state queries, service calls, dashboard management | "Turn on the kitchen lights", "What's the temperature?", "Show me the dashboard list" |
| `ha-entity-manager` | Groups, scenes, labels, floors, bulk entity organization | "Create a group of all living room lights", "Set up a movie night scene", "Label all battery devices" |
| `ha-health-audit` | Find and clean up broken, stale, and orphaned entities | "What entities are broken?", "Run a health audit", "Clean up orphaned entities" |

**3 CLI tools** bundled with the plugin (auto-added to PATH):

| Tool | Protocol | Best for |
|------|----------|----------|
| `ha-api` | REST | Quick state checks, searches, simple service calls |
| `ha-ws` | WebSocket | Registry operations, labels, groups, scenes, health audits |
| `ha-dashboard` | WebSocket | Dashboard listing, export, import |

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.8+ (for WebSocket tools)
- `curl` and `jq` (for REST tool)
- A Home Assistant instance with a long-lived access token

## Installation

```bash
claude plugin add jakethagle/home-assistant-plugin
```

Or for local development:

```bash
claude --plugin-dir /path/to/home-assistant-plugin
```

## Configuration

When you enable the plugin, you'll be prompted for two values:

1. **Home Assistant URL** -- Your instance URL (e.g., `http://homeassistant.local:8123`)
2. **Home Assistant Token** -- A long-lived access token (stored securely in your system keychain)

### Creating a token

1. Open your Home Assistant instance in a browser
2. Click your profile icon (bottom-left)
3. Go to **Security** tab
4. Scroll to **Long-Lived Access Tokens**
5. Click **Create Token**, give it a name, and copy the value

## Usage

Just ask naturally. The plugin picks the right skill and tool automatically.

### Control devices

```
> Turn on the kitchen lights
> Set the thermostat to 72
> Toggle the garage switch
> Run the morning routine automation
```

### Check status

```
> What lights are on?
> What's the temperature in the living room?
> Search for motion sensors
> Show me all automations
```

### Organize entities

```
> Create a group of all downstairs lights
> Set up a movie night scene with dim lights and TV on
> Label all battery-powered devices
> Move the guest sensor to the guest bedroom area
```

### Health audit

```
> Run a health audit
> What entities are unavailable?
> Find stale devices that haven't updated in 24 hours
> Clean up orphaned entities
```

### Dashboard management

```
> List all dashboards
> Export the control panel dashboard
> Show me the main dashboard config
```

## CLI Reference

The tools are available directly in the Claude Code bash environment:

```bash
# REST API (fast, single request)
ha-api states light              # List all lights
ha-api state light.kitchen       # Single entity
ha-api search kitchen            # Search by name
ha-api call light.turn_on light.kitchen
ha-api history sensor.temp 48    # 48h history

# WebSocket API (powerful, registry access)
ha-ws entity list                # All entities
ha-ws device list                # All devices
ha-ws area list                  # All areas
ha-ws call light.turn_on entity_id=light.kitchen brightness=255
ha-ws label create "Battery" color=yellow
ha-ws group create downstairs_lights name="Downstairs" entities=light.a,light.b
ha-ws scene snapshot light.kitchen light.living_room
ha-ws audit summary              # Health overview
ha-ws audit unavailable          # Offline entities
ha-ws audit stale 24             # Not updated in 24h

# Dashboard management
ha-dashboard list                # List dashboards
ha-dashboard export backup.json  # Export config
ha-dashboard save modified.json  # Push changes
```

All tools support `--json` for raw JSON output and `--quiet` for minimal output.

## How it works

The plugin bundles three bash/Python CLI tools that communicate with Home Assistant via its REST and WebSocket APIs. A `SessionStart` hook automatically installs the Python `websockets` dependency into a plugin-managed virtual environment on first use.

Skills are Markdown files that teach Claude how to interpret natural language requests and dispatch to the right CLI tool with the right arguments. No custom code runs in Claude -- it just calls the CLI tools via bash.

```
Plugin
├── bin/           CLI tools (auto-added to PATH)
├── lib/           Python implementations
├── skills/        Natural language skill definitions
└── hooks.json     Auto-setup on session start
```

## License

MIT

# Home Assistant Plugin for Claude Code

Control and monitor your Home Assistant instance using natural language through [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Turn lights on, check sensor values, manage dashboards, organize entities into groups and scenes, read config files and logs, and audit your setup for broken devices -- all by just asking.

## Features

**3 skills** that understand natural language requests:

| Skill | What it does | Example prompts |
|-------|-------------|-----------------|
| `home-assistant` | Device control, state queries, service calls, dashboard management | "Turn on the kitchen lights", "What's the temperature?", "Show me the dashboard list" |
| `ha-entity-manager` | Groups, scenes, labels, floors, bulk entity organization | "Create a group of all living room lights", "Set up a movie night scene", "Label all battery devices" |
| `ha-health-audit` | Find and clean up broken, stale, and orphaned entities | "What entities are broken?", "Run a health audit", "Clean up orphaned entities" |

**4 CLI tools** bundled with the plugin (auto-added to PATH):

| Tool | Protocol | Best for |
|------|----------|----------|
| `ha-api` | REST | Quick state checks, searches, simple service calls |
| `ha-ws` | WebSocket | Registry operations, labels, groups, scenes, integration management, health audits |
| `ha-dashboard` | WebSocket | Dashboard listing, export, import |
| `ha-ssh` | SSH | Config files, .storage access, full logs, Supervisor API |

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.8+ (for WebSocket and SSH tools)
- `curl` and `jq` (for REST tool)
- A Home Assistant instance with a long-lived access token

### SSH prerequisites (optional but recommended)

SSH access unlocks features that the REST and WebSocket APIs cannot provide -- reading `.storage` files, full integration options/data, complete logs, YAML config files, and the Supervisor API.

To use `ha-ssh`, you need:

1. **The [Advanced SSH & Web Terminal](https://github.com/hassio-addons/addon-ssh) addon** installed and running in Home Assistant
2. **An SSH key** added to the addon's authorized keys
3. **Local network access** to your Home Assistant server (see [SSH and local network access](#ssh-and-local-network-access) below)

#### Installing the SSH addon

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**
2. Search for **Advanced SSH & Web Terminal** and click **Install**
3. After installation, go to the addon's **Configuration** tab
4. Add your SSH public key to **Authorized Keys**
5. Start (or restart) the addon

> If you don't have an SSH key, `ha-setup --ssh` will offer to generate one for you.

#### SSH and local network access

SSH connects directly to port 22 on your Home Assistant server. This port is **not** typically exposed through routers or available via external DNS names (e.g., `myhouse.duckdns.org`). You must use the **local/LAN IP address** of your Home Assistant server (e.g., `192.168.1.100`).

This means:
- Your machine running Claude Code must be on the **same local network** as your Home Assistant server
- The SSH host should be a LAN IP (e.g., `192.168.1.x`) or local hostname, **not** the external URL you use for the REST API
- If you use a VPN to access your home network remotely, SSH will work through the VPN tunnel

> **Example:** Your `HA_URL` might be `https://myhouse.duckdns.org:8123` for API access, but `HA_SSH_HOST` should be `192.168.1.100` (the server's local IP).

To find your Home Assistant server's local IP:
- Check your router's device list
- In Home Assistant, go to **Settings > System > Network**
- On the HA host, run `hostname -I`

## Installation

```bash
claude plugin add jakethagle/home-assistant-plugin
```

Or for local development:

```bash
claude --plugin-dir /path/to/home-assistant-plugin
```

## Configuration

Run `ha-setup` to configure the plugin interactively. On first session start, the plugin will prompt you if not yet configured.

### API credentials (required)

```bash
ha-setup
```

You'll be prompted for:

1. **Home Assistant URL** -- Your instance URL (e.g., `http://homeassistant.local:8123`)
2. **Home Assistant Token** -- A long-lived access token

Or non-interactively:

```bash
ha-setup --url https://homeassistant.local:8123 --token eyJhbGci...
```

#### Creating a token

1. Open your Home Assistant instance in a browser
2. Click your profile icon (bottom-left)
3. Go to **Security** tab
4. Scroll to **Long-Lived Access Tokens**
5. Click **Create Token**, give it a name, and copy the value

### SSH configuration (optional)

```bash
ha-setup --ssh
```

This will:
1. Check for an existing SSH key (or generate a new ed25519 key)
2. Display your public key to add to the SSH addon's authorized keys
3. Prompt for the SSH host (LAN IP), port, and user
4. Test the SSH connection

Or non-interactively:

```bash
ha-setup --ssh --ssh-host 192.168.1.100 --ssh-key ~/.ssh/id_ed25519
```

### Configuration file

All credentials are stored in `~/.config/ha-claude/config` with `0600` permissions:

```
HA_URL=https://homeassistant.local:8123
HA_TOKEN=eyJhbGci...
HA_SSH_HOST=192.168.1.100
HA_SSH_PORT=22
HA_SSH_USER=root
HA_SSH_KEY=~/.ssh/id_ed25519
```

View current config with `ha-setup --show`.

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

### Integration management

```
> Disable the old Govee cloud integration
> Delete the broken config entry
> Update the govee2mqtt addon API key
```

### SSH access (config, logs, Supervisor)

```
> Show me the HomeKit bridge entity filter
> What's in configuration.yaml?
> Show me the last 50 lines of HA Core logs
> What addons are installed?
> Validate the HA configuration
> Restart the Zigbee addon
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
ha-api delete-entry <entry_id>   # Delete a config entry

# WebSocket API (powerful, registry access)
ha-ws entity list                # All entities
ha-ws device list                # All devices
ha-ws area list                  # All areas
ha-ws call light.turn_on entity_id=light.kitchen brightness=255
ha-ws label create "Battery" color=yellow
ha-ws group create downstairs_lights name="Downstairs" entities=light.a,light.b
ha-ws scene snapshot light.kitchen light.living_room
ha-ws entries delete <entry_id>  # Delete integration
ha-ws entries disable <entry_id> # Disable integration
ha-ws entries enable <entry_id>  # Re-enable integration
ha-ws audit summary              # Health overview
ha-ws audit unavailable          # Offline entities
ha-ws audit stale 24             # Not updated in 24h

# Dashboard management
ha-dashboard list                # List dashboards
ha-dashboard export backup.json  # Export config
ha-dashboard save modified.json  # Push changes

# SSH access (config, .storage, logs, Supervisor API)
ha-ssh test                      # Test SSH connectivity
ha-ssh storage list              # List .storage files
ha-ssh storage read core.config_entries       # Read a .storage file
ha-ssh storage entries homekit                # Config entries with full options/data
ha-ssh storage entry-options <entry_id>       # Single entry's hidden options/data
ha-ssh config read                            # Read configuration.yaml
ha-ssh config read automations.yaml           # Read any config file
ha-ssh config validate                        # Validate HA config
ha-ssh logs core 50                           # Last 50 lines of HA Core logs
ha-ssh logs supervisor                        # Supervisor logs
ha-ssh logs addon core_ssh                    # Addon-specific logs
ha-ssh supervisor info                        # HA version, machine, arch
ha-ssh supervisor addons                      # List installed addons
ha-ssh supervisor restart --confirm           # Restart HA Core
ha-ssh supervisor addon-restart zigbee2mqtt --confirm  # Restart an addon
ha-ssh supervisor addon-options <slug> key=value       # Update addon config
ha-ssh exec "ls /config/custom_components"    # Run any command
```

All tools support `--json` for raw JSON output and `--quiet` for minimal output.

### Why ha-ssh?

The REST and WebSocket APIs deliberately hide certain data -- notably the `options` and `data` fields of config entries. For example, to see which entities are included in a HomeKit bridge or what port a Zigbee integration uses, you need `ha-ssh storage entry-options <entry_id>`. The typical workflow is:

1. Find the entry ID: `ha-ws entries list`
2. Read full options: `ha-ssh storage entry-options <entry_id>`

`ha-ssh` also provides access to YAML config files, complete system logs, and Supervisor operations (addon management, config validation, restarts) that aren't available through the other APIs.

## How it works

The plugin bundles four bash/Python CLI tools that communicate with Home Assistant via its REST API, WebSocket API, and SSH. A `SessionStart` hook automatically installs the Python `websockets` dependency into a plugin-managed virtual environment on first use.

Skills are Markdown files that teach Claude how to interpret natural language requests and dispatch to the right CLI tool with the right arguments. No custom code runs in Claude -- it just calls the CLI tools via bash.

```
Plugin
├── bin/           CLI tools (auto-added to PATH)
├── lib/           Python implementations + shared config loader
├── skills/        Natural language skill definitions
└── hooks.json     Auto-setup on session start
```

## Troubleshooting

### SSH connection refused

The Advanced SSH & Web Terminal addon may not be running. Check **Settings > Add-ons** in Home Assistant and ensure the addon is started.

### SSH authentication failed

Your SSH public key may not be in the addon's authorized keys. Go to the addon's **Configuration** tab, add your public key, and restart the addon. Re-run `ha-setup --ssh` to verify.

### Cannot reach SSH host

You may not be on the same local network as your Home Assistant server, or the IP address may have changed. Verify the LAN IP and ensure your machine can reach it (`ping 192.168.1.100`).

### Plugin not configured

Run `ha-setup` to set your Home Assistant URL and token. The plugin will remind you on session start if not configured.

## License

MIT

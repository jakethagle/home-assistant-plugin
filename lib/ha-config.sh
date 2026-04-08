# ha-config.sh — Shared credential loader for Home Assistant CLI tools
# Source this file from bin/ scripts to get HA_URL and HA_TOKEN

HA_CONFIG_DIR="$HOME/.config/ha-claude"
HA_CONFIG_FILE="$HA_CONFIG_DIR/config"

# Load from config file
if [[ -f "$HA_CONFIG_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$HA_CONFIG_FILE"
fi

# Plugin env vars override config file (future-proofing)
HA_URL="${CLAUDE_PLUGIN_OPTION_home_assistant_url:-$HA_URL}"
HA_TOKEN="${CLAUDE_PLUGIN_OPTION_home_assistant_token:-$HA_TOKEN}"

# Validate
if [[ -z "${HA_URL:-}" || -z "${HA_TOKEN:-}" ]]; then
  echo "Error: Home Assistant not configured. Run: ha-setup" >&2
  exit 1
fi

HA_URL="${HA_URL%/}"
export HA_URL HA_TOKEN

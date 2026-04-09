# Home Assistant Plugin Tool Audit Report

**Date:** 2026-04-08
**Context:** Investigated and partially resolved a multi-integration Govee mess (cloud, LAN, govee2mqtt), cleaned up rate-limited entities, and updated HomeKit bridges. This report documents every tool interaction, what worked, what failed, and validated fixes against HA's actual APIs.

---

## Table of Contents

1. [Session Summary](#1-session-summary)
2. [Tool Call Inventory](#2-tool-call-inventory)
3. [Bugs Found](#3-bugs-found)
4. [Missing Capabilities](#4-missing-capabilities)
5. [HA API Reference (Validated)](#5-ha-api-reference-validated)
6. [Recommended Fixes](#6-recommended-fixes)
7. [Skill Prompt Improvements](#7-skill-prompt-improvements)

---

## 1. Session Summary

**Goal:** Diagnose why Govee devices were broken/duplicated/rate-limited, consolidate onto govee2mqtt, remove old integrations, and fix HomeKit bridge routing.

**What we accomplished:**
- Identified 3 competing Govee integrations (`govee` cloud, `govee_lan`, `govee2mqtt` addon)
- Set govee2mqtt addon API key via Supervisor REST API through SSH (`POST /addons/{slug}/options`)
- Restarted govee2mqtt addon, confirmed it discovered all bulbs (H6003, H6075, H6072)
- Failed to delete config entries programmatically — user had to do it in the HA UI

**What blocked us:**
- `ha-ssh logs addon <slug>` is broken (argument parsing bug)
- No tool supports `DELETE` HTTP method against HA Core API
- Supervisor proxy only forwards GET/POST, not DELETE
- `ha-ws entries` only supports `list|get`, not `delete` or `disable`

---

## 2. Tool Call Inventory

### ha-ssh (Python, `lib/ha-ssh.py`)

| Command | Result | Notes |
|---------|--------|-------|
| `ha-ssh supervisor info` | SUCCESS | Clean output |
| `ha-ssh supervisor addons` | SUCCESS | Listed all 11 addons with state |
| `ha-ssh supervisor addon-info b9845f46_govee2mqtt` | SUCCESS | Full addon config including schema |
| `ha-ssh supervisor addon-restart b9845f46_govee2mqtt --confirm` | SUCCESS | |
| `ha-ssh config read` | SUCCESS | Read configuration.yaml |
| `ha-ssh storage read core.config_entries` | SUCCESS | Both plain and `--json` modes |
| `ha-ssh storage read core.entity_registry --json` | SUCCESS | |
| `ha-ssh storage read core.device_registry --json` | SUCCESS | |
| `ha-ssh storage entry-options 01KNQKCVT90C` | SUCCESS | Found entry, showed options/data |
| `ha-ssh logs core 20` | SUCCESS | Returned last 20 lines |
| `ha-ssh logs addon b9845f46_govee2mqtt 30` | **BUG** | `ValueError: invalid literal for int() with base 10: 'b9845f46_govee2mqtt'` |
| `ha-ssh logs addon govee2mqtt 30` | **BUG** | Same ValueError |
| `ha-ssh exec 'curl ... /addons/{slug}/options'` | SUCCESS | After fixing shell quoting |
| `ha-ssh exec 'curl -X DELETE ...'` | FAILED | Supervisor proxy returns 405 Method Not Allowed for DELETE |

### ha-api (Bash, `bin/ha-api`)

| Command | Result | Notes |
|---------|--------|-------|
| `ha-api search govee` | SUCCESS | Found entities |
| `ha-api search govee --json` | SUCCESS | But note: `--json` is passed to jq, not the API |
| `ha-api states light` | SUCCESS | Human-readable output |
| `ha-api states light --json` | **FAILED** | `--json` flag not supported by `cmd_states` — passed as filter arg to `grep -i`, causing silent failure or jq parse error |
| `ha-api search h6003` | SUCCESS | Empty result (correct) |
| `ha-api search bedroom` | SUCCESS | Found matching entities |
| `ha-api state sensor.my_ecobee_temperature --json` | SUCCESS | `cmd_state` uses `jq .` — always JSON |
| `ha-api call config.remove_entry ...` | FAILED | No such HA service |

### ha-ws (Python, `lib/ha-ws.py`)

| Command | Result | Notes |
|---------|--------|-------|
| `ha-ws entries list --json` | SUCCESS | Listed config entries with state |
| `ha-ws state light.bedroom_lamp` | SUCCESS | "Entity not found" — correct |
| `ha-ws state light.h6072_0e6a` | SUCCESS | Full attributes |
| `ha-ws call config.entries_delete entry_id=...` | FAILED | No such service (it's a REST endpoint, not a service) |
| `ha-ws call homeassistant.reload_config_entry entry_id=...` | FAILED | Entry stuck in non-recoverable state (correct HA error, not a tool bug) |

### Workarounds Used

| What | How | Why |
|------|-----|-----|
| Set addon options | `ha-ssh exec 'curl -s -X POST ... http://supervisor/addons/{slug}/options'` | No native `ha-ssh` command for addon options |
| Read addon logs | `ha-ssh exec 'curl -s -H "..." http://supervisor/addons/{slug}/logs'` | `ha-ssh logs addon` is broken |
| Delete config entries | User did it in HA UI | No tool supports DELETE on config entries |

---

## 3. Bugs Found

### BUG 1: `ha-ssh logs addon <slug> [lines]` — Argument parsing crash

**File:** `lib/ha-ssh.py`, lines 291-314
**Severity:** Blocks all addon log access

```python
def cmd_logs(ssh, args, opts):
    sub = args[0] if args else "core"           # line 293: sub = "addon"
    lines = int(args[1]) if len(args) > 1 else 100  # line 294: BUG — args[1] is the slug!

    if sub == "addon":                            # line 302
        slug = args[1]                            # line 306: also reads args[1] as slug
        lines = int(args[2]) if len(args) > 2 else 100  # line 307: correct
```

**Problem:** Line 294 runs unconditionally BEFORE the `if sub == "addon"` check. When called as `ha-ssh logs addon my_addon 30`, `args[1]` is the slug string `"my_addon"`, not a number, so `int(args[1])` raises `ValueError`.

**Fix:** Defer the `lines` assignment. Move line 294 into the `elif sub in endpoint_map:` block:

```python
def cmd_logs(ssh, args, opts):
    sub = args[0] if args else "core"

    endpoint_map = {
        "core": "core/logs",
        "supervisor": "supervisor/logs",
        "host": "host/logs",
    }

    if sub == "addon":
        if len(args) < 2:
            print("Usage: ha-ssh logs addon <slug> [lines]", file=sys.stderr)
            return
        slug = args[1]
        lines = int(args[2]) if len(args) > 2 else 100
        endpoint = f"addons/{slug}/logs"
    elif sub in endpoint_map:
        lines = int(args[1]) if len(args) > 1 else 100
        endpoint = endpoint_map[sub]
    else:
        print(f"Unknown log source: {sub}", file=sys.stderr)
        return
```

### BUG 2: `ha-api states` does not support `--json` flag

**File:** `bin/ha-api`, lines 47-54
**Severity:** Low — confusing but not crashing (silently filters incorrectly)

```bash
cmd_states() {
  local filter="${1:-}"
  if [[ -n "$filter" ]]; then
    api_get "/states" | jq -r '...' | grep -i "$filter"
  else
    api_get "/states" | jq -r '...'
  fi
}
```

**Problem:** `ha-api` doesn't parse `--json`/`--quiet` flags globally. The `states` command treats any argument as a grep filter. So `ha-api states light --json` filters for "light" but the `--json` is either passed to grep or ignored. The output is always human-readable.

**Fix:** Add global flag parsing to `ha-api` (similar to how `ha-ws` and `ha-ssh` handle it), and in `cmd_states`, output `jq .` when `--json` is set:

```bash
# At the top, parse flags before the case statement
JSON_MODE=false
QUIET_MODE=false
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --json)  JSON_MODE=true ;;
    --quiet) QUIET_MODE=true ;;
    *)       ARGS+=("$arg") ;;
  esac
done
set -- "${ARGS[@]}"

# In cmd_states:
cmd_states() {
  local filter="${1:-}"
  if [[ "$JSON_MODE" == true ]]; then
    if [[ -n "$filter" ]]; then
      api_get "/states" | jq "[.[] | select(.entity_id | startswith(\"${filter}.\"))]"
    else
      api_get "/states" | jq .
    fi
  else
    # ... existing human-readable logic
  fi
}
```

---

## 4. Missing Capabilities

### CRITICAL: No way to delete config entries

**Impact:** Had to ask the user to delete integrations via the HA UI. This blocks a core workflow (removing broken/duplicate integrations).

**HA's actual API (validated from source code):**

Config entry deletion is a **REST-only** endpoint — there is no websocket command for it:

```
DELETE /api/config/config_entries/entry/{entry_id}
Authorization: Bearer <long-lived-access-token>
```

This is defined in `homeassistant/components/config/config_entries.py` as `ConfigManagerEntryResourceView` mapped to `/api/config/config_entries/entry/{entry_id}` with only the DELETE method.

**Why our tools can't reach it:**
1. `ha-api` only has `api_get()` and `api_post()` helper functions — no `api_delete()`
2. `ha-ssh exec curl -X DELETE http://supervisor/core/api/...` fails because the Supervisor proxy only forwards GET and POST
3. `ha-ws` has no websocket message type for deleting config entries (confirmed — HA doesn't define one)

**Recommended fix:** Add `api_delete()` to `ha-api` and a new command:

```bash
api_delete() {
  curl -sf -X DELETE -H "Authorization: Bearer $HA_TOKEN" \
    -H "Content-Type: application/json" \
    "$HA_URL/api$1"
}

cmd_delete_entry() {
  local entry_id="${1:?Usage: ha-api delete-entry <entry_id>}"
  api_delete "/config/config_entries/entry/$entry_id" | jq .
}
```

Also add to `ha-ws entries`:
```python
elif sub == "delete":
    entry_id = args[1] if len(args) > 1 else None
    if not entry_id:
        print("Usage: ha-ws entries delete <entry_id>", file=sys.stderr)
        return
    url, token = load_env()
    result = rest_request(url, token, "DELETE", f"config/config_entries/entry/{entry_id}")
    print(f"Deleted config entry: {entry_id}")
```

This pattern already exists — `cmd_scene` uses `rest_request()` for DELETE operations (line 657).

### MISSING: `ha-ws entries disable`

HA provides a websocket command for disabling config entries:

```json
{"type": "config_entries/disable", "entry_id": "<id>", "disabled_by": "user"}
```

To re-enable, send `disabled_by: null`. This should be added to `cmd_entries`.

### MISSING: `ha-ssh supervisor addon-options`

We had to use `ha-ssh exec 'curl ...'` to set addon options. A native command would be cleaner:

```python
elif sub == "addon-options":
    if len(args) < 2:
        print("Usage: ha-ssh supervisor addon-options <slug> key=value ...", file=sys.stderr)
        return
    slug = args[1]
    # Parse remaining args as key=value pairs
    options = {}
    for arg in args[2:]:
        if "=" in arg:
            k, _, v = arg.partition("=")
            options[k] = v
    result = ssh.supervisor_api("POST", f"addons/{slug}/options", {"options": options})
    print(json.dumps(result, indent=2))
```

### MISSING: `ha-api` generic DELETE support

The `ha-api` tool has `get` and `post` raw commands but no `delete`:

```bash
cmd_delete() {
  local path="${1:?Usage: ha-api delete <path>}"
  api_delete "/$path" | jq .
}
```

Add to the case statement: `delete) shift; cmd_delete "$@" ;;`

---

## 5. HA API Reference (Validated)

All of the following were validated against HA Core source code (`homeassistant/components/config/`).

### Config Entries (`config_entries.py`)

| Operation | Method | Endpoint/Type |
|-----------|--------|---------------|
| List entries | REST GET | `/api/config/config_entries/entry` |
| Delete entry | REST DELETE | `/api/config/config_entries/entry/{entry_id}` |
| Reload entry | REST POST | `/api/config/config_entries/entry/{entry_id}/reload` |
| Get single entry | WS | `config_entries/get` (filter client-side) |
| Disable entry | WS | `config_entries/disable` with `entry_id`, `disabled_by` |
| Update entry | WS | `config_entries/update` |
| Subscribe to changes | WS | `config_entries/subscribe` |
| Start config flow | REST POST | `/api/config/config_entries/flow` |
| Options flow | REST POST | `/api/config/config_entries/options/flow` |

### Entity Registry (`entity_registry.py`)

| Operation | Type |
|-----------|------|
| List entities | WS `config/entity_registry/list` |
| List for display | WS `config/entity_registry/list_for_display` |
| Get entity | WS `config/entity_registry/get` — requires `entity_id` |
| Get multiple | WS `config/entity_registry/get_entries` — requires `entity_ids` (list) |
| Update entity | WS `config/entity_registry/update` — `entity_id` + optional: `name`, `icon`, `area_id`, `disabled_by`, `hidden_by`, `new_entity_id`, `labels`, `aliases`, `categories`, `device_class`, `options_domain`, `options` |
| Remove entity | WS `config/entity_registry/remove` — requires `entity_id` |
| Get auto IDs | WS `config/entity_registry/get_automatic_entity_ids` — requires `entity_ids` (list) |

### Device Registry (`device_registry.py`)

| Operation | Type |
|-----------|------|
| List devices | WS `config/device_registry/list` |
| Update device | WS `config/device_registry/update` — `device_id` + optional: `area_id`, `disabled_by`, `labels`, `name_by_user` |
| Remove config entry from device | WS `config/device_registry/remove_config_entry` — `device_id` + `config_entry_id` |

### Supervisor Addon API

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Addon info | GET | `/addons/{slug}/info` |
| Addon logs | GET | `/addons/{slug}/logs` |
| Set options | POST | `/addons/{slug}/options` — body: `{"options": {...}}` |
| Start | POST | `/addons/{slug}/start` |
| Stop | POST | `/addons/{slug}/stop` |
| Restart | POST | `/addons/{slug}/restart` |
| Stats | GET | `/addons/{slug}/stats` |

**Supervisor proxy limitation:** The proxy at `http://supervisor/core/api/...` only forwards GET and POST. DELETE, PUT, and PATCH are NOT proxied. To use DELETE, you must hit the HA Core REST API directly (via `HA_URL`).

---

## 6. Recommended Fixes

### Priority 1 — Fix `ha-ssh logs addon` (broken, blocks addon debugging)

Fix the argument parsing in `cmd_logs` at `lib/ha-ssh.py:294`. See Bug 1 above for the exact fix.

### Priority 2 — Add config entry deletion

Add `ha-ws entries delete <entry_id>` using `rest_request(url, token, "DELETE", ...)` — the pattern already exists in `cmd_scene`. Also add `ha-api delete <path>` for generic DELETE support.

### Priority 3 — Add config entry disable/enable

Add `ha-ws entries disable <entry_id>` and `ha-ws entries enable <entry_id>` using the `config_entries/disable` websocket command.

### Priority 4 — Add `ha-ssh supervisor addon-options`

Native command for setting addon options instead of requiring `ha-ssh exec 'curl ...'`.

### Priority 5 — Add `--json` flag support to `ha-api`

Parse `--json` and `--quiet` globally in `ha-api` like the other tools do. At minimum, make `cmd_states` support JSON output.

---

## 7. Skill Prompt Improvements

### Current issues in the skill prompt

1. **The skill says `ha-ssh logs addon <slug> [lines]`** but this command is broken. Until fixed, the skill prompt should document the workaround:
   ```
   # Addon logs (workaround — native command has a bug):
   ha-ssh exec 'curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" http://supervisor/addons/<slug>/logs' | tail -n 30
   ```

2. **The skill doesn't mention DELETE limitations.** It should note:
   - Config entry deletion requires direct REST API DELETE (not through Supervisor proxy)
   - Currently must be done via HA UI or `ha-api delete` (once implemented)

3. **The skill table suggests `ha-ssh storage entry-options <id>` for "Config entry options/data"** — this works but reads from `.storage` file (stale until HA writes). For live state, `ha-ws entries get <id>` is better.

4. **Missing from the tool selection table:**
   - Setting addon options: `ha-ssh supervisor addon-options <slug> key=value` (not yet implemented)
   - Disabling integrations: `ha-ws entries disable <entry_id>` (not yet implemented)
   - Deleting integrations: `ha-ws entries delete <entry_id>` (not yet implemented)
   - Entity renaming: `ha-ws entity update <entity_id> new_entity_id=<new_id>`
   - Removing orphaned entities: `ha-ws entity remove <entity_id>`

5. **The skill should warn about entity ID collisions.** When govee2mqtt creates entities with names that match disabled entities from another integration, HA appends `_2`. The cleanup path is: remove old entity -> rename new entity.

### Suggested additions to skill prompt

```markdown
## Integration Management

### Removing integrations
Use `ha-ws entries delete <entry_id>` to remove a config entry.
If the entry is stuck in `failed_unload`, try restarting HA Core first:
`ha-ssh supervisor restart --confirm`

### Disabling/enabling integrations
`ha-ws entries disable <entry_id>`
`ha-ws entries enable <entry_id>`

### Entity cleanup after integration changes
When switching integrations, new entities may get `_2` suffixes due to
name collisions with old (disabled) entities. To fix:
1. Remove the old entity: `ha-ws entity remove <old_entity_id>`
2. Rename the new one: `ha-ws entity update <entity_id_2> new_entity_id=<clean_id>`

### Setting addon configuration
`ha-ssh supervisor addon-options <slug> key=value ...`
```

---

## Appendix: All HA API Endpoints Used in This Session

| What we did | Tool/API used | Worked? |
|------------|---------------|---------|
| Read .storage files | `ha-ssh storage read` (SSH + cat) | Yes |
| Get config entry details | `ha-ssh storage entry-options` (SSH + cat + parse) | Yes |
| List config entries | `ha-ws entries list` (WS `config_entries/get`) | Yes |
| Read entity registry | `ha-ssh storage read core.entity_registry` (SSH + cat) | Yes |
| Read device registry | `ha-ssh storage read core.device_registry` (SSH + cat) | Yes |
| Search entities | `ha-api search` (REST `GET /api/states` + jq filter) | Yes |
| Get entity state | `ha-ws state` (WS `get_states` + filter) | Yes |
| List all states | `ha-api states light` (REST `GET /api/states` + jq + grep) | Yes |
| Set addon options | `ha-ssh exec curl POST /addons/{slug}/options` | Yes (workaround) |
| Restart addon | `ha-ssh supervisor addon-restart` (SSH + Supervisor POST) | Yes |
| Get addon info | `ha-ssh supervisor addon-info` (SSH + Supervisor GET) | Yes |
| Get addon logs | `ha-ssh logs addon` | **No — bug** |
| Get addon logs | `ha-ssh exec curl GET /addons/{slug}/logs` | Yes (workaround) |
| Delete config entry | `ha-ssh exec curl DELETE ...` | **No — 405** |
| Delete config entry | `ha-ws call ...` | **No — not a service** |
| Delete config entry | User via HA UI | Yes (manual fallback) |

---

*Report generated from a real debugging session. All API details validated against HA Core source code on the `dev` branch.*

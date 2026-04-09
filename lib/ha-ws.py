"""ha-ws — Home Assistant WebSocket API CLI

Usage: ha-ws <command> [args...] [--json] [--quiet]
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

import websockets


def load_env():
    """Load Home Assistant credentials from config file or environment."""
    config_file = os.path.join(os.path.expanduser("~"), ".config", "ha-claude", "config")
    url = None
    token = None
    if os.path.isfile(config_file):
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("HA_URL="):
                    url = line[len("HA_URL="):]
                elif line.startswith("HA_TOKEN="):
                    token = line[len("HA_TOKEN="):]
    # Plugin env vars override config file
    url = os.environ.get("CLAUDE_PLUGIN_OPTION_home_assistant_url", url)
    token = os.environ.get("CLAUDE_PLUGIN_OPTION_home_assistant_token", token)
    if not url or not token:
        print("Error: Home Assistant not configured. Run: ha-setup", file=sys.stderr)
        sys.exit(1)
    return url.rstrip("/"), token


def parse_value(s):
    """Parse a string value into appropriate Python type."""
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.lower() == "null" or s.lower() == "none":
        return None
    # Quoted string
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Number
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_kv_args(args):
    """Parse key=value arguments into a dict."""
    result = {}
    for arg in args:
        if "=" in arg:
            key, _, value = arg.partition("=")
            # Split comma-separated values into lists (for entity lists etc.)
            if "," in value and not value.startswith("{") and not value.startswith('"'):
                result[key] = [parse_value(v.strip()) for v in value.split(",")]
            else:
                result[key] = parse_value(value)
        else:
            # Try parsing as JSON
            try:
                return json.loads(arg)
            except json.JSONDecodeError:
                pass
    return result


def rest_request(url, token, method, path, data=None):
    """Make a REST API request to Home Assistant."""
    req = urllib.request.Request(
        f"{url}/api/{path}",
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"REST {method} /{path} failed ({e.code}): {body}")


class HAWebSocket:
    def __init__(self, url, token):
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/api/websocket"
        self.token = token
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        # Wait for auth_required
        msg = json.loads(await self.ws.recv())
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected message: {msg}")
        # Send auth
        await self.ws.send(json.dumps({"type": "auth", "access_token": self.token}))
        msg = json.loads(await self.ws.recv())
        if msg.get("type") != "auth_ok":
            raise RuntimeError(f"Auth failed: {msg.get('message', 'unknown error')}")

    async def send(self, msg_type, **kwargs):
        self.msg_id += 1
        msg = {"id": self.msg_id, "type": msg_type, **kwargs}
        await self.ws.send(json.dumps(msg))
        while True:
            resp = json.loads(await self.ws.recv())
            if resp.get("id") == self.msg_id:
                if not resp.get("success", True):
                    error = resp.get("error", {})
                    raise RuntimeError(f"Error: {error.get('message', 'unknown')}")
                return resp.get("result", resp)

    async def close(self):
        if self.ws:
            await self.ws.close()


# --- Commands ---

async def cmd_entity(ws, args, opts):
    """Entity registry operations: list, get, update, remove"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config/entity_registry/list")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for e in result:
                disabled = " [disabled]" if e.get("disabled_by") else ""
                name = e.get("name") or e.get("original_name") or ""
                print(f"  {e['entity_id']:50s} {name}{disabled}")

    elif sub == "get":
        entity_id = args[1] if len(args) > 1 else None
        if not entity_id:
            print("Usage: ha-ws entity get <entity_id>", file=sys.stderr)
            return
        result = await ws.send("config/entity_registry/get", entity_id=entity_id)
        print(json.dumps(result, indent=2))

    elif sub == "update":
        entity_id = args[1] if len(args) > 1 else None
        if not entity_id or len(args) < 3:
            print("Usage: ha-ws entity update <entity_id> key=value ...", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/entity_registry/update", entity_id=entity_id, **data)
        print(json.dumps(result, indent=2))

    elif sub == "remove":
        entity_id = args[1] if len(args) > 1 else None
        if not entity_id:
            print("Usage: ha-ws entity remove <entity_id>", file=sys.stderr)
            return
        result = await ws.send("config/entity_registry/remove", entity_id=entity_id)
        print("Removed:", entity_id)
    else:
        print(f"Unknown entity subcommand: {sub}", file=sys.stderr)


async def cmd_device(ws, args, opts):
    """Device registry operations: list, get, update"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config/device_registry/list")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for d in result:
                name = d.get("name_by_user") or d.get("name") or "(unnamed)"
                area = d.get("area_id") or ""
                print(f"  {d['id'][:16]}  {name:40s}  area={area}")

    elif sub == "get":
        device_id = args[1] if len(args) > 1 else None
        if not device_id:
            print("Usage: ha-ws device get <device_id>", file=sys.stderr)
            return
        # List all and filter -- HA WS has no direct device get
        result = await ws.send("config/device_registry/list")
        matches = [d for d in result if d["id"] == device_id]
        if matches:
            print(json.dumps(matches[0], indent=2))
        else:
            print(f"Device not found: {device_id}", file=sys.stderr)

    elif sub == "update":
        device_id = args[1] if len(args) > 1 else None
        if not device_id or len(args) < 3:
            print("Usage: ha-ws device update <device_id> key=value ...", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/device_registry/update", device_id=device_id, **data)
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown device subcommand: {sub}", file=sys.stderr)


async def cmd_area(ws, args, opts):
    """Area registry operations: list, create, update, delete"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config/area_registry/list")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for a in result:
                print(f"  {a['area_id']:30s} {a.get('name', '')}")

    elif sub == "create":
        name = args[1] if len(args) > 1 else None
        if not name:
            print("Usage: ha-ws area create <name>", file=sys.stderr)
            return
        result = await ws.send("config/area_registry/create", name=name)
        print(json.dumps(result, indent=2))

    elif sub == "update":
        area_id = args[1] if len(args) > 1 else None
        if not area_id or len(args) < 3:
            print("Usage: ha-ws area update <area_id> key=value ...", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/area_registry/update", area_id=area_id, **data)
        print(json.dumps(result, indent=2))

    elif sub == "delete":
        area_id = args[1] if len(args) > 1 else None
        if not area_id:
            print("Usage: ha-ws area delete <area_id>", file=sys.stderr)
            return
        result = await ws.send("config/area_registry/delete", area_id=area_id)
        print("Deleted:", area_id)
    else:
        print(f"Unknown area subcommand: {sub}", file=sys.stderr)


async def cmd_state(ws, args, opts):
    """Get state of a single entity."""
    entity_id = args[0] if args else None
    if not entity_id:
        print("Usage: ha-ws state <entity_id>", file=sys.stderr)
        return
    result = await ws.send("get_states")
    matches = [s for s in result if s["entity_id"] == entity_id]
    if matches:
        if opts["json"]:
            print(json.dumps(matches[0], indent=2))
        elif opts["quiet"]:
            print(matches[0]["state"])
        else:
            s = matches[0]
            print(f"  {s['entity_id']}: {s['state']}")
            for k, v in s.get("attributes", {}).items():
                print(f"    {k}: {v}")
    else:
        print(f"Entity not found: {entity_id}", file=sys.stderr)


async def cmd_states(ws, args, opts):
    """List all states, optionally filtered by domain."""
    domain = args[0] if args else None
    result = await ws.send("get_states")
    if opts["json"]:
        if domain:
            result = [s for s in result if s["entity_id"].startswith(f"{domain}.")]
        print(json.dumps(result, indent=2))
    else:
        for s in result:
            if domain and not s["entity_id"].startswith(f"{domain}."):
                continue
            name = s.get("attributes", {}).get("friendly_name", "")
            print(f"  {s['entity_id']:50s} {s['state']:20s} {name}")


async def cmd_call(ws, args, opts):
    """Call a service: ha-ws call domain.service [key=value ...]"""
    if not args:
        print("Usage: ha-ws call <domain.service> [key=value ...] [entity_id]", file=sys.stderr)
        return
    service_str = args[0]
    if "." not in service_str:
        print("Service must be domain.service (e.g., light.turn_on)", file=sys.stderr)
        return
    domain, _, service = service_str.partition(".")

    service_data = {}
    remaining = args[1:]

    # Collect key=value pairs and bare entity IDs
    for arg in remaining:
        if "=" in arg:
            key, _, value = arg.partition("=")
            service_data[key] = parse_value(value)
        elif arg.startswith("{"):
            try:
                service_data.update(json.loads(arg))
            except json.JSONDecodeError:
                print(f"Invalid JSON: {arg}", file=sys.stderr)
                return
        else:
            # Treat as entity_id
            service_data["entity_id"] = arg

    result = await ws.send("call_service", domain=domain, service=service, service_data=service_data)
    if opts["json"]:
        print(json.dumps(result, indent=2))
    elif not opts["quiet"]:
        print(f"Called {domain}.{service}")


async def cmd_services(ws, args, opts):
    """List available services, optionally filtered by domain."""
    domain_filter = args[0] if args else None
    result = await ws.send("get_services")
    if opts["json"]:
        print(json.dumps(result, indent=2))
    else:
        for domain, services in sorted(result.items()):
            if domain_filter and domain != domain_filter:
                continue
            for svc_name, svc_info in sorted(services.items()):
                desc = svc_info.get("description", "")
                print(f"  {domain}.{svc_name:40s} {desc}")


async def cmd_search(ws, args, opts):
    """Search for entities related to a given entity."""
    entity_id = args[0] if args else None
    if not entity_id:
        print("Usage: ha-ws search <entity_id>", file=sys.stderr)
        return
    result = await ws.send("search/related", item_type="entity", item_id=entity_id)
    print(json.dumps(result, indent=2))


async def cmd_config(ws, args, opts):
    """Get Home Assistant configuration."""
    result = await ws.send("get_config")
    print(json.dumps(result, indent=2))


async def cmd_info(ws, args, opts):
    """Get Home Assistant core info."""
    result = await ws.send("get_config")
    if opts["json"]:
        print(json.dumps(result, indent=2))
    else:
        print(f"  Version:    {result.get('version', 'unknown')}")
        print(f"  Location:   {result.get('location_name', 'unknown')}")
        print(f"  Unit Sys:   {result.get('unit_system', {}).get('temperature', 'unknown')}")
        print(f"  Time Zone:  {result.get('time_zone', 'unknown')}")
        print(f"  Components: {len(result.get('components', []))}")


async def cmd_raw(ws, args, opts):
    """Send a raw WebSocket message: ha-ws raw <type> [json_params]"""
    if not args:
        print("Usage: ha-ws raw <type> [json_params]", file=sys.stderr)
        return
    msg_type = args[0]
    kwargs = {}
    if len(args) > 1:
        try:
            kwargs = json.loads(args[1])
        except json.JSONDecodeError:
            kwargs = parse_kv_args(args[1:])
    result = await ws.send(msg_type, **kwargs)
    print(json.dumps(result, indent=2))


async def cmd_label(ws, args, opts):
    """Label registry operations: list, create, update, delete, assign"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config/label_registry/list")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for l in result:
                color = l.get("color") or ""
                desc = l.get("description") or ""
                print(f"  {l.get('label_id', ''):30s} {l.get('name', ''):20s} {color:10s} {desc}")

    elif sub == "create":
        name = args[1] if len(args) > 1 else None
        if not name:
            print("Usage: ha-ws label create <name> [color=X icon=X description=X]", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/label_registry/create", name=name, **data)
        print(json.dumps(result, indent=2))

    elif sub == "update":
        label_id = args[1] if len(args) > 1 else None
        if not label_id or len(args) < 3:
            print("Usage: ha-ws label update <label_id> key=value ...", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/label_registry/update", label_id=label_id, **data)
        print(json.dumps(result, indent=2))

    elif sub == "delete":
        label_id = args[1] if len(args) > 1 else None
        if not label_id:
            print("Usage: ha-ws label delete <label_id>", file=sys.stderr)
            return
        result = await ws.send("config/label_registry/delete", label_id=label_id)
        print("Deleted:", label_id)

    elif sub == "assign":
        if len(args) < 3:
            print("Usage: ha-ws label assign <entity_id> <label_id> [label_id ...]", file=sys.stderr)
            return
        entity_id = args[1]
        new_labels = args[2:]
        # Read current labels, merge, then update
        entity = await ws.send("config/entity_registry/get", entity_id=entity_id)
        current = entity.get("labels") or []
        merged = list(set(current + new_labels))
        result = await ws.send("config/entity_registry/update", entity_id=entity_id, labels=merged)
        print(f"Labels for {entity_id}: {merged}")
    else:
        print(f"Unknown label subcommand: {sub}", file=sys.stderr)


async def cmd_floor(ws, args, opts):
    """Floor registry operations: list, create, update, delete"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config/floor_registry/list")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for f in result:
                level = f.get("level") or ""
                level_str = f"  level={level}" if level else ""
                print(f"  {f.get('floor_id', ''):30s} {f.get('name', '')}{level_str}")

    elif sub == "create":
        name = args[1] if len(args) > 1 else None
        if not name:
            print("Usage: ha-ws floor create <name> [level=X icon=X]", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/floor_registry/create", name=name, **data)
        print(json.dumps(result, indent=2))

    elif sub == "update":
        floor_id = args[1] if len(args) > 1 else None
        if not floor_id or len(args) < 3:
            print("Usage: ha-ws floor update <floor_id> key=value ...", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        result = await ws.send("config/floor_registry/update", floor_id=floor_id, **data)
        print(json.dumps(result, indent=2))

    elif sub == "delete":
        floor_id = args[1] if len(args) > 1 else None
        if not floor_id:
            print("Usage: ha-ws floor delete <floor_id>", file=sys.stderr)
            return
        result = await ws.send("config/floor_registry/delete", floor_id=floor_id)
        print("Deleted:", floor_id)
    else:
        print(f"Unknown floor subcommand: {sub}", file=sys.stderr)


async def cmd_entries(ws, args, opts):
    """Config entry (integration) operations: list, get, delete, disable, enable"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("config_entries/get")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        else:
            for e in result:
                state = e.get("state", "")
                print(f"  {e.get('entry_id', '')[:16]:16s} {e.get('domain', ''):25s} {e.get('title', ''):30s} state={state}")

    elif sub == "get":
        entry_id = args[1] if len(args) > 1 else None
        if not entry_id:
            print("Usage: ha-ws entries get <entry_id>", file=sys.stderr)
            return
        result = await ws.send("config_entries/get")
        matches = [e for e in result if e["entry_id"] == entry_id]
        if matches:
            print(json.dumps(matches[0], indent=2))
        else:
            print(f"Config entry not found: {entry_id}", file=sys.stderr)
    elif sub == "delete":
        entry_id = args[1] if len(args) > 1 else None
        if not entry_id:
            print("Usage: ha-ws entries delete <entry_id>", file=sys.stderr)
            return
        url, token = load_env()
        try:
            result = rest_request(url, token, "DELETE", f"config/config_entries/entry/{entry_id}")
            print(f"Deleted config entry: {entry_id}")
            if opts["json"] and result:
                print(json.dumps(result, indent=2))
        except RuntimeError as e:
            print(f"Failed to delete config entry: {e}", file=sys.stderr)

    elif sub == "disable":
        entry_id = args[1] if len(args) > 1 else None
        if not entry_id:
            print("Usage: ha-ws entries disable <entry_id>", file=sys.stderr)
            return
        result = await ws.send("config_entries/disable", entry_id=entry_id, disabled_by="user")
        print(f"Disabled config entry: {entry_id}")
        if opts["json"] and result:
            print(json.dumps(result, indent=2))

    elif sub == "enable":
        entry_id = args[1] if len(args) > 1 else None
        if not entry_id:
            print("Usage: ha-ws entries enable <entry_id>", file=sys.stderr)
            return
        result = await ws.send("config_entries/disable", entry_id=entry_id, disabled_by=None)
        print(f"Enabled config entry: {entry_id}")
        if opts["json"] and result:
            print(json.dumps(result, indent=2))

    else:
        print(f"Unknown entries subcommand: {sub}. Use: list|get|delete|disable|enable", file=sys.stderr)


async def cmd_group(ws, args, opts):
    """Group management: list, get, create, remove"""
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("get_states")
        groups = [s for s in result if s["entity_id"].startswith("group.")]
        if opts["json"]:
            print(json.dumps(groups, indent=2))
        else:
            for g in groups:
                attrs = g.get("attributes", {})
                members = attrs.get("entity_id", [])
                name = attrs.get("friendly_name", "")
                print(f"  {g['entity_id']:40s} {g['state']:10s} {name}")
                if members:
                    for m in members:
                        print(f"    - {m}")

    elif sub == "get":
        group_id = args[1] if len(args) > 1 else None
        if not group_id:
            print("Usage: ha-ws group get <group_entity_id>", file=sys.stderr)
            return
        if not group_id.startswith("group."):
            group_id = f"group.{group_id}"
        result = await ws.send("get_states")
        matches = [s for s in result if s["entity_id"] == group_id]
        if matches:
            if opts["json"]:
                print(json.dumps(matches[0], indent=2))
            else:
                g = matches[0]
                attrs = g.get("attributes", {})
                print(f"  {g['entity_id']}: {g['state']}")
                print(f"  Name: {attrs.get('friendly_name', '')}")
                members = attrs.get("entity_id", [])
                print(f"  Members ({len(members)}):")
                for m in members:
                    print(f"    - {m}")
        else:
            print(f"Group not found: {group_id}", file=sys.stderr)

    elif sub == "create":
        object_id = args[1] if len(args) > 1 else None
        if not object_id:
            print("Usage: ha-ws group create <object_id> name=\"Name\" entities=a,b,c", file=sys.stderr)
            return
        data = parse_kv_args(args[2:])
        service_data = {"object_id": object_id}
        if "name" in data:
            service_data["name"] = data["name"]
        if "entities" in data:
            entities = data["entities"]
            if isinstance(entities, str):
                entities = [e.strip() for e in entities.split(",")]
            service_data["entities"] = entities
        else:
            print("Error: entities= is required (comma-separated list)", file=sys.stderr)
            return
        await ws.send("call_service", domain="group", service="set", service_data=service_data)
        print(f"Group group.{object_id} created with {len(service_data['entities'])} members")

    elif sub == "remove":
        object_id = args[1] if len(args) > 1 else None
        if not object_id:
            print("Usage: ha-ws group remove <object_id>", file=sys.stderr)
            return
        if object_id.startswith("group."):
            object_id = object_id[6:]
        await ws.send("call_service", domain="group", service="remove", service_data={"object_id": object_id})
        print(f"Removed: group.{object_id}")
    else:
        print(f"Unknown group subcommand: {sub}", file=sys.stderr)


async def cmd_scene(ws, args, opts):
    """Scene management: list, get, create, delete, activate, snapshot, reload"""
    url, token = load_env()
    sub = args[0] if args else "list"

    if sub == "list":
        result = await ws.send("get_states")
        scenes = [s for s in result if s["entity_id"].startswith("scene.")]
        if opts["json"]:
            print(json.dumps(scenes, indent=2))
        else:
            for s in scenes:
                attrs = s.get("attributes", {})
                name = attrs.get("friendly_name", "")
                sid = attrs.get("id", "")
                print(f"  {s['entity_id']:40s} id={str(sid):20s} {name}")

    elif sub == "get":
        scene_id = args[1] if len(args) > 1 else None
        if not scene_id:
            print("Usage: ha-ws scene get <scene_id>  (use numeric id from 'scene list')", file=sys.stderr)
            return
        # Allow entity_id format — look up the numeric ID from state attributes
        if scene_id.startswith("scene."):
            all_states = await ws.send("get_states")
            match = [s for s in all_states if s["entity_id"] == scene_id]
            if match:
                scene_id = str(match[0].get("attributes", {}).get("id", scene_id))
            else:
                print(f"Scene not found: {scene_id}", file=sys.stderr)
                return
        result = rest_request(url, token, "GET", f"config/scene/config/{scene_id}")
        print(json.dumps(result, indent=2))

    elif sub == "create":
        scene_id = args[1] if len(args) > 1 else None
        json_file = args[2] if len(args) > 2 else None
        if not scene_id or not json_file:
            print("Usage: ha-ws scene create <scene_id> <json_file>", file=sys.stderr)
            return
        with open(json_file) as f:
            data = json.load(f)
        result = rest_request(url, token, "POST", f"config/scene/config/{scene_id}", data)
        print(f"Scene '{scene_id}' created")
        # Auto-reload scenes
        await ws.send("call_service", domain="scene", service="reload", service_data={})
        print("Scenes reloaded")

    elif sub == "delete":
        scene_id = args[1] if len(args) > 1 else None
        if not scene_id:
            print("Usage: ha-ws scene delete <scene_id>  (use numeric id or scene.entity_id)", file=sys.stderr)
            return
        if scene_id.startswith("scene."):
            all_states = await ws.send("get_states")
            match = [s for s in all_states if s["entity_id"] == scene_id]
            if match:
                scene_id = str(match[0].get("attributes", {}).get("id", scene_id))
            else:
                print(f"Scene not found: {scene_id}", file=sys.stderr)
                return
        rest_request(url, token, "DELETE", f"config/scene/config/{scene_id}")
        print(f"Scene '{scene_id}' deleted")
        await ws.send("call_service", domain="scene", service="reload", service_data={})
        print("Scenes reloaded")

    elif sub == "activate":
        entity_id = args[1] if len(args) > 1 else None
        if not entity_id:
            print("Usage: ha-ws scene activate <scene_entity_id>", file=sys.stderr)
            return
        if not entity_id.startswith("scene."):
            entity_id = f"scene.{entity_id}"
        await ws.send("call_service", domain="scene", service="turn_on", service_data={"entity_id": entity_id})
        print(f"Activated: {entity_id}")

    elif sub == "snapshot":
        entity_ids = args[1:]
        if not entity_ids:
            print("Usage: ha-ws scene snapshot <entity_id> [entity_id ...]", file=sys.stderr)
            return
        all_states = await ws.send("get_states")
        state_map = {s["entity_id"]: s for s in all_states}
        entities = {}
        for eid in entity_ids:
            if eid in state_map:
                s = state_map[eid]
                entity_state = {"state": s["state"]}
                # Include relevant attributes based on domain
                attrs = s.get("attributes", {})
                for key in ("brightness", "color_temp", "rgb_color", "xy_color", "hs_color",
                            "color_mode", "temperature", "target_temp_high", "target_temp_low",
                            "hvac_mode", "fan_mode", "swing_mode", "preset_mode",
                            "media_content_id", "media_content_type", "volume_level",
                            "source", "sound_mode"):
                    if key in attrs:
                        entity_state[key] = attrs[key]
                entities[eid] = entity_state
            else:
                print(f"  Warning: {eid} not found, skipping", file=sys.stderr)
        scene_config = {"entities": entities}
        print(json.dumps(scene_config, indent=2))

    elif sub == "reload":
        await ws.send("call_service", domain="scene", service="reload", service_data={})
        print("Scenes reloaded")
    else:
        print(f"Unknown scene subcommand: {sub}", file=sys.stderr)


async def cmd_audit(ws, args, opts):
    """Health audit: summary, unavailable, unknown, disabled, stale, orphaned, dead-devices"""
    sub = args[0] if args else "summary"

    # Fetch all data once
    all_states = await ws.send("get_states")
    entity_registry = await ws.send("config/entity_registry/list")
    device_registry = await ws.send("config/device_registry/list")
    config_entries = await ws.send("config_entries/get")

    state_map = {s["entity_id"]: s for s in all_states}
    device_ids = {d["id"] for d in device_registry}
    entry_ids = {e["entry_id"] for e in config_entries}

    # Build entity-to-device mapping
    device_entities = {}
    for e in entity_registry:
        did = e.get("device_id")
        if did:
            device_entities.setdefault(did, []).append(e["entity_id"])

    def get_unavailable():
        return [s for s in all_states if s["state"] == "unavailable"]

    def get_unknown():
        return [s for s in all_states if s["state"] == "unknown"]

    def get_disabled():
        return [e for e in entity_registry if e.get("disabled_by")]

    def get_stale(hours=72):
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        stale = []
        for s in all_states:
            last = s.get("last_updated")
            if last:
                try:
                    ts = datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp()
                    if ts < cutoff:
                        stale.append(s)
                except (ValueError, TypeError):
                    pass
        return stale

    def get_orphaned():
        orphaned = []
        for e in entity_registry:
            did = e.get("device_id")
            ceid = e.get("config_entry_id")
            if did and did not in device_ids:
                orphaned.append({"entity_id": e["entity_id"], "reason": f"device {did[:12]}... not found"})
            elif ceid and ceid not in entry_ids:
                orphaned.append({"entity_id": e["entity_id"], "reason": f"config entry {ceid[:12]}... not found"})
        return orphaned

    def get_dead_devices():
        dead = []
        for d in device_registry:
            entities = device_entities.get(d["id"], [])
            if not entities:
                continue
            all_bad = all(
                state_map.get(eid, {}).get("state") in ("unavailable", "unknown")
                for eid in entities
            )
            if all_bad:
                dead.append({
                    "device_id": d["id"],
                    "name": d.get("name_by_user") or d.get("name") or "(unnamed)",
                    "entity_count": len(entities),
                    "entities": entities,
                })
        return dead

    def print_entity_list(items, state_key=True):
        for s in items:
            eid = s.get("entity_id", "")
            name = s.get("attributes", {}).get("friendly_name", "") if state_key else ""
            state = s.get("state", "") if state_key else ""
            last = s.get("last_updated", "")[:19] if state_key else ""
            if state_key:
                print(f"  {eid:50s} {state:15s} {last} {name}")
            else:
                # For entity registry items (disabled)
                disabled_by = s.get("disabled_by", "")
                n = s.get("name") or s.get("original_name") or ""
                print(f"  {s.get('entity_id', ''):50s} disabled_by={disabled_by:12s} {n}")

    if sub == "summary":
        unavail = get_unavailable()
        unknown = get_unknown()
        disabled = get_disabled()
        stale_hours = int(args[1]) if len(args) > 1 else 72
        stale = get_stale(stale_hours)
        orphaned = get_orphaned()
        dead = get_dead_devices()

        if opts["json"]:
            print(json.dumps({
                "unavailable": len(unavail),
                "unknown": len(unknown),
                "disabled": len(disabled),
                f"stale_{stale_hours}h": len(stale),
                "orphaned": len(orphaned),
                "dead_devices": len(dead),
                "total_entities": len(all_states),
                "total_devices": len(device_registry),
            }, indent=2))
        else:
            print("Health Audit Summary")
            print(f"  Total entities:          {len(all_states):>5}")
            print(f"  Total devices:           {len(device_registry):>5}")
            print(f"  Unavailable entities:    {len(unavail):>5}")
            print(f"  Unknown entities:        {len(unknown):>5}")
            print(f"  Disabled entities:       {len(disabled):>5}")
            print(f"  Stale entities ({stale_hours}h+):  {len(stale):>5}")
            print(f"  Orphaned entities:       {len(orphaned):>5}")
            print(f"  Dead devices:            {len(dead):>5}")
            print()
            print("  Run 'ha-ws audit <category>' for details.")

    elif sub == "unavailable":
        items = get_unavailable()
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Unavailable entities ({len(items)}):")
            print_entity_list(items)

    elif sub == "unknown":
        items = get_unknown()
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Unknown entities ({len(items)}):")
            print_entity_list(items)

    elif sub == "disabled":
        items = get_disabled()
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Disabled entities ({len(items)}):")
            print_entity_list(items, state_key=False)

    elif sub == "stale":
        hours = int(args[1]) if len(args) > 1 else 72
        items = get_stale(hours)
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Stale entities (no update in {hours}h+) ({len(items)}):")
            print_entity_list(items)

    elif sub == "orphaned":
        items = get_orphaned()
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Orphaned entities ({len(items)}):")
            for o in items:
                print(f"  {o['entity_id']:50s} {o['reason']}")

    elif sub == "dead-devices":
        items = get_dead_devices()
        if opts["json"]:
            print(json.dumps(items, indent=2))
        else:
            print(f"Dead devices ({len(items)}):")
            for d in items:
                print(f"  {d['device_id'][:16]}  {d['name']:40s} ({d['entity_count']} entities)")
                for eid in d["entities"]:
                    state = state_map.get(eid, {}).get("state", "?")
                    print(f"    - {eid} ({state})")
    else:
        print(f"Unknown audit subcommand: {sub}", file=sys.stderr)


COMMANDS = {
    "entity": cmd_entity,
    "device": cmd_device,
    "area": cmd_area,
    "state": cmd_state,
    "states": cmd_states,
    "call": cmd_call,
    "services": cmd_services,
    "search": cmd_search,
    "config": cmd_config,
    "info": cmd_info,
    "raw": cmd_raw,
    "label": cmd_label,
    "floor": cmd_floor,
    "entries": cmd_entries,
    "group": cmd_group,
    "scene": cmd_scene,
    "audit": cmd_audit,
}


def usage():
    print("""ha-ws — Home Assistant WebSocket API CLI

Usage: ha-ws <command> [args...] [--json] [--quiet]

Commands:
  entity list|get|update|remove    Entity registry operations
  device list|get|update           Device registry operations
  area list|create|update|delete   Area registry operations
  label list|create|update|delete|assign  Label registry operations
  floor list|create|update|delete  Floor registry operations
  group list|get|create|remove     Group management
  scene list|get|create|delete|activate|snapshot|reload  Scene management
  entries list|get|delete|disable|enable  Config entries (integrations)
  audit summary|unavailable|unknown|disabled|stale|orphaned|dead-devices
  state <entity_id>                Get entity state and attributes
  states [domain]                  List all states (optional domain filter)
  call <domain.service> [args...]  Call a service (key=value or entity_id)
  services [domain]                List available services
  search <entity_id>               Find related entities
  config                           Get HA configuration
  info                             Get HA core info summary
  raw <type> [json]                Send raw WebSocket message

Options:
  --json    Output raw JSON
  --quiet   Minimal output (state values only)""")
    sys.exit(1)


async def main():
    url, token = load_env()

    # Parse global options
    args = sys.argv[1:]
    opts = {"json": False, "quiet": False}
    filtered_args = []
    for a in args:
        if a == "--json":
            opts["json"] = True
        elif a == "--quiet":
            opts["quiet"] = True
        else:
            filtered_args.append(a)

    if not filtered_args:
        usage()

    command = filtered_args[0]
    cmd_args = filtered_args[1:]

    if command not in COMMANDS:
        print(f"Unknown command: {command}", file=sys.stderr)
        usage()

    ws = HAWebSocket(url, token)
    try:
        await ws.connect()
        await COMMANDS[command](ws, cmd_args, opts)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await ws.close()


if __name__ == "__main__":
    asyncio.run(main())

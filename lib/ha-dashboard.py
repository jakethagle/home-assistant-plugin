"""ha-dashboard — Home Assistant Dashboard Management CLI (remote, via WebSocket)

Usage: ha-dashboard <command> [args...]
"""

import asyncio
import json
import os
import sys

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


class HAWebSocket:
    def __init__(self, url, token):
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/api/websocket"
        self.token = token
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        msg = json.loads(await self.ws.recv())
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected message: {msg}")
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


async def cmd_list(ws):
    """List all dashboards."""
    result = await ws.send("lovelace/dashboards/list")
    print(f"  {'ID':30s} {'Title':30s} Mode")
    print(f"  {'--':30s} {'-----':30s} ----")
    # Default dashboard
    print(f"  {'lovelace (default)':30s} {'':30s} ")
    for d in result:
        title = d.get("title", "")
        mode = d.get("mode", "")
        url_path = d.get("url_path", d.get("id", ""))
        print(f"  {url_path:30s} {title:30s} {mode}")


async def cmd_get(ws, args):
    """Get dashboard config. Usage: ha-dashboard get [dashboard_url_path]"""
    url_path = args[0] if args else None
    if url_path:
        result = await ws.send("lovelace/config", url_path=url_path)
    else:
        result = await ws.send("lovelace/config")
    print(json.dumps(result, indent=2))


async def cmd_save(ws, args):
    """Save dashboard config from a JSON file. Usage: ha-dashboard save <json_file> [dashboard_url_path]"""
    if not args:
        print("Usage: ha-dashboard save <json_file> [dashboard_url_path]", file=sys.stderr)
        return

    json_file = args[0]
    url_path = args[1] if len(args) > 1 else None

    with open(json_file) as f:
        config = json.load(f)

    kwargs = {"config": config}
    if url_path:
        kwargs["url_path"] = url_path

    await ws.send("lovelace/config/save", **kwargs)

    views = config.get("views", [])
    print(f"Dashboard saved: {len(views)} view(s)")
    for v in views:
        title = v.get("title", "(untitled)")
        path = v.get("path", "")
        cards = len(v.get("cards", []))
        print(f"  - {title} (path={path}, {cards} cards)")


async def cmd_export(ws, args):
    """Export dashboard config to a JSON file. Usage: ha-dashboard export <output_file> [dashboard_url_path]"""
    if not args:
        print("Usage: ha-dashboard export <output_file> [dashboard_url_path]", file=sys.stderr)
        return

    output_file = args[0]
    url_path = args[1] if len(args) > 1 else None

    if url_path:
        result = await ws.send("lovelace/config", url_path=url_path)
    else:
        result = await ws.send("lovelace/config")

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Exported to {output_file}")


def usage():
    print("""ha-dashboard — Home Assistant Dashboard Management CLI

Usage: ha-dashboard <command> [args...]

Commands:
  list                              List all dashboards
  get [dashboard_url_path]          Get dashboard config as JSON (default: main dashboard)
  save <json_file> [url_path]       Push dashboard config from JSON file
  export <output_file> [url_path]   Export dashboard config to JSON file""")
    sys.exit(1)


async def main():
    url, token = load_env()

    args = sys.argv[1:]
    if not args:
        usage()

    command = args[0]
    cmd_args = args[1:]

    ws = HAWebSocket(url, token)
    try:
        await ws.connect()
        if command == "list":
            await cmd_list(ws)
        elif command == "get":
            await cmd_get(ws, cmd_args)
        elif command == "save":
            await cmd_save(ws, cmd_args)
        elif command == "export":
            await cmd_export(ws, cmd_args)
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            usage()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await ws.close()


if __name__ == "__main__":
    asyncio.run(main())

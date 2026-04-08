"""ha-ssh — Home Assistant SSH Access CLI

Provides direct access to HA config files, .storage, logs, and Supervisor API
via SSH to the HA SSH addon.

Usage: ha-ssh <command> [args...] [--json] [--quiet]
"""

import json
import os
import shlex
import subprocess
import sys
from urllib.parse import urlparse


def load_env():
    """Load Home Assistant and SSH credentials from config file."""
    config_file = os.path.join(os.path.expanduser("~"), ".config", "ha-claude", "config")
    vals = {}
    if os.path.isfile(config_file):
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    vals[key] = value

    ssh_host = vals.get("HA_SSH_HOST", "")
    ssh_port = vals.get("HA_SSH_PORT", "22")
    ssh_user = vals.get("HA_SSH_USER", "root")
    ssh_key = vals.get("HA_SSH_KEY", "")
    ha_url = vals.get("HA_URL", "")

    # If no SSH host configured, try to derive from HA_URL
    if not ssh_host and ha_url:
        try:
            ssh_host = urlparse(ha_url).hostname or ""
        except Exception:
            pass

    if not ssh_host:
        print("Error: SSH not configured. Run: ha-setup --ssh", file=sys.stderr)
        sys.exit(1)

    return {
        "host": ssh_host,
        "port": ssh_port,
        "user": ssh_user,
        "key": ssh_key,
    }


class HASSHClient:
    """Execute commands on the Home Assistant server via SSH."""

    def __init__(self, host, port, user, key_path=None):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path

    def _ssh_args(self):
        args = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-p", str(self.port),
        ]
        if self.key_path:
            expanded = os.path.expanduser(self.key_path)
            if os.path.isfile(expanded):
                args.extend(["-i", expanded])
        args.append(f"{self.user}@{self.host}")
        return args

    def exec(self, command, timeout=30):
        """Execute a command over SSH and return stdout."""
        args = self._ssh_args() + [command]
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"SSH command timed out after {timeout}s. "
                f"Check network connectivity to {self.host}."
            )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Permission denied" in stderr or "authentication" in stderr.lower():
                raise RuntimeError(
                    f"SSH authentication failed. Run: ha-setup --ssh\n{stderr}"
                )
            if "Connection refused" in stderr:
                raise RuntimeError(
                    f"SSH connection refused on port {self.port}. "
                    f"Is the SSH addon running? Check HA Settings > Add-ons.\n{stderr}"
                )
            if "Could not resolve" in stderr or "No route to host" in stderr:
                raise RuntimeError(
                    f"Cannot reach {self.host}. Check network connectivity.\n{stderr}"
                )
            raise RuntimeError(f"SSH command failed: {stderr}")
        return result.stdout

    def read_file(self, path):
        """Read a file from the remote system."""
        return self.exec(f"cat {shlex.quote(path)}")

    def list_dir(self, path):
        """List a directory on the remote system."""
        return self.exec(f"ls -la {shlex.quote(path)}")

    def supervisor_api(self, method, endpoint, data=None):
        """Call the HA Supervisor API from within the SSH container."""
        cmd = f'curl -sf -X {method} -H "Authorization: Bearer $SUPERVISOR_TOKEN" '
        cmd += '-H "Content-Type: application/json" '
        if data:
            cmd += f"-d {shlex.quote(json.dumps(data))} "
        cmd += f'"http://supervisor/{endpoint}"'
        output = self.exec(cmd, timeout=30)
        if not output.strip():
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # Some endpoints return plain text (like logs)
            return output


# --- Commands ---


def cmd_test(ssh, args, opts):
    """Test SSH connectivity."""
    try:
        output = ssh.exec("echo 'SSH connection successful'")
        print(output.strip())
        # Also try reading HA version
        try:
            content = ssh.read_file("/config/.storage/core.config")
            data = json.loads(content)
            version = data.get("data", {}).get("version")
            if version:
                print(f"Home Assistant version: {version}")
        except Exception:
            pass
        # Test Supervisor API access
        try:
            result = ssh.supervisor_api("GET", "core/info")
            if result and "data" in result:
                version = result["data"].get("version", "unknown")
                print(f"Supervisor API accessible (HA Core: {version})")
        except Exception as e:
            print(f"Supervisor API: not available ({e})", file=sys.stderr)
    except RuntimeError as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_storage(ssh, args, opts):
    """Read .storage/ files: list, read, entries, entry-options."""
    sub = args[0] if args else "list"

    if sub == "list":
        output = ssh.exec("ls -1 /config/.storage/ | sort")
        if opts["json"]:
            files = [f for f in output.strip().split("\n") if f]
            print(json.dumps(files, indent=2))
        else:
            print(output)

    elif sub == "read":
        if len(args) < 2:
            print("Usage: ha-ssh storage read <key>", file=sys.stderr)
            print("Example: ha-ssh storage read core.config_entries", file=sys.stderr)
            return
        key = args[1]
        content = ssh.read_file(f"/config/.storage/{key}")
        data = json.loads(content)
        if opts["json"]:
            print(json.dumps(data, indent=2))
        else:
            print(f"Key:     {data.get('key', '?')}")
            print(f"Version: {data.get('version', '?')}.{data.get('minor_version', 0)}")
            top_keys = list(data.get("data", {}).keys())
            print(f"Data:    {top_keys}")
            print()
            print(json.dumps(data["data"], indent=2))

    elif sub == "entries":
        domain_filter = args[1] if len(args) > 1 else None
        content = ssh.read_file("/config/.storage/core.config_entries")
        data = json.loads(content)
        entries = data.get("data", {}).get("entries", [])
        if domain_filter:
            entries = [e for e in entries if e.get("domain") == domain_filter]
        if opts["json"]:
            print(json.dumps(entries, indent=2))
        else:
            for e in entries:
                disabled = " [DISABLED]" if e.get("disabled_by") else ""
                print(f"\n{'='*60}")
                print(f"  Entry ID: {e.get('entry_id')}")
                print(f"  Domain:   {e.get('domain')}")
                print(f"  Title:    {e.get('title')}{disabled}")
                print(f"  Source:   {e.get('source')}")
                opts_data = e.get("options", {})
                if opts_data:
                    print(f"  Options:  {json.dumps(opts_data, indent=4)}")
                entry_data = e.get("data", {})
                if entry_data:
                    # Mask potential secrets in data
                    display_data = _mask_secrets(entry_data)
                    print(f"  Data:     {json.dumps(display_data, indent=4)}")

    elif sub == "entry-options":
        if len(args) < 2:
            print("Usage: ha-ssh storage entry-options <entry_id>", file=sys.stderr)
            return
        entry_id = args[1]
        content = ssh.read_file("/config/.storage/core.config_entries")
        data = json.loads(content)
        entries = data.get("data", {}).get("entries", [])
        match = [e for e in entries if e.get("entry_id") == entry_id]
        if not match:
            # Try partial match
            match = [e for e in entries if entry_id in e.get("entry_id", "")]
        if not match:
            print(f"Entry not found: {entry_id}", file=sys.stderr)
            print("Use 'ha-ssh storage entries' or 'ha-ws entries list' to find entry IDs.", file=sys.stderr)
            return
        for entry in match:
            if opts["json"]:
                print(json.dumps(entry, indent=2))
            else:
                print(f"Entry ID: {entry.get('entry_id')}")
                print(f"Domain:   {entry.get('domain')}")
                print(f"Title:    {entry.get('title')}")
                print(f"Source:   {entry.get('source')}")
                print(f"State:    {entry.get('state')}")
                print()
                opts_data = entry.get("options", {})
                print(f"Options:")
                print(json.dumps(opts_data, indent=2))
                print()
                entry_data = entry.get("data", {})
                print(f"Data:")
                print(json.dumps(_mask_secrets(entry_data), indent=2))
    else:
        print(f"Unknown storage subcommand: {sub}", file=sys.stderr)
        print("Usage: ha-ssh storage list|read|entries|entry-options", file=sys.stderr)


def cmd_config(ssh, args, opts):
    """Read/manage HA config files."""
    sub = args[0] if args else "list"

    if sub == "list":
        output = ssh.exec("ls -la /config/")
        print(output)

    elif sub == "read":
        filename = args[1] if len(args) > 1 else "configuration.yaml"
        # Prevent path traversal
        if ".." in filename or filename.startswith("/"):
            print("Error: Invalid filename", file=sys.stderr)
            return
        content = ssh.read_file(f"/config/{filename}")
        print(content)

    elif sub == "validate":
        result = ssh.supervisor_api("POST", "core/check")
        if result and "data" in result:
            valid = result["data"].get("result") == "valid"
            if valid:
                print("Configuration is valid.")
            else:
                errors = result["data"].get("errors")
                print(f"Configuration invalid: {errors}")
        elif result:
            print(json.dumps(result, indent=2))

    else:
        print(f"Unknown config subcommand: {sub}", file=sys.stderr)
        print("Usage: ha-ssh config list|read|validate", file=sys.stderr)


def cmd_logs(ssh, args, opts):
    """Access HA logs via Supervisor API."""
    sub = args[0] if args else "core"
    lines = int(args[1]) if len(args) > 1 else 100

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
        endpoint = endpoint_map[sub]
    else:
        print(f"Unknown log source: {sub}", file=sys.stderr)
        print("Usage: ha-ssh logs core|supervisor|host|addon <slug> [lines]", file=sys.stderr)
        return

    # Supervisor log endpoints return plain text, not JSON
    cmd = (
        f'curl -sf -H "Authorization: Bearer $SUPERVISOR_TOKEN" '
        f'"http://supervisor/{endpoint}" | tail -n {lines}'
    )
    try:
        output = ssh.exec(cmd, timeout=30)
        print(output)
    except RuntimeError as e:
        print(f"Error fetching logs: {e}", file=sys.stderr)


def cmd_supervisor(ssh, args, opts):
    """Interact with the Supervisor API."""
    sub = args[0] if args else "info"

    if sub == "info":
        result = ssh.supervisor_api("GET", "core/info")
        if opts["json"]:
            print(json.dumps(result, indent=2))
        elif result and "data" in result:
            d = result["data"]
            print(f"  Version:     {d.get('version', '?')}")
            print(f"  Machine:     {d.get('machine', '?')}")
            print(f"  Arch:        {d.get('arch', '?')}")
            print(f"  Image:       {d.get('image', '?')}")
            print(f"  Boot:        {d.get('boot', '?')}")
            print(f"  Last Boot:   {d.get('last_boot', '?')}")
            # Also get supervisor info
            sup = ssh.supervisor_api("GET", "supervisor/info")
            if sup and "data" in sup:
                sd = sup["data"]
                print(f"  Supervisor:  {sd.get('version', '?')}")
                print(f"  Channel:     {sd.get('channel', '?')}")
                print(f"  Addons:      {len(sd.get('addons', []))}")

    elif sub == "addons":
        result = ssh.supervisor_api("GET", "addons")
        if result and "data" in result:
            addons = result["data"].get("addons", [])
            if opts["json"]:
                print(json.dumps(addons, indent=2))
            else:
                for a in addons:
                    state = a.get("state", "?")
                    slug = a.get("slug", "?")
                    name = a.get("name", "?")
                    version = a.get("version", "?")
                    print(f"  {slug:40s} {state:12s} v{version:15s} {name}")

    elif sub == "addon-info":
        if len(args) < 2:
            print("Usage: ha-ssh supervisor addon-info <slug>", file=sys.stderr)
            return
        slug = args[1]
        result = ssh.supervisor_api("GET", f"addons/{slug}/info")
        if result and "data" in result:
            print(json.dumps(result["data"], indent=2))

    elif sub == "restart":
        if "--confirm" not in sys.argv:
            print("This will restart Home Assistant Core.", file=sys.stderr)
            print("Re-run with --confirm to proceed.", file=sys.stderr)
            return
        result = ssh.supervisor_api("POST", "core/restart")
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Restart initiated.")

    elif sub == "addon-restart":
        if len(args) < 2:
            print("Usage: ha-ssh supervisor addon-restart <slug>", file=sys.stderr)
            return
        slug = args[1]
        if "--confirm" not in sys.argv:
            print(f"This will restart addon: {slug}", file=sys.stderr)
            print("Re-run with --confirm to proceed.", file=sys.stderr)
            return
        result = ssh.supervisor_api("POST", f"addons/{slug}/restart")
        if result:
            print(json.dumps(result, indent=2))
        else:
            print(f"Restart initiated for {slug}.")

    elif sub == "reload":
        result = ssh.supervisor_api("POST", "core/options", {"refresh_updates": True})
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Reload initiated.")

    else:
        print(f"Unknown supervisor subcommand: {sub}", file=sys.stderr)
        print("Usage: ha-ssh supervisor info|addons|addon-info|restart|reload|addon-restart", file=sys.stderr)


def cmd_exec(ssh, args, opts):
    """Execute an arbitrary SSH command."""
    if not args:
        print("Usage: ha-ssh exec <command>", file=sys.stderr)
        return
    command = " ".join(args)
    output = ssh.exec(command, timeout=60)
    print(output)


# --- Helpers ---


def _mask_secrets(data):
    """Mask values that look like secrets in config entry data."""
    if not isinstance(data, dict):
        return data
    sensitive_keys = {
        "token", "password", "secret", "api_key", "access_token",
        "refresh_token", "client_secret", "private_key",
    }
    masked = {}
    for k, v in data.items():
        if isinstance(v, dict):
            masked[k] = _mask_secrets(v)
        elif any(s in k.lower() for s in sensitive_keys) and isinstance(v, str) and len(v) > 4:
            masked[k] = f"****{v[-4:]}"
        else:
            masked[k] = v
    return masked


def usage():
    print("""ha-ssh — Home Assistant SSH Access CLI

Usage: ha-ssh <command> [args...] [--json] [--quiet]

Commands:
  test                                    Test SSH connectivity
  storage list                            List .storage/ files
  storage read <key>                      Read a .storage/ file
  storage entries [domain]                List config entries with full options/data
  storage entry-options <entry_id>        Get full options/data for a config entry
  config list                             List files in /config/
  config read [filename]                  Read a config file (default: configuration.yaml)
  config validate                         Validate HA configuration
  logs core [lines]                       HA Core logs (default: 100)
  logs supervisor [lines]                 Supervisor logs
  logs addon <slug> [lines]               Addon logs
  logs host [lines]                       Host system logs
  supervisor info                         System info
  supervisor addons                       List installed addons
  supervisor addon-info <slug>            Addon details
  supervisor restart [--confirm]          Restart HA Core
  supervisor addon-restart <slug> [--confirm]  Restart an addon
  supervisor reload                       Reload HA Core config
  exec <command>                          Run arbitrary SSH command

Options:
  --json    Output raw JSON
  --quiet   Minimal output""")
    sys.exit(1)


COMMANDS = {
    "test": cmd_test,
    "storage": cmd_storage,
    "config": cmd_config,
    "logs": cmd_logs,
    "supervisor": cmd_supervisor,
    "exec": cmd_exec,
}


def main():
    args = sys.argv[1:]
    opts = {"json": False, "quiet": False}
    filtered_args = []
    for arg in args:
        if arg == "--json":
            opts["json"] = True
        elif arg == "--quiet":
            opts["quiet"] = True
        elif arg == "--confirm":
            pass  # Handled directly in commands that need it
        else:
            filtered_args.append(arg)

    if not filtered_args:
        usage()

    command = filtered_args[0]
    cmd_args = filtered_args[1:]

    if command not in COMMANDS:
        print(f"Unknown command: {command}", file=sys.stderr)
        usage()

    env = load_env()
    ssh = HASSHClient(env["host"], env["port"], env["user"], env["key"])

    try:
        COMMANDS[command](ssh, cmd_args, opts)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

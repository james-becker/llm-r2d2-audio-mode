#!/usr/bin/env python3
"""Add or remove R2D2 mode hooks in Cursor's and Codex's user-level hook files.

  hooks_config.py install HOOK_SCRIPT [cursor] [codex]
  hooks_config.py uninstall [cursor] [codex]

Existing hooks are kept. A file is backed up to <file>.r2d2-backup before its first change.

Copyright (c) 2026 James Becker. MIT License; see LICENSE.
"""
import json, os, shutil, sys

MARK = "/.r2d2/r2-hook.sh"
HOME = os.path.expanduser("~")

TARGETS = {
    # file, top-level extras, {event: (action, extra handler fields)}, nested matcher groups?
    "cursor": (os.path.join(HOME, ".cursor", "hooks.json"), {"version": 1}, {
        "beforeSubmitPrompt": ("start", {}),
        "stop": ("stop", {}),
        "sessionEnd": ("kill", {}),
    }, False),
    "codex": (os.path.join(HOME, ".codex", "hooks.json"), {}, {
        "UserPromptSubmit": ("start", {}),
        "Stop": ("stop", {}),
        "Interrupt": ("stopped", {"async": True}),
        "PermissionRequest": ("alert", {"async": True}),
        "SessionEnd": ("kill", {}),
    }, True),
}


def ours(entry):
    """True if a hook entry (Cursor handler or Codex matcher group) runs R2."""
    handlers = entry.get("hooks", [entry]) if isinstance(entry, dict) else []
    return any(MARK in str(h.get("command", "")) for h in handlers if isinstance(h, dict))


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def foreign(data):
    """True if the file holds hooks R2 didn't write (only those are worth backing up)."""
    return any(not ours(e) for entries in data.get("hooks", {}).values() for e in entries)


def save(path, data, backup):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if backup and os.path.exists(path) and not os.path.exists(path + ".r2d2-backup"):
        shutil.copy2(path, path + ".r2d2-backup")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def strip(data):
    hooks = data.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [e for e in hooks[event] if not ours(e)]
        if not hooks[event]:
            del hooks[event]


def install(script, agent):
    path, extras, events, nested = TARGETS[agent]
    data = load(path)
    backup = foreign(data)
    for k, v in extras.items():
        data.setdefault(k, v)
    strip(data)  # idempotent: replace any previous R2 entries
    hooks = data.setdefault("hooks", {})
    for event, (action, extra) in events.items():
        cmd = f'"{script}" {action} {agent}'
        handler = {"type": "command", "command": cmd, **extra} if nested else {"command": cmd, **extra}
        hooks.setdefault(event, []).append({"hooks": [handler]} if nested else handler)
    save(path, data, backup)
    print(f"  {agent}: added R2 hooks to {path}")


def uninstall(agent):
    path = TARGETS[agent][0]
    if not os.path.exists(path):
        return
    data = load(path)
    strip(data)
    save(path, data, False)
    print(f"  {agent}: removed R2 hooks from {path}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "install":
        script, agents = args[0], args[1:]
        for a in agents:
            install(script, a)
    elif cmd == "uninstall":
        for a in args or TARGETS:
            uninstall(a)
    else:
        sys.exit(__doc__)

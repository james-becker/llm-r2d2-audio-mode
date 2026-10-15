# R2D2 mode 🤖

Sound effects for your coding agent. Works with **Claude Code**, **Cursor** and **Codex**.

- **You send a message:** R2 says "bee-dee-WOOP?"
- **While the agent works:** a quiet sparkle of tiny high blips
- **Response finished:** 2 seconds of R2 chatter (different every time), ending on the same "doo-dwee-DWEEE-dip!"
- **You hit Stop:** "dit-dit-bwoooow"
- **Permission needed** (Claude Code, Codex): an alert warble
- **Agent error** (Cursor): a sad droop

## Install

### Claude Code

```
/plugin marketplace add <path to this folder, or this repo's git URL>
/plugin install r2d2@r2d2-mode
```

Then start a new session.

### Cursor and Codex

```bash
./install.sh            # sets up whichever of Cursor / Codex you have
./install.sh cursor     # or pick one
```

This copies R2 to `~/.r2d2/` and adds hooks to `~/.cursor/hooks.json` and/or `~/.codex/hooks.json`.
Hooks you already have are kept, and a file is backed up to `<file>.r2d2-backup` before its first change.

**Codex:** hooks must be trusted before they run. Start `codex`, type `/hooks`, and trust the `r2-hook.sh` entries.

## Tweak

- `R2_VOLUME`: thinking sparkle volume (default `0.15`)
- `R2_TALK_VOLUME`: volume of the hello, finished, stop and alert sounds (default `0.8`)
- `R2_MUTE=1`: silence it
- `R2_DEBUG_LOG=/tmp/r2.log`: log every hook payload and what R2 played (for troubleshooting). Payloads
  can include your prompts and file paths, so delete the log when you're done.

Set these in your shell profile, or for Claude Code under `env` in `~/.claude/settings.json`.

## Uninstall

- Claude Code: `/plugin uninstall r2d2@r2d2-mode`
- Cursor and Codex: `./uninstall.sh`

## Requirements

`python3` (standard library only) and macOS (`afplay`). Linux works with `paplay` or `aplay`.

## Notes

- In Claude Code the Stop button fires no hook, so R2 spots it in the session transcript instead.
- Codex runs hidden background sessions (memory updates, for example) that also fire hooks. R2 ignores any
  Codex event without a session transcript, so those stay silent.
- Every sound is synthesized on the fly in pure Python. No audio files are bundled or downloaded.

## Privacy

R2D2 mode collects nothing and makes no network connections. Everything runs locally:

- It reads the hook payload your agent passes it, and watches the session transcript only to notice when you hit Stop.
- It writes short-lived state files and temporary `.wav` files to your temp directory, then deletes them.
- It writes nothing else, unless you turn on `R2_DEBUG_LOG`.

## License

[MIT](LICENSE) © 2026 James Becker

R2-D2 and Star Wars are trademarks of Lucasfilm Ltd. This is an unofficial fan project, not affiliated with or
endorsed by Lucasfilm or Disney.

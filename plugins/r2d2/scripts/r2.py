#!/usr/bin/env python3
"""R2D2-style chirp synthesizer.

  r2.py hello|done|stopped|alert|sad [--vol V] [--out file.wav]   fixed signature phrases (identical every time)
  r2.py finished [--vol V] [--out file.wav]   2s response-finished notification (fresh chatter + done)
  r2.py babble --state PREFIX [--transcript FILE] [--vol V] [--talk-vol V] [--hello-vol V]
        says hello, sparkles while Claude works, then plays the finished notification
        when PREFIX.finish appears (or stopped/sad/alert on their flag files)

Copyright (c) 2026 James Becker. MIT License; see LICENSE.
"""
import array, math, os, random, shutil, signal, subprocess, sys, tempfile, time, wave

RATE = 22050
TABLE_N = 2048
DRIVES = (1.0, 2.0, 3.5, 6.0)  # timbre: pure whistle -> buzzy droid


def _table(drive):
    norm = math.tanh(drive)
    return [math.tanh(drive * math.sin(2 * math.pi * i / TABLE_N)) / norm for i in range(TABLE_N)]


TABLES = [_table(d) for d in DRIVES]


# ---------------------------------------------------------------- primitives

def tone(freq, dur, vol=0.5, timbre=1, attack=0.003, release=0.010):
    """One syllable. freq is Hz, or callable(t_seconds, frac_0_to_1) -> Hz."""
    n = max(1, int(RATE * dur))
    tab = TABLES[timbre]
    fn = freq if callable(freq) else (lambda t, x: freq)
    att, rel = max(1, int(RATE * attack)), max(1, int(RATE * release))
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        phase = (phase + fn(i / RATE, i / n) / RATE) % 1.0
        env = min(1.0, i / att, (n - i) / rel)
        out[i] = tab[int(phase * TABLE_N)] * vol * env
    return out


def silence(dur):
    return [0.0] * int(RATE * dur)


# ---------------------------------------------------------------- fixed signatures

def hello():  # "bee-dee-WOOP?"
    return (tone(lambda t, x: 1400 + 900 * x ** 0.7, 0.07, 0.5, 2) + silence(0.03)
            + tone(lambda t, x: 2300 - 500 * x, 0.06, 0.5, 2) + silence(0.03)
            + tone(lambda t, x: 1500 + 1700 * x ** 2, 0.16, 0.5, 1))


def done():  # "doo-dwee-dee-DWEEE-dip!"
    return (tone(lambda t, x: 1200 + 1200 * x ** 1.5, 0.07, 0.5, 2) + silence(0.03)
            + tone(lambda t, x: 1800 + 200 * math.sin(2 * math.pi * 30 * t), 0.06, 0.5, 2) + silence(0.03)
            + tone(lambda t, x: 1600 + 1400 * x ** 1.5, 0.10, 0.5, 1) + silence(0.04)
            + tone(lambda t, x: 3000 - 200 * x, 0.05, 0.45, 0))


def stopped():  # "dit-dit-bwoooow", powering down
    return (tone(2000, 0.04, 0.5, 2) + silence(0.03) + tone(2000, 0.04, 0.5, 2) + silence(0.05)
            + tone(lambda t, x: 1600 * (1 - 0.75 * x) + 40 * math.sin(2 * math.pi * (18 - 12 * x) * t), 0.5, 0.5, 1))


def alert():  # agitated warble, then a falling whine
    s = []
    for _ in range(3):
        s += tone(lambda t, x: 2200 + 400 * x + 300 * math.sin(2 * math.pi * 40 * t), 0.06, 0.5, 3) + silence(0.05)
    return s + tone(lambda t, x: 2800 - 1400 * x + 150 * math.sin(2 * math.pi * 30 * t), 0.15, 0.5, 2)


def sad():
    return tone(lambda t, x: 1800 - 1200 * x + 60 * math.sin(2 * math.pi * 8 * t), 0.45, 0.5, 1)


FIXED = {"hello": hello, "done": done, "stopped": stopped, "alert": alert, "sad": sad}


# ---------------------------------------------------------------- generative babble

class Mood:
    """Slowly drifting pitch/energy so the chatter wanders instead of looping."""

    def __init__(self, r):
        self.r = r
        self.pitch = r.uniform(1000, 1900)
        self.energy = r.random()
        self.clock, self.swell = r.uniform(0, 10), r.uniform(2.5, 4.5)  # sparkle density cycle

    def drift(self):
        self.pitch = min(2400, max(700, self.pitch * self.r.uniform(0.85, 1.18)))
        self.energy = min(1.0, max(0.0, self.energy + self.r.uniform(-0.3, 0.3)))


def sweep(r, m):
    a = m.pitch * r.uniform(0.6, 1.6)
    b = a * r.choice([r.uniform(0.4, 0.8), r.uniform(1.3, 2.4)])
    k = r.uniform(0.4, 2.5)
    return tone(lambda t, x: a + (b - a) * x ** k, r.uniform(0.04, 0.16), r.uniform(0.35, 0.55), r.randrange(4))


def warble(r, m):
    c, glide = m.pitch * r.uniform(0.8, 1.5), r.uniform(-0.4, 0.4)
    depth, rate = c * r.uniform(0.05, 0.25), r.uniform(12, 40)
    return tone(lambda t, x: c * (1 + glide * x) + depth * math.sin(2 * math.pi * rate * t),
                r.uniform(0.12, 0.4), 0.45, r.randrange(4))


def trill(r, m):
    a = m.pitch * r.uniform(0.8, 1.4)
    b, rate = a * r.uniform(1.15, 1.6), r.uniform(14, 28)
    return tone(lambda t, x: a if math.sin(2 * math.pi * rate * t) > 0 else b,
                r.uniform(0.15, 0.45), 0.4, r.randrange(3))


def blips(r, m):
    out = []
    for _ in range(r.randint(3, 9)):
        f = m.pitch * r.choice((0.75, 1, 1.25, 1.5, 2)) * r.uniform(0.97, 1.03)
        out += tone(f, r.uniform(0.02, 0.05), 0.4, r.randrange(4)) + silence(r.uniform(0.005, 0.03))
    return out


def whistle(r, m):
    a, b = m.pitch * r.uniform(0.7, 1.8), m.pitch * r.uniform(0.7, 1.8)
    vib = r.uniform(4, 8)
    return tone(lambda t, x: a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * x)) + a * 0.02 * math.sin(2 * math.pi * vib * t),
                r.uniform(0.25, 0.6), 0.4, r.randrange(2))


def burble(r, m):
    steps = [m.pitch * r.uniform(0.35, 0.8) for _ in range(40)]
    hold = r.uniform(0.012, 0.03)
    return tone(lambda t, x: steps[int(t / hold) % 40], r.uniform(0.15, 0.4), 0.45, r.randrange(2, 4))


def scream(r, m):  # rare outburst
    return tone(lambda t, x: 3200 - 2600 * x ** 0.6 + 120 * math.sin(2 * math.pi * 25 * t), r.uniform(0.4, 0.7), 0.45, 3)


def phrase(r, m):
    e = m.energy  # excited -> blips/trills/sweeps; pensive -> whistles/burbles/warbles
    kinds = (sweep, warble, trill, blips, whistle, burble, scream)
    weights = (2 + 3 * e, 2, 1 + 2 * e, 1 + 3 * e, 3 - 2 * e, 2.5 - 1.5 * e, 0.08)
    out = []
    for _ in range(r.randint(2, 4 + int(6 * e))):
        out += r.choices(kinds, weights)[0](r, m) + silence(r.uniform(0, 0.06))
    if r.random() < 0.4:  # end like a question (up) or a statement (down)
        a = m.pitch * r.uniform(0.9, 1.3)
        b = a * (r.uniform(1.5, 2.2) if r.random() < 0.5 else r.uniform(0.45, 0.7))
        out += tone(lambda t, x: a + (b - a) * x ** 1.5, r.uniform(0.1, 0.22), 0.45, r.randrange(3))
    return out


def finished(r=None, seconds=2.0):
    """Response-finished notification: fresh R2 chatter, cut to fit, ending on the fixed done() signature."""
    r = r or random.Random()
    m = Mood(r)
    m.energy = max(m.energy, 0.7)
    tail = silence(0.05) + done()
    limit = int(RATE * seconds) - len(tail)
    out = []
    while len(out) < limit:
        m.drift()
        out += phrase(r, m) + silence(r.uniform(0.04, 0.1))
    out = out[:limit]
    fade_n = int(RATE * 0.08)
    for i in range(1, fade_n + 1):  # soften the cut
        out[-i] *= i / fade_n
    return out + tail


def murmur(r, m, seconds):
    """Thinking voice: a quiet sparkle of tiny, very short high blips at random pitches.

    Density swells and thins slowly; m.clock carries the swell across chunks so it never restarts.
    """
    n = int(RATE * seconds)
    out = [0.0] * n
    pos = 0
    while True:
        t = m.clock + pos / RATE
        rate = 4 + 16 * (0.5 - 0.5 * math.cos(2 * math.pi * t / m.swell))
        pos += int(RATE * r.expovariate(rate))
        if pos >= n:
            break
        g = tone(r.uniform(1800, 4200), r.uniform(0.006, 0.016), r.uniform(0.15, 0.35), timbre=0, attack=0.002, release=0.004)
        for i, v in enumerate(g[: n - pos]):
            out[pos + i] += v
    m.clock += seconds
    return out


# ---------------------------------------------------------------- output

def write(samples, path, gain=1.0):
    pcm = array.array("h", (int(max(-1.0, min(1.0, s * gain)) * 32000) for s in samples))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def play_cmd(path):
    for cmd, args in (("afplay", []), ("paplay", []), ("aplay", ["-q"])):
        if shutil.which(cmd):
            return [cmd, *args, path]
    raise SystemExit("r2: no audio player found (need afplay, paplay or aplay)")


class Transcript:
    """Tails the session transcript for activity and for the user hitting Stop (which fires no hook)."""

    def __init__(self, path):
        try:
            self.path, self.pos = path, os.path.getsize(path)  # ignore history
            self.pending = b""
        except (OSError, TypeError):
            self.path, self.pending = None, b""

    def read_new(self):
        if not self.path:
            return b""
        try:
            with open(self.path, "rb") as f:
                f.seek(self.pos)
                data = f.read()
        except OSError:
            return b""
        self.pos += len(data)
        self.pending += data
        return data

    def interrupted(self):
        self.read_new()
        return b"[Request interrupted by user" in self.pending

    def take(self):
        data, self.pending = self.pending, b""
        return data


class Player:
    """Plays rendered chunks back to back, rendering the next while the current one plays."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="r2-")
        self.proc, self.n = None, 0

    def play(self, samples, gain):
        self.n += 1
        path = os.path.join(self.tmp, f"{self.n}.wav")
        write(samples, path, gain)
        self.wait()
        self.proc = subprocess.Popen(play_cmd(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.last = path

    def wait(self):
        if self.proc:
            self.proc.wait()
            os.remove(self.last)
            self.proc = None

    def busy(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.wait()

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        shutil.rmtree(self.tmp, ignore_errors=True)


def babble(state, transcript, vol, talk_vol, hello_vol, idle_limit=300, max_seconds=3600):
    """Say hello, then sparkle quietly while Claude works.

    <state>.finish (Stop hook): play the 2s finished() notification and exit.
    <state>.stopped (Cursor/Codex interrupt hooks), or Claude's transcript interrupt marker: play stopped() and exit.
    <state>.error (Cursor stop with status "error"): play sad() and exit.
    <state>.alert (Notification hook): play alert(), then stay quiet until the transcript shows activity.
    """
    try:
        os.setsid()  # outlive the hook process: some agents clean up a hook's process group when it exits
    except OSError:
        pass
    r = random.Random()  # seeded from OS entropy: never the same twice
    m, player, tx = Mood(r), Player(), Transcript(transcript)
    flag = lambda name: os.path.exists(f"{state}.{name}")

    def log(msg):
        if os.environ.get("R2_DEBUG_LOG"):
            with open(os.environ["R2_DEBUG_LOG"], "a") as f:
                f.write(f"babble {os.path.basename(state)} {msg}\n")

    def bail(*sig):
        log("exit: " + ("killed" if sig else "done"))
        player.close()
        for name in ("pid", "finish", "stopped", "error", "alert"):
            try:
                os.remove(f"{state}.{name}")
            except OSError:
                pass
        sys.exit(0)

    def last_word(samples, name):
        log("playing " + name)
        player.stop()
        player.play(samples, talk_vol)
        player.wait()
        bail()

    signal.signal(signal.SIGTERM, bail)
    signal.signal(signal.SIGINT, bail)
    start = last_activity = time.monotonic()
    paused = False

    player.play(hello(), hello_vol)
    while True:
        now = time.monotonic()
        idle = tx.path and now - last_activity > idle_limit
        limit = max_seconds if tx.path else min(max_seconds, 1200)  # nothing to watch: give up after 20 min
        if now - start > limit or idle:  # orphaned or abandoned
            player.wait()
            bail()
        tx.read_new()
        new = tx.take()
        if new:
            last_activity, paused = now, False
        if b"[Request interrupted by user" in new or flag("stopped"):
            last_word(stopped(), "stopped")
        if flag("error"):
            last_word(sad(), "sad")
        if flag("finish"):
            last_word(finished(r), "finished")
        if flag("alert"):
            os.remove(f"{state}.alert")
            paused = True
            player.stop()
            player.play(alert(), talk_vol)
            continue
        if paused:
            time.sleep(0.3)
            continue

        player.play(murmur(r, m, r.uniform(1.0, 2.0)), vol)
        while player.busy():  # react within 0.1s rather than at the end of the chunk
            if any(flag(n) for n in ("finish", "stopped", "error", "alert")) or tx.interrupted():
                break
            time.sleep(0.1)


def main(argv):
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    kind = argv[0] if argv and not argv[0].startswith("--") else "hello"
    vol = float(opt("--vol", 0.6))
    if kind == "babble":
        babble(opt("--state", os.path.join(tempfile.gettempdir(), "claude-r2-manual")), opt("--transcript", None),
               float(opt("--vol", 0.15)), float(opt("--talk-vol", 0.8)), float(opt("--hello-vol", 0.6)))
        return
    if kind == "finished":
        FIXED["finished"] = finished
    if kind not in FIXED:
        raise SystemExit(f"r2: unknown phrase {kind!r}; try one of {', '.join([*FIXED, 'finished', 'babble'])}")
    out = opt("--out", None)
    path = out or tempfile.mktemp(suffix=".wav")
    write(FIXED[kind](), path, vol)
    if not out:
        subprocess.run(play_cmd(path))
        os.remove(path)


if __name__ == "__main__":
    main(sys.argv[1:])

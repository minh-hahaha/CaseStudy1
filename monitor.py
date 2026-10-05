"""Resource monitoring + adaptive response (Case Study 2, Deliverable 6 EC).

A daemon thread samples CPU and RAM. On crossing a threshold it:
  (a) sends a Discord webhook alert (once, on the transition), and
  (b) sets an `overloaded` flag the router reads to shed load.
When usage drops below (threshold - RECOVER_MARGIN) it sends a recovery
alert and clears the flag, so the system returns to normal on its own.

Env (all optional): CPU_THRESHOLD(80) MEM_THRESHOLD(80) RECOVER_MARGIN(10)
CHECK_INTERVAL(10) DISCORD_WEBHOOK_URL.  Set CPU_THRESHOLD=5 to force a trip.
"""
import os, threading, time
import psutil, requests

CPU_THRESHOLD  = float(os.getenv("CPU_THRESHOLD", 80))
MEM_THRESHOLD  = float(os.getenv("MEM_THRESHOLD", 80))
RECOVER_MARGIN = float(os.getenv("RECOVER_MARGIN", 10))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))
WEBHOOK        = os.getenv("DISCORD_WEBHOOK_URL")

_state = {"overloaded": False, "cpu": 0.0, "mem": 0.0}
_started = False

def _notify(msg: str) -> None:
    print(f"[monitor] {msg}", flush=True)
    if not WEBHOOK:
        return
    try:
        # Discord's edge 403s the default UA, so send a normal one.
        requests.post(WEBHOOK, json={"content": msg},
                      headers={"User-Agent": "cs553-monitor/1.0"}, timeout=5)
    except requests.RequestException as exc:
        print(f"[monitor] webhook failed: {exc}", flush=True)

def _loop() -> None:
    while True:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory().percent
        _state["cpu"], _state["mem"] = cpu, mem
        over = cpu > CPU_THRESHOLD or mem > MEM_THRESHOLD
        recovered = (cpu < CPU_THRESHOLD - RECOVER_MARGIN
                     and mem < MEM_THRESHOLD - RECOVER_MARGIN)
        if over and not _state["overloaded"]:
            _state["overloaded"] = True
            _notify(f":warning: VM near capacity (CPU {cpu:.0f}%, RAM {mem:.0f}%). "
                    f"Shedding load: new requests get an 'at capacity' message.")
        elif recovered and _state["overloaded"]:
            _state["overloaded"] = False
            _notify(f":white_check_mark: VM load normal (CPU {cpu:.0f}%, "
                    f"RAM {mem:.0f}%). Serving requests normally.")
        time.sleep(CHECK_INTERVAL)

def start() -> None:
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_loop, daemon=True).start()

def is_overloaded() -> bool:
    return _state["overloaded"]

def status_text() -> str:
    return f"CPU {_state['cpu']:.0f}% | RAM {_state['mem']:.0f}%"
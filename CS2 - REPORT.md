# DS/CS553 Case Study 2 Report
https://github.com/minh-hahaha/CaseStudy1/tree/casestudy2

## a. Group Members' Names

Minh Ha, Max Jeronimo

## b. Virtual Machine Setup Process

Our group (group 7) was given the VM `paffenroth-23.dyn.wpi.edu`, which we reach on port 22007 as `student-admin`. Every group's VM starts with the same shared class key, so anyone with it could log into our machine. Replacing it was the first thing we did.

We wrote `deploy_first_part.sh` to do the lockdown, and its main goal is to not lock ourselves out. It builds a fresh `authorized_keys` from our own public key plus any teammate keys in a `pubkeys/` folder (it refuses to run if the class key is in there). On a fresh VM it adds our keys first, confirms our key actually logs in, and only then replaces `~/.ssh/authorized_keys` with just our group's keys, which removes the class key. It finishes by checking that the class key is now rejected. Each teammate logs in as the same `student-admin` user with their own private key; nobody ever shares a private key.

The VM runs Ubuntu 22.04 with 4 GB RAM and no GPU; system Python is 3.10.12. Our code lives in `~/CaseStudy1` (a clone of our Case Study 1 repo on the `casestudy2` branch), and we keep the virtualenv at `~/venv`, outside the repo, so pulling or re-cloning never disturbs it. Setup is: install `python3.10-venv`, create the venv, install the CPU-only PyTorch wheel first (plain `torch` would pull gigabytes of unusable CUDA libraries), then the rest of `requirements.txt`. The remote model needs a Hugging Face token, which on the Space came from the user's login but doesn't exist on a VM, so we keep it in `~/.cs553.env` (`chmod 600`, outside the repo) and load it from a small `start_app.sh` launcher.

## c. Deployment Process

Both products live in one Gradio app (`app.py`, "Meme Creator"). BLIP always runs locally to describe the image; a **Routing** setting then picks who writes the captions: the API-based product sends the description to a remote LLM through the Hugging Face Inference API, and the local product runs `Qwen/Qwen3-0.6B` on the VM. One deployment covers both, and we tested each by setting Routing to remote (2a) and local (2b).

**Changes we made for the VM:**

1. *Reachability.* Gradio defaults to `127.0.0.1`, so nothing outside the VM could connect. We set `demo.launch(server_name="0.0.0.0", server_port=7860, ...)` (commit `d4e5276`). Port 8007 on the VM forwards to 7860 inside it, so the app is at `http://paffenroth-23.dyn.wpi.edu:8007`.
2. *Device check.* `src/compute.py` returned `"cuda"` whenever `spaces` could be imported, which is true on the VM even though there's no GPU. We changed it to `if is_zero_gpu() and is_on_space():` (commit `a768920`) so it falls through to CPU on the VM.
3. *Login.* The app already uses the `HF_TOKEN` environment variable when it isn't on a Space, so no change was needed beyond providing the token.

**Problems we hit:** the venv already on the VM was built on a pre-release Python (`3.11.0rc1`) and crashed loading BLIP with `AttributeError: module 'sys' has no attribute 'get_int_max_str_digits'`; rebuilding on system Python 3.10.12 fixed it (and `python3 -m venv` first needed `python3.10-venv` for `ensurepip`). The first request is slow because the models download on first use; after that they stay cached. With both models loaded the app uses about 2.6 GB of RAM, so it fits the 4 GB VM with room to spare.

**Result:** both products work at `http://paffenroth-23.dyn.wpi.edu:8007`. The app launches detached (via `setsid`), so it keeps running after we log out. Part 3 automates deploying and recovering it.


## d. Automated Recovery

**Deploy script.** Deployment is two scripts so a wiped VM rebuilds with no manual typing. `deploy_first_part.sh` does the key lockdown and copies the repo to the VM as `~/CaseStudy1`. `deploy_second_part.sh` copies the secrets to `~/.cs553.env`, installs `python3-venv`, builds the venv, installs requirements, and launches the app detached. Rerunning both in order rebuilds everything.

**Where the checker runs.** The watchdog can't live on the VM it rescues (it would die with it), and GitHub Actions can't reach the class VMs. So it runs on `linux.wpi.edu`, an always-on WPI server, via cron every two minutes:

```
*/2 * * * * /home/mtjeronimo/cs2/recover.sh
```

**Detecting failure.** Requesting the app's public port from linux.wpi.edu always failed (WPI blocks that cross-host request), so `recover.sh` checks *on the VM* over SSH using a dedicated recovery key: it tests whether anything is listening on port 7860. This separates "VM unreachable" (SSH fails) from "VM up, app dead" (SSH works, port closed). The recovery key has no passphrase because cron is unattended; it sits in a `chmod 700` folder, `chmod 600`, and its public key is in `pubkeys/` so a redeploy re-authorizes it. The logic: SSH fails → log that a manual redeploy is needed; app not listening → restart it; app listening → healthy.

**Resilience test.** We killed the app (`pkill -f app.py`) and watched the log. Our first version detected the outage but the app stayed down:

```
15:26  DOWN: app not listening on 7860 - restarting
15:26  STILL DOWN after restart
15:28  DOWN ... STILL DOWN
```

The restart backgrounded the launch *inside* the SSH session, so the app was killed when that session closed. We fixed it by detaching in a subshell before the session returns:

```
(setsid bash ~/CaseStudy1/start_app.sh > ~/CaseStudy1/log.txt 2>&1 < /dev/null &); sleep 3
```

After that, the next scheduled run recovered the app on its own, with no manual login:

```
15:32  DOWN: app not listening on 7860 - restarting
15:32  RECOVERED: app restarted (now listening on 7860)
15:34  OK: app healthy (listening on 7860)
```

(monitoring.png)

**Limitations and improvements.** Detection can lag up to two minutes (the cron cadence). The passphrase-less key on a shared server is a real tradeoff, limited by file permissions and the fact that the VM is disposable. A full wipe isn't auto-rebuilt; that would mean staging the class key on a shared server, which we chose not to do, so a wipe means rerunning the two deploy scripts (staged and ready). We'd improve this by running the app under `systemd` (instant OS-level restart instead of a two-minute cron), restricting the recovery key with a forced command, and automating full-wipe redeploy.

## e. Additional Insights, Challenges, and Future Improvements

The main lesson was that automating something isn't the same as automating it correctly: our watchdog detected failures on the first try, but recovery silently failed for three cycles because the restarted app was being killed with its SSH session. We only caught it by watching a real failure instead of trusting the happy path. We also learned to check the Python *version*, not just the packages (`pip check` passed on the broken venv because nothing was installed yet), and that platform assumptions break quietly across machines (the "spaces imports means GPU" shortcut was right on the Space, wrong on the VM). Keeping the token, venv, and model cache outside the repo paid off. Future work: pre-download models during deploy, pin exact versions including the CPU torch wheel, clean up the transformers deprecation warnings, and move to a `systemd` service.

## f. Security and Automation Review (LLM)

We gave our deploy and recovery scripts to an LLM for review. The scripts contain only file paths and hostnames; all keys, tokens, and the webhook URL live in separate files, so no secret values were shared.

**Model:** Claude (Anthropic, Opus 4.8)

**Prompt:** "Here are three bash scripts for deploying and auto-recovering a Gradio app on a disposable Ubuntu class VM: `deploy_first_part.sh` (replaces the shared SSH key with our own and copies the code), `deploy_second_part.sh` (builds the venv, installs deps, launches the app), and `recover.sh` (runs on a separate always-on server via cron, checks the app over SSH, and restarts it if it's down). Please review them for security, reliability, and improvements. Point out the most important issues first. No secret values are included, only file paths and hostnames."

**Response:**

*Done well:* the lockdown verifies our key works before removing the class key (can't brick the VM) and confirms the class key is rejected; secrets stay in `~/.cs553.env` outside the repo; every ssh/scp uses `-i` with `IdentitiesOnly` and `BatchMode`; the watchdog's loopback-over-SSH check correctly distinguishes a dead app from an unreachable VM.

*Most important issues:* (1) The passphrase-less recovery key on a shared server is the biggest risk; restrict it in the VM's `authorized_keys` with `from="..."` and a forced `command="..."` so a leak can only run the one recovery action from one host. (2) Host-key checking is disabled (`StrictHostKeyChecking=no`), which drops MITM protection; reasonable for a wipe-prone VM but worth pinning once stable. (3) `deploy_first_part.sh` has no `set -euo pipefail`, so a mid-script failure could leave `authorized_keys` half-applied.

*Reliability:* (4) `pkill -f app.py` is too broad; use a pidfile. (5) The watchdog has no backoff or escalation; add a failure counter and alert after N failed restarts. (6) The health check only confirms the port is open, not that the app responds. (7) No log rotation on `recover.log`/`log.txt`.

*Lower priority:* centralize config instead of hard-coding it in each script; confirm `.cs553.env` and `log.txt` are gitignored; pin dependency versions; consider `systemd`.

*Bottom line:* the security-critical path (key lockdown) is well designed; the weak points are operational (the passphrase-less key, disabled host-key checking, missing `set -e`).

**Which we'd implement:** the quick wins now (confirm gitignores, add log rotation, switch `pkill` to a pidfile), then the forced-command key restriction as the highest-value security fix. Pinning versions and moving to `systemd` are already on our improvement list. We'd skip host-key pinning since the VM's key changes on every wipe.

## g. Resource Monitoring and Adaptive Response (Extra Credit)

We added resource monitoring in `src/monitor.py`. A background thread samples CPU and RAM every 10 seconds with `psutil` (already a dependency, so no new packages). The **threshold** is 80% CPU or RAM (set to 5% for the demo so it trips immediately), with a 10-point margin so it only clears below 70% and doesn't flap. When usage crosses the threshold it does two things: **sends a Discord webhook alert** to our team channel (with a normal `User-Agent` header, since Discord's edge blocks the default one), and **flips an overloaded flag** the router reads. Because all routing lives in `src/router.py`, this was a one-place change: `make_captions` sheds load by returning an "operating near capacity" message instead of running the heavy models. When usage falls back below 70%, it sends a recovery alert and clears the flag, so the app **returns to normal on its own**.

![alt text](discord)

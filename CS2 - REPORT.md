# DS/CS553 Case Study 2 Report

## a. Group Members' Names

Minh Ha, Max Jeronimo

## b. Virtual Machine Setup Process

**SSH access**

Our group (group 7) was given the VM `paffenroth-23.dyn.wpi.edu`, which we connect to on port 22007 as `student-admin`. At the start, every group's VM accepts the same shared class key. That means anyone in the class with that key could get into our machine, so the first thing we had to do was replace it with our own keys.

We made our own key pair (`minh-key`), and any teammate who needs access puts their public key in a `pubkeys/` folder. Then we wrote a script, `deploy_first_part.sh`, to do the lockdown. The main thing we were worried about was locking ourselves out, so the script is careful about the order it does things in:

1. It builds a new `authorized_keys` file with our public key and our teammates' public keys. If the class key somehow ends up in there, it stops.
2. It checks which key works right now. If our key already works, the machine is already locked. If only the class key works, the VM is fresh, so it adds our keys first and then tests that our key actually logs in.
3. Only after our key is confirmed working does it replace `~/.ssh/authorized_keys` on the VM with just our group's keys. This is the step that removes the class key.
4. At the end it tries the class key again to make sure it gets rejected.

We pass the key with `-i` on every ssh/scp command instead of using ssh-agent, which also means the script can just be rerun if the VM gets wiped. My teammate logs in as the same `student-admin` user, just with their own private key. If the professor needed access, the plan would be to add his public key to `pubkeys/`. Nobody would ever send a private key.

**Virtual environment**

The VM runs Ubuntu 22.04 with 4 GB of RAM and no GPU. Disk space wasn't an issue (1.8 TB, 37% used). The system Python is 3.10.12.

Our code is in `~/CaseStudy1`, which is a clone of our Case Study 1 repo on the `casestudy2` branch. We kept the virtual environment at `~/venv`, outside the repo, so pulling new code or re-cloning doesn't mess with it.

Setting it up:

1. Installed `python3.10-venv` with apt. Without it, `python3 -m venv` creates the folder but can't install pip into it.
2. Created the venv with the system Python 3.10.12.
3. Installed the CPU-only version of PyTorch from PyTorch's CPU wheel index. We did this first on purpose: plain `torch` from `requirements.txt` would have downloaded a few GB of CUDA libraries we can't even use on this machine.
4. Installed everything else from `requirements.txt` (`gradio[oauth]==6.26.0`, `transformers` 5.18.0, `accelerate`, `huggingface_hub`, `pillow`, `spaces`, `httpx2`).
5. Checked that it worked by importing `BlipForConditionalGeneration`, `gradio` and `torch` from inside the venv.

The remote model needs a Hugging Face token. On our Hugging Face Space, the app got the token from the user's login or a Space secret, but neither of those exists on a VM. So we put the token in a file, `~/.cs553.env`. We created it with `umask 077` so only `student-admin` can read it, and typed the token into a hidden `read -s` prompt so it never showed up on screen or in the shell history. The file is outside the repo so it can't accidentally get committed. We also wrote a short launcher, `~/start_app.sh`, that loads the token and starts the app, so neither of us has to remember the commands.

## c. Deployment Process

In Case Study 1 we built both products into one Gradio app (`app.py`, "Meme Creator"). BLIP (`Salesforce/blip-image-captioning-base`) always runs locally to describe the image. Then a **Routing** setting picks which product writes the captions: the API-based product sends the description to a remote LLM through the Hugging Face Inference API, and the local product runs `Qwen/Qwen3-0.6B` right on the VM. So one deployment covers both products. We tested them separately by setting Routing to remote for 2a and to local for 2b.

**Changes we made for the VM**

1. *Making the app reachable.* By default, Gradio only listens on `127.0.0.1`, so nothing outside the VM could connect. We changed the launch line to `demo.launch(server_name="0.0.0.0", server_port=7860, ...)` (commit `d4e5276`). Port 8007 on the VM forwards to 7860 inside it, so the app is at `http://paffenroth-23.dyn.wpi.edu:8007` on the WPI network. We first tested it through an SSH tunnel (`ssh -L 7860:localhost:7860 ...`), then opened port 8007 directly.
2. *Fixing the device check.* `src/compute.py` returned `"cuda"` any time the `spaces` package could be imported. That shortcut was meant for ZeroGPU on Hugging Face. But `spaces` is in our requirements, so it imports fine on the VM too, and the app would have tried to put the models on a GPU that isn't there. We changed the line to `if is_zero_gpu() and is_on_space():` (commit `a768920`). It still behaves the same on the Space, and on the VM it falls through to the normal check and uses the CPU.
3. *Login.* The app already hides the Hugging Face login button when it's not running on a Space and uses the `HF_TOKEN` environment variable instead, which comes from our `~/.cs553.env` file. So we didn't have to change anything here.

**Problems we ran into**

- *The old venv used a broken Python.* The venv that was already on the VM was built on a pre-release Python (`3.11.0rc1`). Installing packages worked fine, but the first time we generated captions, it crashed while loading BLIP with `AttributeError: module 'sys' has no attribute 'get_int_max_str_digits'`. The PyTorch version we had needs that function, and that Python build doesn't have it. We moved the old venv out of the way (`~/venv-py311rc`) and rebuilt it with the system Python 3.10.12, which fixed it.
- *The rebuild failed at first.* `python3 -m venv` complained that `ensurepip` wasn't available. Installing `python3.10-venv` fixed that.
- *The first request was really slow.* The models get downloaded the first time they're used: BLIP on the first request, and Qwen the first time you pick local routing. While Qwen was loading, `top` showed around 50% I/O wait with the Python process barely using any CPU. The load average went up to about 18, but that was from waiting on the disk, not the CPU being busy. After that first time, the models stay in memory, and they're cached on disk for when the app restarts.
- *Memory was tight but fine.* With both BLIP and Qwen loaded, the app used about 2.6 GB of RAM (around 65%). There was still about 2.3 GB available and it never touched swap, so both products fit on the 4 GB VM.
- *Warnings in the logs.* Transformers prints some deprecation warnings about how `src/local_llm.py` passes the generation settings. Captions still generate correctly, so we left these as something to clean up later.

**Result**

Both products work on the VM at `http://paffenroth-23.dyn.wpi.edu:8007`.  Right now the app runs in the foreground of an SSH session, so it stops when we log out. Part 3 is where we automate deploying it and bringing it back up.

## d. Automated Recovery

The deploy script

Deployment is split into two scripts so a wiped VM can go from bare to running without us typing anything by hand.

deploy_first_part.sh does the key lockdown from part (b), then clones our repo (minh-hahaha/CaseStudy1, branch casestudy2) and copies it onto the VM as ~/CaseStudy1.
deploy_second_part.sh finishes the job: it copies the secrets file up to ~/.cs553.env, installs python3-venv, builds the venv at ~/venv, installs the requirements, and launches the app detached with start_app.sh. The launch is wrapped so it survives the SSH session closing.

Rerunning both in order rebuilds the whole deployment after a wipe.

Why the checker runs on linux.wpi.edu

The watchdog can't live on the VM it is supposed to rescue: if the VM goes down, a watchdog on that same VM goes down with it. GitHub Actions can't help either, because the Actions runners can't reach the class VMs on the WPI network. So we put the checker on linux.wpi.edu, a WPI login server that is always up and can reach our VM, and run it on a cron schedule. Our script is recover.sh, and the cron line runs it every two minutes:

*/2 * * * * /home/mtjeronimo/cs2/recover.sh

How failures get detected

We first tried having recover.sh check the app by requesting http://paffenroth-23.dyn.wpi.edu:8007 from linux.wpi.edu, but that always failed (HTTP 000) because WPI blocks that cross-host request. So the check runs on the VM instead, over SSH: recover.sh logs into the VM with a dedicated recovery key and tests whether anything is listening on port 7860 (using a bash /dev/tcp connection test). This also cleanly separates "the VM is unreachable" (SSH itself fails) from "the VM is up but the app died" (SSH works, port 7860 is closed).

The recovery key is a separate key with no passphrase, authorized on the VM. We had to make it passphrase-less because cron runs unattended, with no one there to type a passphrase. The private key lives in a chmod 700 folder on our personal linux.wpi.edu account, chmod 600. Its public key is also in our pubkeys/ folder, so deploy_first_part.sh re-authorizes it automatically after a wipe.

The logic is three steps: if SSH fails, the VM is off or wiped, so it logs that a manual redeploy is needed; if SSH works but the app isn't listening, it restarts the app; if the app is listening, it logs that everything is healthy and exits.

Resilience test and what happened

We tested by killing the app on the VM (pkill -f app.py) and watching the recovery log on linux.wpi.edu. Our first version did not work: the log showed the outage being detected but the app staying down.

15:24  OK: app healthy (listening on 7860)
15:26  DOWN: app not listening on 7860 - restarting
15:26  STILL DOWN after restart
15:28  DOWN ... STILL DOWN
15:30  DOWN ... STILL DOWN

The problem was in how the restart launched the app. The restart command backgrounded the launch inside the SSH session (setsid start_app.sh &), but because the SSH connection closed right after, the app was killed along with the session before it could finish starting. We fixed it by wrapping the launch in a detached subshell and giving it a moment to detach before the SSH session returns:

(setsid bash ~/CaseStudy1/start_app.sh > ~/CaseStudy1/log.txt 2>&1 < /dev/null &); sleep 3

After that change, the next scheduled run recovered the app on its own:

15:32  DOWN: app not listening on 7860 - restarting
15:32  RECOVERED: app restarted (now listening on 7860)
15:34  OK: app healthy (listening on 7860)
15:36  OK: app healthy (listening on 7860)


No manual login was needed. We killed the app, and within one two-minute cron cycle the watchdog detected it and brought it back.

How well it worked, limitations, and improvements

It works reliably for the failure we most expected: the app process dying while the VM stays up. The three-step design also means an unreachable VM is at least detected and logged rather than silently ignored.

Limitations:

Detection latency. With a two-minute cron cadence, the app can be down for up to two minutes before recovery starts. Fine for a class project, too slow for real traffic.
The passphrase-less recovery key is the main security tradeoff. A key with no passphrase sitting on a shared server is a real risk. We limited the blast radius by keeping it in a locked-down folder, giving it 600 permissions, and relying on the fact that the VM itself is disposable, but a passwordless key is still a passwordless key.
Full-wipe recovery is not automated. recover.sh restarts a crashed app, but it does not by itself rebuild a VM that was wiped back to the class key. Doing that automatically would mean staging the shared class key on linux.wpi.edu too, which we chose not to do on a multi-user server. For now, a wipe means rerunning the two deploy scripts, which are staged there and ready.

What we'd improve: run the app under systemd so the operating system restarts it instantly instead of waiting on a two-minute cron, lower the cron interval or switch to an event-based trigger, restrict the recovery key with a forced command in authorized_keys so it can only do exactly what the watchdog needs, and automate the full redeploy path for a wiped VM.

e. Additional Insights, Challenges, and Future Improvements

The biggest thing we learned early on is to check the Python version, not just the packages. The old venv looked fine, and pip check even passed, but only because nothing was installed yet. The real problem didn't show up until torch was actually imported. We also learned that code written for one platform can break quietly on another. The "if spaces imports, there's a GPU" shortcut made total sense on Hugging Face and was just wrong on our VM. Keeping the token, the venv and the model cache outside the repo turned out to be a good call, since it means we can pull or re-clone the code without worrying about losing anything.

Part 3 taught us a different lesson: automating something is not the same as automating it correctly. Our recovery watchdog detected failures perfectly from the first try, but the recovery itself quietly failed for three cycles because the restarted app was being killed with the SSH session that launched it. The fix was small (detach the process before the session closes), but we only found it because we watched the log through a real failure instead of assuming it worked. A lot of the WSL friction on the laptop side taught us the same thing in miniature: file permissions on the Windows mount don't behave like Linux permissions, so SSH kept rejecting keys until we moved them into the Linux filesystem.

Things we'd like to improve: download the models during deployment so the first person to use the app after a fresh install doesn't have to wait, pin exact package versions (including CPU torch) so rebuilds are repeatable, clean up the transformers warnings in src/local_llm.py, and move the app to a systemd service so both the launch and the recovery are handled by the operating system rather than ad-hoc background processes.

f. Security and Automation Review (LLM)

We gave our deployment and recovery scripts to an LLM and asked it to review them for security, reliability, and anything we could improve. All real key material, tokens, and the webhook URL were already kept in separate files, so the scripts we shared contained only file paths and hostnames, no secret values.

Model: Claude (Anthropic, Opus 4.8)

Prompt:

Here are three bash scripts for deploying and auto-recovering a Gradio app on a disposable Ubuntu class VM: deploy_first_part.sh (replaces the shared SSH key with our own and copies the code), deploy_second_part.sh (builds the venv, installs deps, launches the app), and recover.sh (runs on a separate always-on server via cron, checks the app over SSH, and restarts it if it's down). Please review them for security, reliability, and improvements. Point out the most important issues first. No secret values are included, only file paths and hostnames.

Response:

"Review of deployment and recovery scripts
What's done well
The lockdown can't brick the VM. deploy_first_part.sh adds your keys and verifies your own key logs in before it ever removes the shared class key, and it re-checks at the end that the class key is rejected. That ordering is the single most important safety property here, and it's correct.
Secrets are handled sensibly. The token lives in ~/.cs553.env, chmod 600, outside the git repo, and is loaded at runtime rather than hard-coded. No secret values appear in any script.
Keys are used explicitly. Every ssh/scp passes -i with IdentitiesOnly=yes and BatchMode=yes, so the intended key is always used and the scripts never hang on a prompt.
The watchdog distinguishes failure modes. Checking port 7860 on the VM's own loopback over SSH correctly separates "VM unreachable" from "VM up, app dead," which is better than a single external ping.
Most important issues (highest priority first)

1. The passphrase-less recovery key is the biggest risk.
recover.sh authenticates with a key that has no passphrase, sitting on linux.wpi.edu, a shared multi-user server. Anyone who can read that file gets student-admin on your VM. chmod 600 plus a chmod 700 parent folder is the right start, but it does not protect you from a server administrator or a root-level compromise. Reduce the blast radius by restricting the key on the VM side, in ~/.ssh/authorized_keys:

from="<linux.wpi.edu host>",command="<only the restart command>",no-port-forwarding,no-pty ssh-ed25519 AAAA...

That way, even if the key leaks, it can only run your one recovery action, only from that one host.

2. Host-key verification is disabled everywhere.
All three scripts use StrictHostKeyChecking=no (and the deploy scripts also UserKnownHostsFile=/dev/null). This removes any protection against a man-in-the-middle on the SSH connection. It's a reasonable choice for a VM whose host key changes on every wipe, but it is a real weakening, so it should be a documented decision, and worth pinning the host key once the VM is stable.

3. deploy_first_part.sh has no set -euo pipefail.
It starts with #! /bin/bash and no error-handling flags, so if a step in the middle fails (a failed scp, a network blip), the script keeps going and can leave authorized_keys in a half-applied state. The fresh-machine branch is where this matters most, since it's actively changing who can log in. Add set -euo pipefail and/or check the exit status of the key-install and scp steps before proceeding. (Your deploy_second_part.sh and recover.sh already do this.)

Reliability issues

4. pkill -f app.py is too broad.
It kills any process whose command line contains "app.py," which could catch an editor, a grep, or an unrelated process. Track the real PID in a pidfile when you launch, and kill that specific PID instead.

5. The watchdog has no backoff or escalation.
If start_app.sh is itself broken (bad env file, missing venv), recover.sh will restart it, see it's still down, and repeat every two minutes forever, with no alert that recovery is failing. Add a consecutive-failure counter and send a Discord alert after, say, 3 failed restarts, so a human knows automatic recovery has given up.

6. The health check is a port-open test, not a real request.
</dev/tcp/127.0.0.1/7860 only confirms something is listening. An app that has hung but still holds the port would read as healthy. A lightweight HTTP request to a known endpoint would catch that case.

7. No log rotation.
recover.log and the app's log.txt grow without bound. Add simple truncation or rotation, especially now that log.txt lives inside the repo folder.

Lower priority
Config is duplicated. deploy_first_part.sh hard-codes the port, host, and key path instead of sourcing config.sh like connect.sh does. Centralizing them would prevent the three scripts from drifting.
Confirm .cs553.env and log.txt are gitignored, so a secret or a noisy log never gets committed.
Pin exact dependency versions (including the CPU torch wheel) for repeatable rebuilds.
Consider a systemd service instead of setsid/nohup, so the OS supervises the process and restarts it instantly rather than waiting on a two-minute cron.
Bottom line

The security-critical path (the key lockdown) is well designed and fail-safe. The weakest points are operational: the passphrase-less key on a shared host, disabled host-key checking, and the lack of set -e in the one script that changes login access. Fixing #1–#3 would close the real gaps; #4–#7 would make the automation trustworthy enough to leave running unattended."

Which suggestions we'd implement. We would do the quick, high-value ones for sure: confirm .cs553.env and log.txt are gitignored, add log rotation, and switch pkill to a pidfile. We think the forced-command restriction on the recovery key (#1) is the most valuable security fix and would do it next, since it directly addresses the one real weakness in our design. Pinning versions and moving to systemd are the right long-term calls and are already on our Part (e) improvement list. We would hold off on pinning the host key (#2) only because our VM gets wiped and its host key changes, which would just cause failed logins.

g. Resource Monitoring and Adaptive Response (Extra Credit)

We added resource monitoring with an automatic reaction, in src/monitor.py.

Threshold used. 80% for CPU or RAM. For the demo we set CPU_THRESHOLD=5 in ~/.cs553.env so it trips immediately; in normal operation it is 80%. Recovery uses a margin, so the system only clears the overloaded state once usage drops below 70% (threshold minus a 10-point margin), which stops it from flapping on and off right at the line.
How usage is measured. A background daemon thread samples CPU and RAM every 10 seconds with psutil (psutil.cpu_percent and psutil.virtual_memory().percent). psutil was already installed as a dependency of accelerate, so this added no new packages.
What automated action is taken. The monitor does two things when usage crosses the threshold. First, it sends a Discord webhook alert to our team channel (the same webhook idea from Case Study 1; we had to set a normal User-Agent header because Discord's edge blocks the default one). Second, it flips an overloaded flag that the request router reads. Because all of our routing lives in src/router.py, this was a one-place change: when the flag is set, make_captions sheds load by immediately returning an "operating near capacity" message instead of running the heavy vision and caption models on an already-stressed VM.
How it returns to normal. When usage falls back below 70%, the monitor sends a recovery alert to Discord and clears the flag, and the app starts serving captions normally again, with no manual intervention.

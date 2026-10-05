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

Both products work on the VM at `http://paffenroth-23.dyn.wpi.edu:8007`. Screenshots: TODO (2a with Routing = remote, 2b with Routing = local). Right now the app runs in the foreground of an SSH session, so it stops when we log out. Part 3 is where we automate deploying it and bringing it back up.

## d. Automated Recovery

TODO after 3a to 3c: the deploy script, the recovery checker on linux.wpi.edu, how failures get detected, the resilience tests and what happened, how well it worked, limitations, and what we'd improve.

## e. Additional Insights, Challenges, and Future Improvements

The biggest thing we learned so far is to check the Python version, not just the packages. The old venv looked fine, and `pip check` even passed, but only because nothing was installed yet. The real problem didn't show up until torch was actually imported. We also learned that code written for one platform can break quietly on another. The "if `spaces` imports, there's a GPU" shortcut made total sense on Hugging Face and was just wrong on our VM. Keeping the token, the venv and the model cache outside the repo turned out to be a good call, since it means we can pull or re-clone the code without worrying about losing anything.

Things we'd like to improve: download the models during deployment so the first person to use the app after a fresh install doesn't have to wait, pin exact package versions (including CPU torch) so rebuilds are repeatable, and clean up the transformers warnings in `src/local_llm.py`.

TODO: add recovery and monitoring reflections after part 3.

## f. Security and Automation Review (LLM)

TODO once the scripts are done. Plan: give our deployment and recovery scripts to an LLM, with all keys, tokens and hostnames removed, and record the model, the full prompt and the full response. Then summarize the most useful suggestions and which ones we'd actually implement.

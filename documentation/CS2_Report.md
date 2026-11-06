# DS/CS553 Case Study 2: Deployment and Automated Recovery

## a. Group Members' Names

Minh Ha, TODO: teammate's full name

## b. Virtual Machine Setup Process

**SSH access.** Professor Paffenroth assigned our group (group 7) the VM `paffenroth-23.dyn.wpi.edu`. It is reached over SSH on port 22007 as the user `student-admin`. Every group's machine initially trusts the same shared class key (`student-admin_key`), so anyone holding that key could log into any group's VM. We generated our own key pair (`minh-key`), and teammates contribute their public keys through a `pubkeys/` folder.

Our script `deploy_first_part.sh` locks the machine down in an order that avoids locking ourselves out:

1. It builds a new `authorized_keys` file from our public key plus every teammate's public key. It refuses to continue if the class key appears in that file.
2. It checks which key currently works. If our key already works, the machine is already locked. If only the class key works, the machine is fresh: the script appends our keys using the class key, then confirms our key logs in before it changes anything else.
3. Only after that confirmation does it overwrite `~/.ssh/authorized_keys` on the VM with our group's keys alone, which removes the class key.
4. It finishes by trying the class key again and reports whether the machine is locked (class key rejected) or not.

Every command passes the key explicitly with `-i`, so no ssh-agent is needed, and the script can be rerun safely after the VM is wiped. Teammates log in as the same `student-admin` user with their own private keys. The professor does not hold a key to the locked machine. If access were required, we would add the professor's public key to `pubkeys/`, never share a private key.

**Virtual environment.** The VM runs Ubuntu 22.04 with 4 GB of RAM, no GPU, and ample disk (1.8 TB, 37% used). The system Python is 3.10.12. We set up the environment as follows:

1. Kept the application code at `~/CaseStudy1`, a clone of our Case Study 1 GitHub repository on the `casestudy2` branch.
2. Put the virtual environment at `~/venv`, outside the repository, so that `git pull` or a fresh clone never touches it.
3. Installed `python3.10-venv` with apt, because Ubuntu ships the `ensurepip` module separately and `python3 -m venv` cannot install pip without it.
4. Created the venv from the system Python 3.10.12.
5. Installed the CPU-only build of PyTorch from the PyTorch CPU wheel index first. The plain `torch` entry in `requirements.txt` would otherwise pull several gigabytes of CUDA libraries the VM cannot use.
6. Installed the rest of `requirements.txt`: `gradio[oauth]==6.26.0`, `transformers` (5.18.0 resolved), `accelerate`, `huggingface_hub`, `pillow`, `spaces` and `httpx2`.
7. Verified the install by importing `BlipForConditionalGeneration`, `gradio` and `torch` inside the venv.

The remote product needs a Hugging Face API token. On Hugging Face Spaces, the app gets it from the visitor's OAuth login or a Space secret. Neither exists on a VM, so the token lives in `~/.cs553.env`. We created that file with `umask 077` (mode 600, readable only by `student-admin`) and entered the token through a hidden `read -s` prompt, so it never appears on screen or in shell history. The file sits outside the repository so it can never be committed. A small launcher, `~/start_app.sh`, exports the token and starts the app.

## c. Deployment Process

Both Case Study 1 products live in a single Gradio application (`app.py`, "Meme Creator"). BLIP (`Salesforce/blip-image-captioning-base`) always runs locally to describe the uploaded image. A **Routing** control then selects which product writes the captions: the API-based product sends the description to a remotely hosted LLM through the Hugging Face Inference API, and the locally executed product runs `Qwen/Qwen3-0.6B` on the VM. One deployment therefore serves both products. We verified each one separately by forcing Routing to remote (2a) and to local (2b).

**Modifications for the VM environment.**

1. *Network binding.* Gradio listens on `127.0.0.1` by default, which is unreachable from outside the VM. We changed the launch call to `demo.launch(server_name="0.0.0.0", server_port=7860, ...)` (commit `d4e5276`). The VM's external port 8007 forwards to internal port 7860, so the deployed app is reachable at `http://paffenroth-23.dyn.wpi.edu:8007` from the WPI network. We first confirmed access through an SSH tunnel (`ssh -L 7860:localhost:7860 ...`), then directly on port 8007.
2. *Device selection.* `src/compute.py` returned `"cuda"` whenever the `spaces` package could be imported, a shortcut meant for Hugging Face ZeroGPU. `spaces` is in `requirements.txt`, so it imports on the VM too, and the local models would have been loaded onto a GPU that does not exist. We changed the check to `if is_zero_gpu() and is_on_space():` (commit `a768920`). Spaces behave exactly as before, and the VM falls back to `torch.cuda.is_available()` and selects the CPU.
3. *Authentication.* The app already hides the OAuth login button when it is not running on a Space (no `SPACE_ID`) and falls back to the `HF_TOKEN` environment variable. That variable is supplied by `~/.cs553.env`.

**Challenges.**

- *Broken Python in the original venv.* The original venv had been built on `/usr/lib/python3.11`, which reports `3.11.0rc1`, a pre-release build. The first caption request crashed while importing BLIP with `AttributeError: module 'sys' has no attribute 'get_int_max_str_digits'`. That function is required by the installed PyTorch and is missing from this release candidate. We moved the old venv aside (`~/venv-py311rc`) and rebuilt it on the system Python 3.10.12, which resolved the error.
- *Missing pip bootstrap.* The first rebuild failed because `ensurepip` was unavailable. Installing `python3.10-venv` fixed it.
- *Slow first request.* The first request downloads model weights into `~/.cache/huggingface`: BLIP for any request, plus Qwen the first time local routing is used. During the first local request, `top` showed about 50% I/O wait with the Python process mostly idle. The load average reached about 18, inflated by processes waiting on disk rather than by CPU work. Later requests reuse the in-memory models, and later restarts reuse the on-disk cache.
- *Memory headroom.* With both BLIP and Qwen loaded, the app used about 2.6 GB of resident memory (about 65% of RAM). Roughly 2.3 GB remained available and swap stayed unused, so both products fit within the 4 GB VM.
- *Library warnings.* Transformers logs deprecation warnings about how `src/local_llm.py` passes generation settings (`generation_config` together with explicit sampling arguments, and `max_length` alongside `max_new_tokens`). Generation works correctly; these are cleanup items for future library versions.

**Result.** Both products run on the VM and return captions at `http://paffenroth-23.dyn.wpi.edu:8007`. Screenshots: TODO (2a with Routing = remote, 2b with Routing = local). At this stage the app runs in the foreground of an SSH session and stops when that session ends. Section 3 adds automated deployment and recovery.

## d. Automated Recovery

TODO after deliverables 3a to 3c: the deployment script, the recovery checker on linux.wpi.edu, how failures are detected, resilience test steps and outcomes, effectiveness, limitations, and potential improvements.

## e. Additional Insights, Challenges, and Future Improvements

Lessons so far: verify the interpreter as well as the packages. The original venv passed `pip check` with nothing installed and ran a pre-release Python that only failed once torch was actually imported. Assumptions baked in for one platform, such as "the `spaces` package means a GPU exists", break silently on another, so hardware detection should check the actual hardware and runtime. Keeping secrets, the venv and the model cache outside the repository made redeploying the code safe.

Planned improvements: pre-download model weights during deployment so the first user request after a fresh install is not slow; pin exact dependency versions, including CPU torch, for reproducible rebuilds; and clean up the transformers deprecation warnings in `src/local_llm.py`.

TODO: add recovery and monitoring reflections after part 3.

## f. Security and Automation Review (LLM)

TODO after the scripts are final. The plan: send the deployment and recovery scripts, with all keys, tokens and hostnames redacted, to an LLM; record the model used, the complete prompt and the full response; then summarize the most useful recommendations and which ones we would implement.

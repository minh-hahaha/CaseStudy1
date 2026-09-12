"""MemeForge: Gradio front end for DS/CS553 Case Study 1.

Upload an image, pick a voice, get class-ready meme captions, render the meme.
Vision (BLIP) always runs locally on this Space. Caption writing is served
either by a remotely hosted LLM through the Inference API or by a locally
executed LLM, with automatic failover between them.

Structure, CSS and the OAuth login flow follow the class example (example.py).
"""

import time

import gradio as gr

from src import compute, local_llm, local_vision, remote_llm, router
from src.meme_render import render_meme
from src.styles import DEFAULT_STYLE, STYLES

PLACEMENTS = ["Top", "Bottom"]
UPLOAD_PROMPT = "Upload an image first."

fancy_css = """
.gradio-container {
    width: 96% !important;
    max-width: none !important;
}
#app-title {
    text-align: center;
    margin-bottom: 4px;
}
#app-subtitle {
    text-align: center;
    color: var(--body-text-color-subdued);
    margin-bottom: 24px;
}
#forge-container, #lab-container {
    width: 100%;
    border: 1px solid var(--border-color-primary);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
#model-note {
    font-size: 0.9em;
    color: var(--body-text-color-subdued);
    margin-top: 8px;
}
@media (max-width: 768px) {
    .gradio-container {
        width: 98% !important;
    }
    #forge-container, #lab-container {
        padding: 8px;
    }
}
"""


def _describe(image) -> tuple[str, float]:
    """Run local BLIP and report how long it took."""
    start = time.perf_counter()
    scene = local_vision.describe_image(image)
    return scene, time.perf_counter() - start


def _token_value(hf_token) -> str | None:
    """Pull the string out of Gradio's OAuth token, if a viewer is logged in."""
    return getattr(hf_token, "token", None)


def _status_block(source: str, vision_time: float, elapsed: float, note: str) -> str:
    """Report which model served the request (Deliverable 6c) plus timings."""
    bits = [
        f"**Served by:** {source}",
        f"**Vision (local BLIP):** {vision_time:.2f}s",
        f"**Caption generation:** {elapsed:.2f}s",
    ]
    if note:
        bits.append(f"**Note:** {note}")
    return "\n\n".join(bits)


def run_factory(
    image,
    style,
    topic,
    n,
    temperature,
    mode,
    simulate_outage,
    hf_token: gr.OAuthToken | None = None,
):
    """Describe the image, route the caption request, and fill the picker."""
    if image is None:
        return "", UPLOAD_PROMPT, gr.update(choices=[], value=None), None

    scene, vision_time = _describe(image)
    result = router.make_captions(
        scene=scene,
        style=style,
        n=int(n),
        temperature=float(temperature),
        topic=topic,
        mode=mode,
        simulate_outage=simulate_outage,
        token=_token_value(hf_token),
    )

    captions = result["captions"]
    return (
        f"*BLIP saw:* {scene}",
        _status_block(
            result["source"], vision_time, result["elapsed"], result["note"]
        ),
        gr.update(choices=captions, value=captions[0] if captions else None),
        None,
    )


def burn_caption(image, caption, placement):
    """Burn the chosen caption onto the image at the chosen edge."""
    if image is None or not caption:
        return None

    is_top = placement == "Top"
    return render_meme(
        image,
        top_text=caption if is_top else "",
        bottom_text="" if is_top else caption,
    )


def _as_bullets(captions) -> str:
    return "\n".join(f"- {caption}" for caption in captions)


def run_bakeoff(image, style, topic, hf_token: gr.OAuthToken | None = None):
    """Run both text paths on one identical scene, for report item 4d."""
    if image is None:
        return UPLOAD_PROMPT, "", ""

    scene, vision_time = _describe(image)

    remote_start = time.perf_counter()
    try:
        remote_out = _as_bullets(
            remote_llm.generate_captions(
                scene, style, 3, 0.9, topic=topic, token=_token_value(hf_token)
            )
        )
    except remote_llm.RemoteCaptionError as exc:
        remote_out = f"**Failed:** {exc}"
    remote_time = time.perf_counter() - remote_start

    local_start = time.perf_counter()
    try:
        local_out = _as_bullets(
            local_llm.generate_captions(scene, style, 3, 0.9, topic)
        )
    except local_llm.LocalCaptionError as exc:
        local_out = f"**Failed:** {exc}"
    local_time = time.perf_counter() - local_start

    header = (
        f"*BLIP saw:* {scene}  \n"
        f"Local vision: {vision_time:.2f}s | "
        f"Remote text: {remote_time:.2f}s | Local text: {local_time:.2f}s"
    )
    return header, remote_out, local_out


with gr.Blocks(title="MemeForge") as demo:
    with gr.Sidebar():
        # Gradio's LoginButton raises at construction time outside a Space
        # unless the machine already holds a token, so gate it on SPACE_ID and
        # let local runs fall through to the HF_TOKEN environment variable.
        if compute.is_on_space():
            gr.LoginButton()
        gr.Markdown(
            "Log in to use the remote model. Without a login the app falls back "
            "to the Space's own HF_TOKEN secret, and failing that, to the "
            "locally executed model.",
            elem_id="model-note",
        )

    gr.Markdown("# 🔥 MemeForge", elem_id="app-title")
    gr.Markdown(
        "Drop in an image, pick a voice, get class-ready meme captions. "
        "Vision runs locally on this Space. Captions come from a remote LLM, "
        "with automatic failover to a local model.",
        elem_id="app-subtitle",
    )

    with gr.Tab("Meme Factory"):
        with gr.Row(elem_id="forge-container"):
            with gr.Column(scale=1):
                image_in = gr.Image(type="pil", label="Image")
                style_in = gr.Dropdown(
                    list(STYLES), value=DEFAULT_STYLE, label="Voice"
                )
                topic_in = gr.Textbox(
                    label="Optional topic hook",
                    placeholder="e.g. gradient descent, midterm week",
                )
                with gr.Accordion("Generation settings", open=False):
                    n_in = gr.Slider(1, 6, value=3, step=1, label="Captions")
                    temp_in = gr.Slider(0.2, 1.4, value=0.9, step=0.1, label="Spice")
                    mode_in = gr.Radio(
                        router.MODES, value=router.AUTO_MODE, label="Routing"
                    )
                    outage_in = gr.Checkbox(
                        label="Simulate remote API outage (failover demo)"
                    )
                go = gr.Button("Generate captions", variant="primary")
            with gr.Column(scale=1):
                scene_out = gr.Markdown()
                status_out = gr.Markdown()
                caption_pick = gr.Radio(choices=[], label="Pick a caption")
                placement_in = gr.Radio(
                    PLACEMENTS, value="Bottom", label="Placement"
                )
                burn = gr.Button("Render meme")
                meme_out = gr.Image(label="Your meme", type="pil")

        go.click(
            run_factory,
            [image_in, style_in, topic_in, n_in, temp_in, mode_in, outage_in],
            [scene_out, status_out, caption_pick, meme_out],
        )
        burn.click(burn_caption, [image_in, caption_pick, placement_in], meme_out)

    with gr.Tab("Model Lab"):
        with gr.Column(elem_id="lab-container"):
            gr.Markdown(
                "Same image, same scene description, same prompt, both models. "
                "Use this to collect the performance numbers for the report."
            )
            lab_image = gr.Image(type="pil", label="Image")
            lab_style = gr.Dropdown(list(STYLES), value="Dad Joke", label="Voice")
            lab_topic = gr.Textbox(label="Optional topic hook")
            lab_go = gr.Button("Run both models", variant="primary")
            lab_header = gr.Markdown()
            with gr.Row():
                with gr.Column():
                    gr.Markdown(f"### Remote — `{remote_llm.DEFAULT_MODEL}`")
                    lab_remote = gr.Markdown()
                with gr.Column():
                    gr.Markdown(f"### Local — `{local_llm.MODEL_ID}`")
                    lab_local = gr.Markdown()

        lab_go.click(
            run_bakeoff,
            [lab_image, lab_style, lab_topic],
            [lab_header, lab_remote, lab_local],
        )


if __name__ == "__main__":
    # Gradio 6 moved `theme` and `css` off the Blocks constructor onto launch().
    demo.launch(theme=gr.themes.Soft(), css=fancy_css)

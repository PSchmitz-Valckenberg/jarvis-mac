"""Screenshot + vision — lets Jarvis look at what's on screen.

Captures the screen with macOS's `screencapture`, then asks a
vision-capable Groq model to describe it. Runs as a separate API call
from the main chat completion, since the configured chat model isn't
necessarily multimodal.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path

from .base import Tool, ToolError


class SeeScreenTool(Tool):
    name = "see_screen"
    description = (
        "Take a screenshot of the user's screen right now and describe "
        "what's on it, or answer a specific question about it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What to look for or ask about the screen. Defaults to a general description.",
            },
        },
        "required": [],
    }

    def run(self, question: str = "Describe what's visible on this screen.") -> str:
        from ..config import config
        from groq import Groq

        fd, path_str = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        path = Path(path_str)
        path.unlink(missing_ok=True)  # screencapture writes the file itself; just needed a unique name
        try:
            result = subprocess.run(
                ["screencapture", "-x", str(path)], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0 or not path.exists():
                raise ToolError((result.stderr or "screencapture failed").strip())

            # A full-resolution Retina screenshot is several MB raw — base64
            # of that trips Groq's request-size limit (413). Downscale with
            # macOS's built-in `sips` rather than pulling in an image library.
            subprocess.run(
                ["sips", "-Z", "1280", str(path)], capture_output=True, text=True, timeout=10
            )
            image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        finally:
            path.unlink(missing_ok=True)

        client = Groq(api_key=config.groq_api_key)
        try:
            completion = client.chat.completions.create(
                model=config.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=512,
            )
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Vision request failed: {exc}") from exc

        return (completion.choices[0].message.content or "").strip() or "(no description returned)"

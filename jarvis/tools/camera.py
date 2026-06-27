"""Camera input — one frame from the webcam, described via vision.

Mirrors vision.py's screenshot tool: capture, then ask a vision-capable
Groq model. Opens the camera only for the duration of one capture rather
than keeping it running, since this is an occasional "look at me/this"
action, not continuous monitoring.
"""

from __future__ import annotations

import base64

import cv2

from .base import Tool, ToolError


class SeeCameraTool(Tool):
    name = "see_camera"
    description = (
        "Take a single picture with the user's webcam right now and "
        "describe it, or answer a specific question about it. Use this "
        "when the user wants Jarvis to look at them or something held up "
        "to the camera — not for the screen, use see_screen for that."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "What to look for or ask about the picture. Defaults to a general description.",
            },
        },
        "required": [],
    }

    def run(self, question: str = "Describe what's visible in this picture.") -> str:
        from ..config import config
        from groq import Groq

        capture = cv2.VideoCapture(config.camera_index)
        try:
            if not capture.isOpened():
                raise ToolError(
                    "Couldn't open the camera — check System Settings > Privacy & "
                    "Security > Camera and make sure this app/binary is allowed."
                )
            ok, frame = capture.read()
        finally:
            capture.release()

        if not ok or frame is None:
            raise ToolError("Couldn't capture a frame from the camera.")

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            raise ToolError("Couldn't encode the captured frame.")
        image_b64 = base64.b64encode(buffer.tobytes()).decode("ascii")

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
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=512,
            )
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"Vision request failed: {exc}") from exc

        return (completion.choices[0].message.content or "").strip() or "(no description returned)"

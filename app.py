"""Hugging Face Spaces entry point for Organization Matching Registry (BCA / BQP).

This file runs the FastAPI web application on port 7860 (Hugging Face default)
and mounts Gradio to satisfy Hugging Face Space's Gradio SDK requirements.
"""

from __future__ import annotations

import os
import uvicorn
from api.main import app

PORT = int(os.environ.get("PORT", 7860))

try:
    import gradio as gr

    # Mount Gradio Blocks at /gradio so Hugging Face detects Gradio SDK cleanly
    demo = gr.Blocks(title="Tra cứu Tổ chức BCA / BQP")
    with demo:
        gr.Markdown(
            "# 🏛️ Hệ thống Tra cứu Tổ chức BCA / BQP\n\n"
            "Hệ thống đã sẵn sàng phục vụ. Truy cập giao diện chính tại root: [/](/)"
        )
    app = gr.mount_gradio_app(app, demo, path="/gradio")
except Exception as e:
    print(f"Gradio mounting skipped: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

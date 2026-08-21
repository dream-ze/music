# Workaround for gradio CLI requiring requests module (not installed in this env)
import sys
import unittest.mock
if 'requests' not in sys.modules:
    sys.modules['requests'] = unittest.mock.MagicMock()

import gradio as gr
import config
from src.pipeline import make_song

config.ensure_dirs()


def on_generate(lyrics_text, feeling, length_label, seed):
    length = "short" if length_label == "短版 Demo" else "full"
    seed_val = int(seed) if str(seed).strip() else None
    result = make_song(lyrics_text, feeling, length=length, seed=seed_val)
    return result["song"], result["structured_lyrics"]


with gr.Blocks(title="把歌词变成一首歌") as demo:
    gr.Markdown("## 🎵 把歌词变成一首歌")
    lyrics_in = gr.Textbox(label="歌词", lines=8, placeholder="我曾走过那条街……")
    feeling_in = gr.Textbox(
        label="你想要什么感觉？", placeholder="女声，R&B，深夜，温柔"
    )
    with gr.Accordion("高级设置", open=False):
        length_in = gr.Radio(
            ["短版 Demo", "完整歌曲"], value="完整歌曲", label="歌曲长度"
        )
        seed_in = gr.Textbox(label="Seed（留空随机）", value="")
    btn = gr.Button("帮我做成一首歌", variant="primary")
    audio_out = gr.Audio(label="成品", type="filepath")
    struct_out = gr.Textbox(label="结构化歌词", lines=8)
    gr.Markdown("_音色转换等功能见后续版本。克隆他人声音请确保已获授权。_")

    btn.click(
        on_generate,
        [lyrics_in, feeling_in, length_in, seed_in],
        [audio_out, struct_out],
    )

if __name__ == "__main__":
    demo.launch()

import gradio as gr
import config
from src import credentials
from src.pipeline import make_song

config.ensure_dirs()


def _credential_status(provider: str) -> str:
    if config.get_llm_provider(provider)["key_env"] is None:
        return "ℹ️ 此供应商无需 Key"
    try:
        return "✅ 已保存 Key" if credentials.has_saved_key(provider) else "⚪ 尚未保存 Key"
    except Exception:
        return "⚠️ 无法读取 Windows 凭据"


def on_provider_change(provider):
    return config.get_llm_provider(provider)["model"], _credential_status(provider)


def on_save_key(provider, api_key):
    try:
        credentials.save_key(provider, api_key)
        return "✅ Key 已安全保存", ""
    except Exception as exc:
        return f"⚠️ 保存失败：{exc}", ""


def on_delete_key(provider):
    try:
        credentials.delete_key(provider)
        return "🗑️ 已删除保存的 Key", ""
    except Exception:
        return "⚠️ 删除失败或尚未保存 Key", ""


def on_generate(
    lyrics_text, feeling, length_label, seed, provider, model, api_key
):
    length = "short" if length_label == "短版 Demo" else "full"
    s = str(seed).strip()
    try:
        seed_val = int(s) if s else None
    except ValueError:
        seed_val = None  # 非法输入按"随机"处理
    result = make_song(
        lyrics_text,
        feeling,
        length=length,
        seed=seed_val,
        llm_options={
            "provider": provider,
            "model": model,
            "api_key": (api_key or "").strip() or None,
        },
    )
    status = "\n".join(f"- {event}" for event in result["llm_status"])
    return result["song"], result["structured_lyrics"], status


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
        provider_in = gr.Dropdown(
            choices=[(item["label"], name) for name, item in config.LLM_PROVIDERS.items()],
            value="deepseek",
            label="文本模型供应商",
        )
        model_in = gr.Textbox(
            label="模型名称", value=config.get_llm_provider("deepseek")["model"]
        )
        api_key_in = gr.Textbox(
            label="API Key（仅本次使用；可保存到 Windows 凭据管理器）",
            type="password",
        )
        with gr.Row():
            save_key_btn = gr.Button("保存 Key")
            delete_key_btn = gr.Button("删除 Key")
        key_status_out = gr.Textbox(
            label="Key 状态", value=_credential_status("deepseek"), interactive=False
        )
    btn = gr.Button("帮我做成一首歌", variant="primary")
    audio_out = gr.Audio(label="成品", type="filepath")
    struct_out = gr.Textbox(label="结构化歌词", lines=8)
    llm_status_out = gr.Markdown("_等待生成_", label="文本模型状态")
    gr.Markdown("_音色转换等功能见后续版本。克隆他人声音请确保已获授权。_")

    btn.click(
        on_generate,
        [lyrics_in, feeling_in, length_in, seed_in, provider_in, model_in, api_key_in],
        [audio_out, struct_out, llm_status_out],
    )
    provider_in.change(
        on_provider_change, provider_in, [model_in, key_status_out]
    )
    save_key_btn.click(
        on_save_key, [provider_in, api_key_in], [key_status_out, api_key_in]
    )
    delete_key_btn.click(
        on_delete_key, provider_in, [key_status_out, api_key_in]
    )

if __name__ == "__main__":
    demo.launch()

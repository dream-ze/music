import app


def test_provider_change_returns_default_model_and_saved_status(monkeypatch):
    monkeypatch.setattr(app.credentials, "has_saved_key", lambda provider: True)
    model, status = app.on_provider_change("deepseek")
    assert model == "deepseek-v4-flash"
    assert status == "✅ 已保存 Key"


def test_save_and_delete_key_callbacks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app.credentials, "save_key", lambda provider, key: calls.append(("save", provider, key))
    )
    monkeypatch.setattr(
        app.credentials, "delete_key", lambda provider: calls.append(("delete", provider))
    )
    assert app.on_save_key("openai", "secret") == ("✅ Key 已安全保存", "")
    assert app.on_delete_key("openai") == ("🗑️ 已删除保存的 Key", "")
    assert calls == [("save", "openai", "secret"), ("delete", "openai")]


def test_generate_passes_provider_settings_and_returns_status(monkeypatch):
    captured = {}

    def fake_make_song(*args, **kwargs):
        captured.update(kwargs)
        return {
            "song": "song.wav", "structured_lyrics": "[Verse]\n词",
            "llm_status": ["歌曲规划：模型调用成功", "歌词整理：模型调用成功"],
        }

    monkeypatch.setattr(app, "make_song", fake_make_song)
    result = app.on_generate(
        "词", "温柔", "短版 Demo", "7", "qwen", "qwen-flash", "temporary"
    )
    assert captured["llm_options"] == {
        "provider": "qwen", "model": "qwen-flash", "api_key": "temporary"
    }
    assert result[0] == "song.wav"
    assert "模型调用成功" in result[2]


def test_api_key_component_is_password_field():
    assert app.api_key_in.type == "password"

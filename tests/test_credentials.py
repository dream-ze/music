import pytest

from src import credentials


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_saved_key_round_trip(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(credentials, "_keyring", fake)
    credentials.save_key("deepseek", "secret")
    assert credentials.get_saved_key("deepseek") == "secret"
    assert credentials.has_saved_key("deepseek") is True
    credentials.delete_key("deepseek")
    assert credentials.get_saved_key("deepseek") is None


def test_resolve_key_priority(monkeypatch):
    fake = FakeKeyring()
    fake.set_password(credentials.SERVICE_NAME, "deepseek", "saved")
    monkeypatch.setattr(credentials, "_keyring", fake)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment")
    assert credentials.resolve_key("deepseek", "temporary") == "temporary"
    assert credentials.resolve_key("deepseek") == "saved"
    fake.values.clear()
    assert credentials.resolve_key("deepseek") == "environment"


def test_save_rejects_empty_key():
    with pytest.raises(ValueError, match="不能为空"):
        credentials.save_key("deepseek", "  ")

import pytest
from fastapi import HTTPException
from server import auth


def test_passcode_ok(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "sesame")
    assert auth.require_passcode("sesame") == "sesame"


def test_passcode_wrong(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "sesame")
    with pytest.raises(HTTPException) as ei:
        auth.require_passcode("nope")
    assert ei.value.status_code == 401


def test_passcode_disabled_when_empty(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "")
    assert auth.require_passcode("") == "anonymous"

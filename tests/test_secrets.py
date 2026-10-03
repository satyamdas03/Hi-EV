"""Tests for the Hi-EV encrypted secrets store."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ev.secrets import EncryptedSecretStore, SecretsError


def test_store_set_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_MASTER_PASSWORD", "test-password")
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "vault.json"))
    store = EncryptedSecretStore()
    store.set("ANTHROPIC_API_KEY", "sk-test")
    assert store.get("ANTHROPIC_API_KEY") == "sk-test"


def test_store_list_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_MASTER_PASSWORD", "test-password")
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "vault.json"))
    store = EncryptedSecretStore()
    store.set("A", "1")
    store.set("B", "2")
    assert store.list() == ["A", "B"]
    assert store.delete("A") is True
    assert store.delete("A") is False
    assert store.list() == ["B"]


def test_store_load_into_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_MASTER_PASSWORD", "test-password")
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "vault.json"))
    store = EncryptedSecretStore()
    store.set("ANTHROPIC_API_KEY", "sk-live")
    store.load_into_env()
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-live"


def test_store_missing_secret_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_MASTER_PASSWORD", "test-password")
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "vault.json"))
    store = EncryptedSecretStore()
    with pytest.raises(SecretsError, match="Secret 'MISSING' not found"):
        store.get("MISSING")


def test_store_no_key_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("EV_MASTER_PASSWORD", raising=False)
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "vault.json"))
    store = EncryptedSecretStore()
    with pytest.raises(SecretsError, match="No vault key available"):
        store.set("X", "y")


def test_store_exists_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EV_VAULT_PATH", str(tmp_path / "no_vault.json"))
    store = EncryptedSecretStore()
    assert store.exists() is False

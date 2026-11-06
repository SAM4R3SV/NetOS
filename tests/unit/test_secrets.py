import os
import stat
from pathlib import Path

import pytest

from netos.security.secrets.manager import (
    SecretManager,
    SecretNameError,
    SecretNotFoundError,
    SecretStoreError,
    SecretStoreUnavailableError,
    mask_secret,
)


def test_secret_lifecycle_and_persistence(tmp_path):
    directory = tmp_path / "secrets"
    manager = SecretManager(directory)

    manager.set_secret("telegram.bot_token", "test-token-value")
    assert manager.secret_exists("telegram.bot_token")
    assert manager.get_secret("telegram.bot_token") == "test-token-value"
    assert manager.list_secret_names() == ["telegram.bot_token"]

    manager.set_secret("telegram.bot_token", "rotated-token")
    assert SecretManager(directory).get_secret("telegram.bot_token") == "rotated-token"
    manager.delete_secret("telegram.bot_token")
    assert not manager.secret_exists("telegram.bot_token")


def test_secret_names_and_empty_values_are_rejected(tmp_path):
    manager = SecretManager(tmp_path / "secrets")
    with pytest.raises(SecretNameError):
        manager.set_secret("../escape", "value")
    with pytest.raises(SecretNameError):
        manager.set_secret("", "value")
    with pytest.raises(ValueError):
        manager.set_secret("valid", "")
    with pytest.raises(ValueError):
        manager.set_secret("valid", "bad\x00value")


def test_missing_and_corrupt_secrets_are_explicit_without_value_in_error(tmp_path):
    manager = SecretManager(tmp_path / "secrets")
    with pytest.raises(SecretNotFoundError):
        manager.get_secret("missing")
    manager.initialize()
    (tmp_path / "secrets" / "corrupt").write_text("", encoding="utf-8")
    if os.name == "posix":
        (tmp_path / "secrets" / "corrupt").chmod(0o600)
    with pytest.raises(SecretStoreUnavailableError) as error:
        manager.get_secret("corrupt")
    assert "test-token" not in str(error.value)


def test_directories_are_isolated_and_names_never_contain_values(tmp_path):
    first = SecretManager(tmp_path / "first")
    second = SecretManager(tmp_path / "second")
    first.set_secret("provider.url", "test-webhook-value")

    assert second.list_secret_names() == []
    assert first.list_secret_names() == ["provider.url"]
    assert "test-webhook-value" not in repr(first.list_secret_names())


def test_mask_is_presentation_only():
    assert mask_secret("123456789", 3, 3) == "123•••789"
    assert mask_secret("abc", 3, 3) == "•••"


def test_failed_atomic_write_leaves_no_temporary_secret(tmp_path, monkeypatch):
    manager = SecretManager(tmp_path / "secrets")
    original_replace = os.replace

    def fail_replace(source: str | bytes | Path, destination: str | bytes | Path):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(SecretStoreUnavailableError):
        manager.set_secret("provider.token", "test-value")
    monkeypatch.setattr(os, "replace", original_replace)
    assert manager.list_secret_names() == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission check only")
def test_insecure_linux_directory_permissions_are_rejected(tmp_path):
    directory = tmp_path / "secrets"
    directory.mkdir(mode=0o755)
    manager = SecretManager(directory)
    with pytest.raises(SecretStoreUnavailableError):
        manager.initialize()


def test_symlink_secret_is_rejected_when_supported(tmp_path):
    manager = SecretManager(tmp_path / "secrets")
    manager.initialize()
    target = tmp_path / "outside"
    target.write_text("outside-value", encoding="utf-8")
    link = tmp_path / "secrets" / "linked"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable in this environment")
    with pytest.raises(SecretStoreError):
        manager.get_secret("linked")


def test_opened_descriptor_is_validated_with_fstat(tmp_path, monkeypatch):
    manager = SecretManager(tmp_path / "secrets")
    manager.set_secret("descriptor", "descriptor-value")
    original_fstat = os.fstat
    calls: list[int] = []

    def recording_fstat(descriptor: int):
        calls.append(descriptor)
        return original_fstat(descriptor)

    monkeypatch.setattr(os, "fstat", recording_fstat)
    assert manager.get_secret("descriptor") == "descriptor-value"
    assert calls
    assert all(isinstance(descriptor, int) for descriptor in calls)


def test_non_regular_secret_is_rejected(tmp_path):
    manager = SecretManager(tmp_path / "secrets")
    manager.initialize()
    directory = tmp_path / "secrets" / "directory"
    directory.mkdir()
    with pytest.raises(SecretStoreError):
        manager.get_secret("directory")


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor metadata only")
def test_descriptor_permissions_and_ownership_are_validated(tmp_path):
    manager = SecretManager(tmp_path / "secrets")
    manager.set_secret("secure", "secure-value")
    path = tmp_path / "secrets" / "secure"
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    with pytest.raises(SecretStoreUnavailableError):
        manager.get_secret("secure")

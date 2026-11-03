import os
import time

from netos.observability.logging import configure_logging


def test_log_retention_removes_only_expired_rotated_logs(tmp_path):
    old_log = tmp_path / "netos.log.2020-01-01"
    recent_log = tmp_path / "netos.log.2026-01-01"
    unrelated = tmp_path / "other.log"
    for path in (old_log, recent_log, unrelated):
        path.write_text("old", encoding="utf-8")
    old_timestamp = time.time() - 3 * 24 * 60 * 60
    os.utime(old_log, (old_timestamp, old_timestamp))

    configure_logging(tmp_path, "INFO", 1)

    assert not old_log.exists()
    assert recent_log.exists()
    assert unrelated.exists()

import json
from datetime import date

import pytest

from gridflow.store import save_bronze


def test_content_addressed_file_and_idempotent_reload(tmp_path):
    day = date(2024, 1, 1)
    a = save_bronze(tmp_path, "energy_price", day, {"data": [{"price": 1}]}, "https://x")
    b = save_bronze(tmp_path, "energy_price", day, {"data": [{"price": 1}]}, "https://x")
    assert not a.already_exists
    assert b.already_exists
    assert a.sha256 == b.sha256
    assert json.loads(a.content_path.read_text())["data"][0]["price"] == 1
    assert json.loads(a.metadata_path.read_text())["sha256"] == a.sha256


def test_updated_source_version_gets_new_hash(tmp_path):
    day = date(2024, 1, 1)
    old = save_bronze(tmp_path, "weather_hourly", day, {"x": 1}, "https://x")
    new = save_bronze(tmp_path, "weather_hourly", day, {"x": 2}, "https://x")
    assert old.sha256 != new.sha256
    assert old.content_path.is_file()
    assert new.content_path.is_file()


def test_rejects_unknown_source(tmp_path):
    with pytest.raises(ValueError, match="Unsupported source"):
        save_bronze(tmp_path, "../unsafe", date(2024, 1, 1), {}, "https://x")

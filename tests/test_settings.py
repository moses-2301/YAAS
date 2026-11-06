"""User settings live in settings.json; config.py only holds defaults."""
import json
import os
import shutil
import subprocess
import sys

import pytest

import config
import gui
from studio import settings as studio_settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = {"Host": "localhost:7070"}


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", str(path))
    return path


@pytest.fixture
def restore_config():
    """Endpoints change config attributes in memory; put them back afterwards."""
    saved = {k: getattr(config, k) for k in config.USER_SETTINGS}
    yield
    for k, v in saved.items():
        setattr(config, k, v)


# ── load / save ───────────────────────────────────────────────────────────────

def test_missing_file_means_no_overrides(settings_file):
    assert config.load_settings() == {}


def test_unknown_keys_wrong_types_and_secrets_are_ignored(settings_file):
    settings_file.write_text(json.dumps({
        "CHANNEL_NAME": "Mine", "MUSIC_VOLUME": 0.5,
        "MUSIC_ENABLED": "yes",          # wrong type
        "GEMINI_API_KEY": "secret",      # secrets never come from here
        "OUTPUT_DIR": "/tmp/x",          # not a user setting
        "NOPE": 1,
    }))
    assert config.load_settings() == {"CHANNEL_NAME": "Mine", "MUSIC_VOLUME": 0.5}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_broken_file_is_ignored_not_fatal(settings_file, content):
    settings_file.write_text(content)
    assert config.load_settings() == {}


def test_save_keeps_only_values_that_differ_from_defaults(settings_file):
    config.save_settings({"CHANNEL_NAME": "Mine", "VOICE_ID": config.DEFAULTS["VOICE_ID"]})
    config.save_settings({"MUSIC_VOLUME": 0.3})                       # merges
    assert config.load_settings() == {"CHANNEL_NAME": "Mine", "MUSIC_VOLUME": 0.3}
    config.save_settings({"CHANNEL_NAME": config.DEFAULTS["CHANNEL_NAME"]})   # back to default
    assert config.load_settings() == {"MUSIC_VOLUME": 0.3}
    assert not os.path.exists(str(settings_file) + ".tmp")


def test_save_rejects_unknown_or_mistyped_values(settings_file):
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        config.save_settings({"GEMINI_API_KEY": "x"})
    with pytest.raises(ValueError, match="MUSIC_VOLUME"):
        config.save_settings({"MUSIC_VOLUME": "loud"})
    assert not settings_file.exists()


def test_saved_settings_override_defaults_at_import(tmp_path):
    shutil.copy(os.path.join(ROOT, "config.py"), tmp_path / "config.py")
    (tmp_path / "settings.json").write_text(json.dumps(
        {"CHANNEL_NAME": "From JSON", "IMAGE_SOURCES": ["nasa"], "KB_ZOOM_END": 1.2}))
    out = subprocess.run(
        [sys.executable, "-c",
         "import json, config; print(json.dumps([config.CHANNEL_NAME, config.IMAGE_SOURCES,"
         " config.KB_ZOOM_END, config.DEFAULTS['CHANNEL_NAME']]))"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path)})
    assert json.loads(out.stdout) == ["From JSON", ["nasa"], 1.2, "My AI Channel"]


# ── the Settings endpoint ─────────────────────────────────────────────────────

def test_settings_page_writes_settings_json_not_config_py(settings_file, monkeypatch, restore_config):
    monkeypatch.setattr(config, "save_env", lambda values: None)
    cfg = os.path.join(ROOT, "config.py")
    before = open(cfg, encoding="utf-8").read()

    r = gui.app.test_client().post("/api/save-settings", headers=LOCAL, json={
        "channel_name": "Space Facts", "music_volume": "0.25", "show_brand": False,
        "image_sources": "nasa, openverse",
        "channel_desc": '\n  Space videos with """quotes""" and a # hash\n',
    })
    assert r.get_json() == {"ok": True}
    assert open(cfg, encoding="utf-8").read() == before
    saved = config.load_settings()
    assert saved == {
        "CHANNEL_NAME": "Space Facts", "MUSIC_VOLUME": 0.25, "SHOW_CHANNEL_BRAND": False,
        "IMAGE_SOURCES": ["nasa", "openverse"],
        "CHANNEL_DESCRIPTION": 'Space videos with """quotes""" and a # hash',
    }
    assert config.CHANNEL_NAME == "Space Facts"
    got = gui.app.test_client().get("/api/settings", headers=LOCAL).get_json()
    assert got["channel_name"] == "Space Facts" and got["music_volume"] == 0.25


def test_api_keys_still_go_to_env_only(settings_file, monkeypatch, restore_config):
    env = {}
    monkeypatch.setattr(config, "save_env", env.update)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "", raising=False)
    r = gui.app.test_client().post("/api/save-settings", headers=LOCAL,
                                   json={"gemini_key": "AIza-test"})
    assert r.get_json() == {"ok": True}
    assert env == {"GEMINI_API_KEY": "AIza-test"}
    assert not settings_file.exists()


# ── importing an old config.py ────────────────────────────────────────────────

OLD_CONFIG = '''
open("pwned.txt", "w").write("ran")      # must never execute
CHANNEL_NAME = 'Old Channel'
CHANNEL_DESCRIPTION = """
My old description.
"""
MUSIC_VOLUME = 0.2
VOICE_ID = "en-US-AndrewNeural"          # same as the default → not imported
IMAGE_SOURCES = ['nasa', 'pollinations']
OVERLAY_OPACITY = 0.5 + 0.1              # not a plain literal → skipped
GEMINI_API_KEY = "never-imported"
SHOW_CHANNEL_BRAND = "nope"              # wrong type → skipped
'''


def test_import_legacy_config_reads_values_without_running_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = tmp_path / "old_config.py"
    old.write_text(OLD_CONFIG)
    assert config.import_legacy_config(str(old)) == {
        "CHANNEL_NAME": "Old Channel",
        "CHANNEL_DESCRIPTION": "My old description.",
        "MUSIC_VOLUME": 0.2,
        "IMAGE_SOURCES": ["nasa", "pollinations"],
    }
    assert not (tmp_path / "pwned.txt").exists()


def test_import_settings_command(tmp_path, settings_file, capsys):
    old = tmp_path / "old_config.py"
    old.write_text(OLD_CONFIG)
    studio_settings.import_settings(str(old))
    assert config.load_settings()["CHANNEL_NAME"] == "Old Channel"
    assert "Imported 4 setting(s)" in capsys.readouterr().out


# ── multi-channel profiles and niche ──────────────────────────────────────────

def test_multi_channel_profiles_and_niche(settings_file, restore_config):
    client = gui.app.test_client()

    # 1. Check initial profiles
    r = client.get("/api/profiles", headers=LOCAL).get_json()
    assert "active" in r and len(r["profiles"]) >= 1

    # 2. Save settings including channel_niche
    r = client.post("/api/save-settings", headers=LOCAL, json={
        "channel_name": "Finance Mindset",
        "channel_niche": "Finance & Psychology",
        "voice_id": "en-GB-RyanNeural",
    })
    assert r.get_json() == {"ok": True}
    assert config.CHANNEL_NAME == "Finance Mindset"
    assert config.CHANNEL_NICHE == "Finance & Psychology"
    assert config.VOICE_ID == "en-GB-RyanNeural"

    # 3. Create a second profile
    r = client.post("/api/profiles/create", headers=LOCAL, json={
        "name": "Tech Horizons",
        "niche": "Technology & AI",
    })
    res = r.get_json()
    assert res["ok"] is True
    tech_id = res["profile_id"]
    assert config.get_active_profile_id() == tech_id
    assert config.CHANNEL_NAME == "Tech Horizons"
    assert config.CHANNEL_NICHE == "Technology & AI"
    # Notice voice_id resets to default for the new profile
    assert config.VOICE_ID == config.DEFAULTS["VOICE_ID"]

    # 4. Save settings on the second profile
    client.post("/api/save-settings", headers=LOCAL, json={
        "voice_id": "en-US-BrianNeural",
    })
    assert config.VOICE_ID == "en-US-BrianNeural"

    # 5. List profiles
    profs = client.get("/api/profiles", headers=LOCAL).get_json()["profiles"]
    assert len(profs) == 2
    tech_prof = next(p for p in profs if p["id"] == tech_id)
    assert tech_prof["active"] is True
    first_pid = next(p["id"] for p in profs if p["id"] != tech_id)

    # 6. Switch back to the first profile
    r = client.post("/api/profiles/active", headers=LOCAL, json={"profile_id": first_pid})
    assert r.get_json()["ok"] is True
    assert config.get_active_profile_id() == first_pid
    assert config.CHANNEL_NAME == "Finance Mindset"
    assert config.CHANNEL_NICHE == "Finance & Psychology"
    assert config.VOICE_ID == "en-GB-RyanNeural"

    # 7. Delete the second profile
    r = client.post("/api/profiles/delete", headers=LOCAL, json={"profile_id": tech_id})
    assert r.get_json()["ok"] is True
    profs_after = client.get("/api/profiles", headers=LOCAL).get_json()["profiles"]
    assert len(profs_after) == 1
    assert profs_after[0]["id"] == first_pid

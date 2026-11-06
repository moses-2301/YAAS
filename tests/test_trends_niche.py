"""Tests for niche-aware trend filtering and multi-profile saved niches."""
import json
import pytest
import config
from apis import trends
import gui

LOCAL = {"Host": "localhost:7070"}


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", str(path))
    return path


def test_list_saved_niches_empty(settings_file):
    assert config.list_saved_niches() == []


def test_list_saved_niches_multiple_profiles(settings_file):
    settings_file.write_text(json.dumps({
        "active_profile": "channel-1",
        "profiles": {
            "channel-1": {"CHANNEL_NAME": "Tech Channel", "CHANNEL_NICHE": "Technology"},
            "channel-2": {"CHANNEL_NAME": "Finance Channel", "CHANNEL_NICHE": "Finance"},
            "channel-3": {"CHANNEL_NAME": "Duplicate Niche", "CHANNEL_NICHE": "technology"},
            "channel-4": {"CHANNEL_NAME": "Empty Niche", "CHANNEL_NICHE": "  "},
        },
        "global": {}
    }))
    niches = config.list_saved_niches()
    assert niches == ["Technology", "Finance"]


def test_matches_niche_all_or_empty():
    item = {"title": "Arbitrary Headline", "detail": "Some detail", "k": "google"}
    assert trends.matches_niche(item, "") is True
    assert trends.matches_niche(item, "all") is True
    assert trends.matches_niche(item, "All") is True
    assert trends.matches_niche(item, "general (no niche)") is True


def test_matches_niche_source_affinity():
    space_item = {"title": "Rocket launch scheduled", "detail": "Cape Canaveral", "k": "spaceflight"}
    tech_item = {"title": "Compiler optimization tricks", "detail": "Low level assembly", "k": "hackernews"}
    paper_item = {"title": "Non-Abelian Topology", "detail": "Lattice gauge models", "k": "arxiv"}

    assert trends.matches_niche(space_item, "Space") is True
    assert trends.matches_niche(tech_item, "Technology") is True
    assert trends.matches_niche(paper_item, "Science") is True


def test_matches_niche_avoids_false_positives():
    # 'general' should not match 'gene', 'start' should not match 'star'
    political_item = {
        "title": "United States midterm election",
        "detail": "General elections in the United States starting soon",
        "k": "wikipedia"
    }
    assert trends.matches_niche(political_item, "Science") is False
    assert trends.matches_niche(political_item, "Space") is False


def test_filter_trends_by_niche():
    sources = {
        "spaceflight": {
            "ok": True,
            "items": [
                {"title": "Starship orbital flight test", "detail": "Super Heavy booster"},
                {"title": "Mars Rover sample collection", "detail": "Jezero crater exploration"},
            ]
        },
        "hackernews": {
            "ok": True,
            "items": [
                {"title": "Python 3.14 features", "detail": "Faster interpreter and JIT"},
                {"title": "Fed announces interest rate cut", "detail": "Central bank monetary policy"},
            ]
        }
    }

    space_results = trends.filter_trends_by_niche(sources, "Space")
    assert len(space_results) == 2
    assert all(it["k"] == "spaceflight" for it in space_results)

    tech_results = trends.filter_trends_by_niche(sources, "Technology")
    assert any("Python" in it["title"] for it in tech_results)

    finance_results = trends.filter_trends_by_niche(sources, "Finance")
    assert any("interest rate" in it["title"] for it in finance_results)

    all_results = trends.filter_trends_by_niche(sources, "all")
    assert len(all_results) == 4


def test_headlines_with_niche(monkeypatch):
    mock_trends = {
        "sources": {
            "hackernews": {
                "ok": True,
                "items": [
                    {"title": "New AI model released", "detail": "State of the art transformer"},
                ]
            },
            "spaceflight": {
                "ok": True,
                "items": [
                    {"title": "Artemis Moon Mission launch", "detail": "NASA Orion spacecraft"},
                ]
            }
        },
        "fetched_at": 1000
    }
    monkeypatch.setattr(trends, "get_trends", lambda: mock_trends)

    space_hl = trends.headlines(limit=10, niche="Space")
    assert "Artemis Moon Mission launch" in space_hl

    ai_hl = trends.headlines(limit=10, niche="Technology")
    assert "New AI model released" in ai_hl


def test_dashboard_trends_api_includes_niches(settings_file, monkeypatch):
    settings_file.write_text(json.dumps({
        "active_profile": "channel-1",
        "profiles": {
            "channel-1": {"CHANNEL_NAME": "Channel One", "CHANNEL_NICHE": "Finance"},
            "channel-2": {"CHANNEL_NAME": "Channel Two", "CHANNEL_NICHE": "Science"},
        },
        "global": {}
    }))

    mock_trends = {
        "sources": {
            "spaceflight": {
                "ok": True,
                "items": [{"title": "NASA updates mission", "detail": "Space probe"}]
            }
        },
        "fetched_at": 1000
    }
    monkeypatch.setattr(trends, "get_trends", lambda: mock_trends)

    app = gui.create_app()
    with app.test_client() as c:
        res = c.get("/api/trends", headers=LOCAL)
        assert res.status_code == 200
        data = res.get_json()
        assert "niches" in data
        assert "Finance" in data["niches"]
        assert "Science" in data["niches"]

        # Test with niche query param
        res_filtered = c.get("/api/trends?niche=Space", headers=LOCAL)
        data_filtered = res_filtered.get_json()
        assert "filtered" in data_filtered
        assert len(data_filtered["filtered"]) == 1


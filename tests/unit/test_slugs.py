"""Pure tests for public run slugs (no DB).

Public run_id is a human-readable slug; UUID stays the row primary key.
"""

from app.services.slugs import parse_uuid, slug_from_repo, slugify, unique_slug


def test_slug_from_github_https_url():
    assert (
        slug_from_repo("https://github.com/vallaksa/journalApplication.git")
        == "vallaksa-journalapplication"
    )


def test_slug_from_git_ssh_url():
    assert (
        slug_from_repo("git@github.com:vallaksa/journalApplication.git")
        == "vallaksa-journalapplication"
    )


def test_slug_from_local_path():
    assert slug_from_repo(None, "/home/me/projects/journalApplication") == "journalapplication"


def test_slugify_intent():
    assert slugify("A journal app with Spring Boot") == "a-journal-app-with-spring-boot"


def test_slugify_empty_falls_back_to_run():
    assert slugify("") == "run"
    assert slugify(None) == "run"


def test_unique_slug_returns_base_when_free():
    assert unique_slug("vallaksa-journalapplication", set()) == "vallaksa-journalapplication"


def test_unique_slug_appends_number_on_collision():
    taken = {"vallaksa-journalapplication", "vallaksa-journalapplication-2"}
    assert unique_slug("vallaksa-journalapplication", taken) == "vallaksa-journalapplication-3"


def test_parse_uuid_accepts_uuid_and_rejects_slug():
    assert parse_uuid("3f1aecd4-ae82-418a-aaee-d92a4617e3c0") is not None
    assert parse_uuid("vallaksa-journalapplication") is None

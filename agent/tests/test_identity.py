from agent.identity import load_or_create_identity


def test_creates_identity_on_first_load(tmp_path):
    path = tmp_path / "identity.json"
    identity = load_or_create_identity(path)

    assert identity["installation_id"]
    assert identity["metadata"]["hostname"]
    assert path.is_file()


def test_reload_keeps_same_installation_id(tmp_path):
    path = tmp_path / "identity.json"
    first = load_or_create_identity(path)
    second = load_or_create_identity(path)

    assert second["installation_id"] == first["installation_id"]

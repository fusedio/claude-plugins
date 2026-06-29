"""Storage-location + keychain-service resolution tests for secrets-management.

Covers: ``secrets_file`` param > OPENFUSED_SECRETS_FILE > default for the store
path, and ``service`` param > OPENFUSED_KEYRING_SERVICE > "openfused" for the
keychain namespace (two services isolate the same name).
"""


def test_secrets_file_param_honored(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_SECRETS_FILE", raising=False)
    store_a = str(tmp_path / "a.json")
    store_b = str(tmp_path / "b.json")
    load_udf("put", "put")(name="k", value="v", secrets_file=store_a)
    assert load_udf("get", "get")(name="k", secrets_file=store_a) == {"name": "k", "value": "v"}
    # a different store path does not see the secret
    assert load_udf("get", "get")(name="k", secrets_file=store_b).get("ok") is False


def test_env_fallback_when_param_omitted(load_udf, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENFUSED_SECRETS_FILE", str(tmp_path / "env.json"))
    load_udf("put", "put")(name="k", value="v")
    assert load_udf("get", "get")(name="k") == {"name": "k", "value": "v"}


def test_secrets_file_param_overrides_env(load_udf, tmp_path, monkeypatch):
    env_store = str(tmp_path / "env.json")
    param_store = str(tmp_path / "param.json")
    monkeypatch.setenv("OPENFUSED_SECRETS_FILE", env_store)
    # both env and param set on the same call → param wins
    load_udf("put", "put")(name="k", value="v", secrets_file=param_store)
    # verify with explicit params (a fresh process per call in production; here the
    # prelude mutates os.environ, so check both stores explicitly rather than relying
    # on env state across calls)
    assert load_udf("get", "get")(name="k", secrets_file=param_store) == {"name": "k", "value": "v"}
    assert load_udf("get", "get")(name="k", secrets_file=env_store).get("ok") is False


def test_service_namespace_isolates_secrets(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_KEYRING_SERVICE", raising=False)
    store = str(tmp_path / "s.json")
    load_udf("put", "put")(name="k", value="v", service="a", secrets_file=store)
    # same name + store, different service → not visible
    assert load_udf("get", "get")(name="k", service="b", secrets_file=store).get("ok") is False
    assert load_udf("get", "get")(name="k", service="a", secrets_file=store) == {"name": "k", "value": "v"}


def test_default_service_when_omitted(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_KEYRING_SERVICE", raising=False)
    store = str(tmp_path / "s.json")
    # written under the default service "openfused" → readable via explicit service="openfused"
    load_udf("put", "put")(name="k", value="v", secrets_file=store)
    assert load_udf("get", "get")(name="k", service="openfused", secrets_file=store) == {
        "name": "k",
        "value": "v",
    }

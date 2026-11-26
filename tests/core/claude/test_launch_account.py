"""Launching the CLI with another account of Claude: its token, and nothing of another server."""

import pytest

from wxclaude.core.claude.launch import (
    ACCOUNT_TOKEN_VARIABLE,
    KEY_VARIABLE,
    SCRUB_VARIABLE,
    launch_for,
    provider_environment,
    provider_settings,
    sends_effort,
)
from wxclaude.core.config.agents import MODELS
from wxclaude.core.config.key_transmission import RELAYED
from wxclaude.core.config.providers import (
    ENGINE_ACCOUNT,
    KEY_NONE,
    Provider,
    ProviderStore,
)
from wxclaude.core.security.key_relay import KeyRelay

pytestmark = pytest.mark.unit

TOKEN = "sk-ant-oat01-secret"


class PlainVault:
    def encrypt(self, secret: str) -> str:
        return "enc:" + secret

    def decrypt(self, blob: str) -> str:
        return blob.removeprefix("enc:")


def account(**changes: object) -> Provider:
    made = Provider(id="compte-2", name="Compte 2", engine=ENGINE_ACCOUNT)
    for name, value in changes.items():
        setattr(made, name, value)
    return made


def store_with_account() -> ProviderStore:
    store = ProviderStore(PlainVault())
    store.add(account())
    store.set_key("compte-2", TOKEN)
    return store


def test_an_account_is_claude_with_its_own_sign_in() -> None:
    provider = account()
    assert provider.is_account
    assert provider.problem() is None  # no address, no models to type
    assert provider.models == list(MODELS)
    assert provider.aliases == {}
    assert provider.needs_key
    assert not provider.loads_models
    assert not provider.uses_sdk
    assert account(key_source=KEY_NONE).problem() is not None
    assert account(loading_method="lmstudio").loads_models is False


def test_the_token_goes_to_the_environment_and_nothing_else_changes() -> None:
    launch = launch_for("compte-2", store_with_account())
    assert launch is not None
    inherited = {"ANTHROPIC_BASE_URL": "http://localhost:1234", "PATH": "x"}
    env = provider_environment(launch, inherited)
    assert env is not None
    assert env[ACCOUNT_TOKEN_VARIABLE] == TOKEN
    assert KEY_VARIABLE not in env
    assert "ANTHROPIC_BASE_URL" not in env  # never a local server inherited from WxClaude
    assert SCRUB_VARIABLE not in env  # the CLI would force the manual mode
    assert not launch.scrub
    assert "DISABLE_TELEMETRY" not in env  # it is Claude
    settings = provider_settings(launch, "sonnet")
    assert settings == {"env": {}}
    assert sends_effort(launch)


def test_the_variables_of_an_account_still_apply() -> None:
    store = ProviderStore(PlainVault())
    store.add(account(env={"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000"}))
    store.set_key("compte-2", TOKEN)
    settings = provider_settings(launch_for("compte-2", store), "sonnet")
    assert settings == {"env": {"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000"}}


def test_an_account_is_never_relayed() -> None:
    relay = KeyRelay()
    try:
        launch = launch_for("compte-2", store_with_account(), transmission=RELAYED, relay=relay)
        assert launch is not None
        assert launch.relay is None
        assert launch.key == TOKEN
    finally:
        relay.stop()

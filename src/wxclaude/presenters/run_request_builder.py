"""What a message is sent with: the request given to the runner (the workspace, the conversation,
the provider and its key, the trust of the folder, the limit of turns) and the permission mode the
CLI is given. Taken out of ``RunPresenter``, which owns it. Nothing here touches wx."""

from typing import TYPE_CHECKING

from wxclaude.core.claude.launch import launch_for
from wxclaude.core.claude.runner import RunRequest
from wxclaude.core.config.agents import Agent
from wxclaude.core.security.restricted import restricted_permission_mode
from wxclaude.presenters.shared import Shared

if TYPE_CHECKING:
    from wxclaude.presenters.run_presenter import RunLinks


class RunRequestBuilder:
    """Builds the request of a message from the shared state and the links of the window."""

    def __init__(self, shared: Shared, links: RunLinks) -> None:
        self._settings = shared.settings
        self._files = shared.files
        self._security = shared.security
        self._providers = shared.providers
        self._relay = shared.relay
        self._links = links

    @property
    def restricted(self) -> bool:
        """Is the folder not trusted? The CLI is then launched so that it ignores the project."""
        return self._security is not None and self._security.restricted

    @property
    def _max_turns(self) -> int:
        """The limit of turns of the workspace (0: none)."""
        state = None if self._security is None else self._security.state
        return 0 if state is None else state.max_turns

    def build(self, text: str, agent: Agent) -> RunRequest | None:
        """The request to send ``text`` with ``agent``; None when no workspace is open. Raises
        ``ProviderError`` or ``KeyVaultError`` when the provider of the agent cannot be used."""
        workspace = self._links.workspace()
        if workspace is None:
            return None
        conversation_id = self._links.conversation_id()
        provider = launch_for(
            agent.provider,
            self._providers,
            transmission=self._settings.key_transmission,
            relay=self._relay,
        )
        return RunRequest(
            text,
            agent,
            conversation_id,
            self._files.find_session(conversation_id) is not None,
            workspace,
            self._links.conversation_name(),  # given to the CLI by the first message only
            self._links.fork_from(),  # a branch: its first message copies that history
            restricted=self.restricted,
            provider=provider,
            max_turns=self._max_turns,
        )

    def mode_sent(self, agent: Agent) -> str:
        """The permission mode the CLI is given for ``agent``: a folder that is not trusted
        keeps only the strict modes, the others become manual (``RunRequest.restricted``)."""
        mode = agent.permission_mode or ""
        return restricted_permission_mode(mode) if self.restricted else mode

"""Runtime configuration for the Streamlit application."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppCredentials:
    """Credentials and optional tracing configuration for one app session."""

    openai_api_key: str
    langsmith_api_key: str
    langsmith_enabled: bool = False

    @property
    def is_complete(self) -> bool:
        """Return whether required credentials for the selected features exist."""
        return bool(self.openai_api_key.strip()) and (
            not self.langsmith_enabled or bool(self.langsmith_api_key.strip())
        )
"""Application-level errors that presentation can handle consistently."""


class ProjectNotFoundError(LookupError):
    """Raised when a requested project does not exist."""


class EntryNotFoundError(LookupError):
    """Raised when a requested translation entry does not exist."""


class ModelUnavailableError(ConnectionError):
    """Raised when a local model backend cannot be reached."""


class ModelTimeoutError(TimeoutError):
    """Raised when a model backend does not respond before the configured timeout."""


class InvalidModelResponseError(ValueError):
    """Raised when a model response does not match the translation contract."""


class PlaceholderMismatchError(ValueError):
    """Raised when a translated string does not preserve protected placeholders."""


class NoOpenProjectError(RuntimeError):
    """Raised when a project operation requires an active project session."""

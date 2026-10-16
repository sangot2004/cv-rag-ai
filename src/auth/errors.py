class AccessDenied(PermissionError):
    """Base class retained for Streamlit and existing callers."""


class AuthenticationRequired(AccessDenied):
    pass


class Forbidden(AccessDenied):
    pass


class ConversationNotFound(AccessDenied):
    pass

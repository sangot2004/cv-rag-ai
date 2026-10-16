class ChatConflict(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class CleanupPending(RuntimeError):
    pass


class MessageNotFound(LookupError):
    pass


class DependencyUnavailable(RuntimeError):
    pass

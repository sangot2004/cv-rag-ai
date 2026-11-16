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


class AttachmentError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status

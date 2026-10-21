class InvitationConflict(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class InvitationNotFound(LookupError):
    pass

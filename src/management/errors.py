class ManagementError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.status = code, status
        super().__init__(message)

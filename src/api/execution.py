from src.auth.service import auth_scope


def execute(token, response, fn, *args, **kwargs):
    with auth_scope(token):
        result = fn(*args, **kwargs)
    response.headers["Cache-Control"] = "private, no-store"
    return result

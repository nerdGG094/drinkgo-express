from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def role_required(*roles):
    roles_normalizados = [r.lower() for r in roles]

    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            user_role = (current_user.role or "").strip().lower()

            if user_role not in roles_normalizados:
                abort(403)

            return f(*args, **kwargs)
        return wrapper
    return decorator

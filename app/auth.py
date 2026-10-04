"""Single-user authentication with expiring, signed browser sessions."""
import hashlib
import hmac
import os
import secrets
import time

COOKIE = 'forgetfulme_session'
TTL = 8 * 60 * 60


def credentials_valid(username, password):
    user_ok = secrets.compare_digest(username.encode(), os.environ['ADMIN_USER'].encode())
    password_ok = secrets.compare_digest(password.encode(), os.environ['ADMIN_PASSWORD'].encode())
    return user_ok and password_ok


def signature(value):
    key = (os.environ['ADMIN_USER'] + '\0' + os.environ['ADMIN_PASSWORD']).encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def issue_session():
    payload = f'{int(time.time()) + TTL}.{secrets.token_hex(16)}'
    return f'{payload}.{signature(payload)}'


def session_valid(token):
    if not token or len(token) > 256:
        return False
    try:
        expires, nonce, signed = token.split('.')
        payload = f'{expires}.{nonce}'
        return int(time.time()) < int(expires) <= int(time.time()) + TTL and secrets.compare_digest(signed, signature(payload))
    except (ValueError, TypeError):
        return False

"""Signed access tokens with persisted session revocation and explicit clocks."""
import os
from pathlib import Path
import secrets

import jwt


def init_jwt(app):
    secret = app.config.get('JWT_SECRET') or os.environ.get('AEGIS_JWT_SECRET')
    if not secret:
        # Local deployments share a persistent key across workers/restarts.
        # Production deployments should provision AEGIS_JWT_SECRET explicitly.
        path = Path(app.config.get('JWT_KEY_PATH') or
                    Path(app.config['UPLOAD_DIR']).parent / 'jwt-signing.key')
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temporary = path.with_name(path.name + '.' + secrets.token_hex(16) + '.key')
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='ascii') as stream:
                    stream.write(secrets.token_urlsafe(48))
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    # Publish a fully written key without replacing another worker's key.
                    os.link(temporary, path)
                except FileExistsError:
                    pass
            finally:
                temporary.unlink(missing_ok=True)
        secret = path.read_text(encoding='ascii').strip()
    if not isinstance(secret, (str, bytes)) or len(secret) < 32:
        raise ValueError('JWT signing key must contain at least 32 bytes/characters')
    app.config['JWT_SECRET'] = secret
    app.config.setdefault('JWT_ISSUER', 'aegis-backend')
    app.config.setdefault('JWT_AUDIENCE', 'aegis-api')


def issue_token(config, user_id, now, expires_at):
    return jwt.encode(dict(sub=user_id, iat=now, nbf=now, exp=expires_at,
                           jti=secrets.token_urlsafe(24),
                           iss=config['JWT_ISSUER'], aud=config['JWT_AUDIENCE']),
                      config['JWT_SECRET'], algorithm='HS256')


def validate_token(config, token, now):
    # Signature/algorithm/issuer/audience are verified by PyJWT. Dates use the
    # same clock as the session repository (also supports deterministic tests).
    claims = jwt.decode(token, config['JWT_SECRET'], algorithms=['HS256'],
                        issuer=config['JWT_ISSUER'], audience=config['JWT_AUDIENCE'],
                        options=dict(require=['sub', 'iat', 'nbf', 'exp', 'jti', 'iss', 'aud'],
                                     verify_exp=False, verify_iat=False, verify_nbf=False))
    if any(type(claims[name]) is not int for name in ('iat', 'nbf', 'exp')):
        raise jwt.InvalidTokenError('Invalid token dates')
    if (claims['iat'] > now or claims['nbf'] > now or claims['exp'] <= now
            or claims['exp'] <= claims['iat'] or claims['nbf'] != claims['iat']
            or not isinstance(claims['sub'], str) or not claims['sub']
            or not isinstance(claims['jti'], str) or not claims['jti']):
        raise jwt.InvalidTokenError('Invalid token claims')
    return claims

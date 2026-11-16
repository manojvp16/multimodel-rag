"""Optional local access control; required for production deployments."""
from secrets import compare_digest

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic

from omnirag.config import settings

basic_auth = HTTPBasic(auto_error=False)


def validate_deployment_settings():
    if bool(settings.AUTH_USERNAME) != bool(settings.AUTH_PASSWORD):
        raise RuntimeError('Set both AUTH_USERNAME and AUTH_PASSWORD, or neither for local development.')
    if not settings.DEBUG:
        if not settings.AUTH_USERNAME or not settings.AUTH_PASSWORD:
            raise RuntimeError('Production requires AUTH_USERNAME and AUTH_PASSWORD.')
        if len(settings.AUTH_PASSWORD) < 16:
            raise RuntimeError('Production AUTH_PASSWORD must contain at least 16 characters.')
        if settings.AUTH_PASSWORD.startswith('replace_with'):
            raise RuntimeError('Replace the example AUTH_PASSWORD before deploying.')
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == 'your_api_key_here':
            raise RuntimeError('Production requires a real GEMINI_API_KEY.')


async def require_access(request, call_next):
    if request.url.path == '/health' and request.method in {'GET', 'HEAD'}:
        return await call_next(request)
    if not settings.AUTH_USERNAME and not settings.AUTH_PASSWORD and settings.DEBUG:
        return await call_next(request)
    try:
        credentials = await basic_auth(request)
    except HTTPException:
        credentials = None
    username = credentials.username if credentials else ''
    password = credentials.password if credentials else ''
    username_valid = compare_digest(username.encode('utf-8'), settings.AUTH_USERNAME.encode('utf-8'))
    password_valid = compare_digest(password.encode('utf-8'), settings.AUTH_PASSWORD.encode('utf-8'))
    if credentials is None or not settings.AUTH_USERNAME or not settings.AUTH_PASSWORD or not (username_valid and password_valid):
        return JSONResponse(status_code=401, content={'detail': 'Sign in to access this document workspace.'},
                            headers={'WWW-Authenticate': 'Basic realm="OmniRAG", charset="UTF-8"', 'Cache-Control': 'no-store'})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response

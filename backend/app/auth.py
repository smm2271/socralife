import hashlib, secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import httpx, jwt
from fastapi import Request, Response
from sqlalchemy import select, delete
from .models import User, Login, OAuthState, now
from .domain import Problem

def hash_token(token): return hashlib.sha256(token.encode()).hexdigest()
def expires(): return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
def establish(db, user, response, settings):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(Login(token=hash_token(token), user_id=user.id, csrf=csrf, expires=expires()))
    response.set_cookie("socralife_session", token, httponly=True, secure=settings.environment == "production", samesite="lax", max_age=604800, path="/")
    return {"id": user.id, "email": user.email, "name": user.name, "csrf_token": csrf, "ai_mode": settings.ai_provider}

def authenticate(request, db):
    login = db.get(Login, hash_token(request.cookies.get("socralife_session", "")))
    user = db.get(User, login.user_id) if login else None
    if not login or login.expires < now() or not user or user.disabled: raise Problem(401, "UNAUTHENTICATED", "請先登入")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        token = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(token, login.csrf): raise Problem(403, "CSRF_FAILED", "請重新載入頁面")
    return user, login

def google_start(db, response, settings):
    if not settings.google_client_id: raise Problem(503, "AUTH_NOT_CONFIGURED", "Google 登入尚未設定")
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(OAuthState(state=hash_token(state), nonce=nonce, expires=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()))
    response.set_cookie("socralife_oauth", state, httponly=True, secure=settings.environment == "production", samesite="lax", max_age=600)
    uri = settings.google_redirect_uri or settings.public_url.rstrip("/") + "/api/v1/auth/google/callback"
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(dict(client_id=settings.google_client_id, redirect_uri=uri, response_type="code", scope="openid email profile", state=state, nonce=nonce))

async def google_finish(request, db, settings):
    state = request.query_params.get("state", "")
    if not state or not secrets.compare_digest(state, request.cookies.get("socralife_oauth", "")): raise Problem(400, "OAUTH_STATE", "登入驗證失敗")
    item = db.get(OAuthState, hash_token(state), with_for_update=True)
    if not item or item.expires < now(): raise Problem(400, "OAUTH_STATE", "登入已逾時")
    nonce = item.nonce; db.delete(item); db.commit()
    uri = settings.google_redirect_uri or settings.public_url.rstrip("/") + "/api/v1/auth/google/callback"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await client.post("https://oauth2.googleapis.com/token", data=dict(code=request.query_params.get("code", ""), client_id=settings.google_client_id, client_secret=settings.google_client_secret, redirect_uri=uri, grant_type="authorization_code"))
            token.raise_for_status()
            raw = token.json()["id_token"]
            keys = await client.get("https://www.googleapis.com/oauth2/v3/certs"); keys.raise_for_status()
        header = jwt.get_unverified_header(raw)
        key_data = next(k for k in keys.json()["keys"] if k["kid"] == header["kid"])
        claims = jwt.decode(raw, jwt.PyJWK.from_dict(key_data).key, algorithms=["RS256"], audience=settings.google_client_id, options={"require": ["exp", "iat", "sub", "iss", "aud", "nonce"]})
        if claims["iss"] not in ("https://accounts.google.com", "accounts.google.com") or not secrets.compare_digest(claims["nonce"], nonce) or not claims.get("email_verified"): raise ValueError("claims")
    except Exception: raise Problem(401, "OAUTH_FAILED", "Google 身分驗證失敗")
    user = db.scalar(select(User).where(User.google_sub == claims["sub"]))
    if not user:
        user = User(google_sub=claims["sub"], email=claims["email"], name=claims.get("name", "")); db.add(user); db.flush()
    if user.disabled: raise Problem(401, "ACCOUNT_DISABLED", "帳號已停用")
    return user

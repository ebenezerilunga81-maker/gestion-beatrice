import os
import logging
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from supabase import create_client
from supabase.lib.client_options import ClientOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gestion-beatrice")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://gestion-beatrice-officielle.onrender.com").strip()

app = FastAPI(title="GESTION BÉATRICE API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def public_client():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Authentification non configurée sur le serveur.")
    return create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def admin_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Gestion administrative non configurée sur le serveur.")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class CreateUserInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    role: str = Field(pattern="^(PREFET|CAISSIER)$")


class UpdateUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    role: Optional[str] = Field(default=None, pattern="^(PREFET|CAISSIER)$")
    is_active: Optional[bool] = None


def get_bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Session requise.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Jeton de session absent.")
    return token


def current_profile(token: str = Depends(get_bearer_token)):
    try:
        client = public_client()
        auth_result = client.auth.get_user(token)
        user = auth_result.user
        if user is None:
            raise HTTPException(status_code=401, detail="Session invalide.")
        result = admin_client().table("profiles").select(
            "id,auth_user_id,full_name,username,role,is_active"
        ).eq("auth_user_id", str(user.id)).maybe_single().execute()
        profile = result.data
        if not profile or not profile.get("is_active"):
            raise HTTPException(status_code=403, detail="Compte absent ou désactivé. Contactez l'administrateur.")
        return {"user": user, "profile": profile, "token": token}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de validation de session")
        raise HTTPException(status_code=401, detail="Session invalide ou expirée.")


def require_admin(context=Depends(current_profile)):
    if context["profile"]["role"] != "ADMINISTRATEUR":
        raise HTTPException(status_code=403, detail="Action réservée à l'administrateur.")
    return context


def audit(action: str, actor_profile_id: str, record_id: str, old_data=None, new_data=None):
    admin_client().table("audit_logs").insert({
        "actor_profile_id": actor_profile_id,
        "action": action,
        "table_name": "profiles",
        "record_id": str(record_id),
        "old_data": old_data,
        "new_data": new_data,
    }).execute()


@app.get("/")
def root():
    return {"name": "GESTION BÉATRICE API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "gestion-beatrice-api",
        "supabase_url_configured": bool(SUPABASE_URL),
        "public_auth_configured": bool(SUPABASE_ANON_KEY),
        "admin_key_configured": bool(SUPABASE_SERVICE_ROLE_KEY),
    }


@app.post("/api/auth/login")
def login(payload: LoginInput):
    try:
        response = public_client().auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password,
        })
        if not response.user or not response.session:
            raise HTTPException(status_code=401, detail="Identifiants incorrects.")
        profile_result = admin_client().table("profiles").select(
            "id,full_name,role,is_active"
        ).eq("auth_user_id", str(response.user.id)).maybe_single().execute()
        profile = profile_result.data
        if not profile or not profile.get("is_active"):
            try:
                public_client().auth.sign_out()
            except Exception:
                pass
            raise HTTPException(status_code=403, detail="Compte non activé dans GESTION BÉATRICE.")
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "expires_in": response.session.expires_in,
            "user": {
                "id": str(response.user.id),
                "full_name": profile["full_name"],
                "role": profile["role"],
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.warning("Échec de connexion", exc_info=True)
        raise HTTPException(status_code=401, detail="Connexion refusée. Vérifiez vos identifiants.")


@app.get("/api/me")
def me(context=Depends(current_profile)):
    profile = context["profile"]
    return {
        "id": profile["id"],
        "auth_user_id": profile["auth_user_id"],
        "full_name": profile["full_name"],
        "username": profile["username"],
        "role": profile["role"],
        "is_active": profile["is_active"],
    }


@app.get("/api/admin/users")
def list_users(context=Depends(require_admin)):
    try:
        response = admin_client().table("profiles").select(
            "id,auth_user_id,full_name,username,role,is_active,created_at"
        ).in_("role", ["PREFET", "CAISSIER"]).order("created_at", desc=True).execute()
        return {"users": response.data or []}
    except Exception:
        logger.exception("Impossible de lister les comptes")
        raise HTTPException(status_code=500, detail="Impossible de charger les comptes.")


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserInput, context=Depends(require_admin)):
    client = admin_client()
    auth_user_id = None
    try:
        created = client.auth.admin.create_user({
            "email": str(payload.email),
            "password": payload.password,
            "email_confirm": True,
            "user_metadata": {"full_name": payload.full_name},
        })
        if not created.user:
            raise HTTPException(status_code=400, detail="La création du compte Auth a échoué.")
        auth_user_id = str(created.user.id)
        inserted = client.table("profiles").insert({
            "auth_user_id": auth_user_id,
            "full_name": payload.full_name.strip(),
            "role": payload.role,
            "is_active": True,
        }).execute()
        profile = inserted.data[0] if inserted.data else None
        if not profile:
            raise RuntimeError("Le profil métier n'a pas été créé.")
        audit("CREATE_PROFILE", context["profile"]["id"], profile["id"],
              new_data={"full_name": payload.full_name, "role": payload.role, "is_active": True})
        return {"user": profile}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de création de compte")
        if auth_user_id:
            try:
                client.auth.admin.delete_user(auth_user_id)
            except Exception:
                logger.exception("Échec du nettoyage du compte Auth incomplet")
        raise HTTPException(status_code=400, detail="Création impossible. Vérifiez que l'adresse e-mail n'est pas déjà utilisée.")


@app.patch("/api/admin/users/{profile_id}")
def update_user(profile_id: UUID, payload: UpdateUserInput, context=Depends(require_admin)):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification fournie.")
    client = admin_client()
    try:
        before_result = client.table("profiles").select(
            "id,auth_user_id,full_name,role,is_active"
        ).eq("id", str(profile_id)).in_("role", ["PREFET", "CAISSIER"]).single().execute()
        before = before_result.data
        if not before:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        updated = client.table("profiles").update(changes).eq("id", str(profile_id)).execute()
        after = updated.data[0] if updated.data else None
        if not after:
            raise RuntimeError("La modification n'a retourné aucun profil.")
        audit("UPDATE_PROFILE", context["profile"]["id"], str(profile_id),
              old_data={k: before.get(k) for k in changes},
              new_data={k: after.get(k) for k in changes})
        return {"user": after}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de modification de compte")
        raise HTTPException(status_code=400, detail="Modification du compte impossible.")


@app.get("/api/config")
def config():
    return {"application": "GESTION BÉATRICE", "login_enabled": bool(SUPABASE_URL and SUPABASE_ANON_KEY)}


@app.get("/health/ready")
def ready():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Configuration Supabase incomplète.")
    return {"status": "ready"}

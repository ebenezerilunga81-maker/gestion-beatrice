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
        raise HTTPException(status_code=503, detail="Authentification non configurée.")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False))


def admin_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Service administratif non configuré.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False))


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


def bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Session requise.")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Jeton absent.")
    return token


def current_profile(token: str = Depends(bearer_token)):
    try:
        auth_user = public_client().auth.get_user(token).user
        if auth_user is None:
            raise HTTPException(status_code=401, detail="Session invalide.")
        profile = admin_client().table("profiles").select(
            "id,auth_user_id,full_name,username,role,is_active"
        ).eq("auth_user_id", str(auth_user.id)).maybe_single().execute().data
        if not profile or not profile["is_active"]:
            raise HTTPException(status_code=403, detail="Compte absent ou désactivé.")
        return {"user": auth_user, "profile": profile}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Validation de session échouée")
        raise HTTPException(status_code=401, detail="Session invalide ou expirée.")


def require_admin(context=Depends(current_profile)):
    if context["profile"]["role"] != "ADMINISTRATEUR":
        raise HTTPException(status_code=403, detail="Action réservée à l'administrateur.")
    return context


def write_audit(action: str, actor_id: str, record_id: str, old_data=None, new_data=None):
    admin_client().table("audit_logs").insert({
        "actor_profile_id": actor_id, "action": action, "table_name": "profiles",
        "record_id": str(record_id), "old_data": old_data, "new_data": new_data,
    }).execute()


@app.get("/")
def root():
    return {"name": "GESTION BÉATRICE API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "gestion-beatrice-api",
            "supabase_url_configured": bool(SUPABASE_URL),
            "public_auth_configured": bool(SUPABASE_ANON_KEY),
            "admin_key_configured": bool(SUPABASE_SERVICE_ROLE_KEY)}


@app.get("/health/ready")
def ready():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Configuration Supabase incomplète.")
    return {"status": "ready"}


@app.post("/api/auth/login")
def login(payload: LoginInput):
    try:
        client = public_client()
        session = client.auth.sign_in_with_password({"email": str(payload.email), "password": payload.password})
        if not session.user or not session.session:
            raise HTTPException(status_code=401, detail="Identifiants incorrects.")
        profile = admin_client().table("profiles").select(
            "id,full_name,role,is_active"
        ).eq("auth_user_id", str(session.user.id)).maybe_single().execute().data
        if not profile or not profile["is_active"]:
            raise HTTPException(status_code=403, detail="Compte non activé dans GESTION BÉATRICE.")
        return {"access_token": session.session.access_token,
                "refresh_token": session.session.refresh_token,
                "token_type": "bearer", "expires_in": session.session.expires_in,
                "user": {"id": str(session.user.id), "full_name": profile["full_name"], "role": profile["role"]}}
    except HTTPException:
        raise
    except Exception:
        logger.warning("Connexion refusée", exc_info=True)
        raise HTTPException(status_code=401, detail="Connexion refusée. Vérifiez vos identifiants.")


@app.get("/api/me")
def me(context=Depends(current_profile)):
    return context["profile"]


@app.get("/api/admin/users")
def list_users(context=Depends(require_admin)):
    try:
        rows = admin_client().table("profiles").select(
            "id,auth_user_id,full_name,username,role,is_active,created_at"
        ).in_("role", ["PREFET", "CAISSIER"]).order("created_at", desc=True).execute().data
        return {"users": rows or []}
    except Exception:
        logger.exception("Liste des comptes indisponible")
        raise HTTPException(status_code=500, detail="Impossible de charger les comptes.")


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserInput, context=Depends(require_admin)):
    client = admin_client()
    auth_id = None
    try:
        created = client.auth.admin.create_user({
            "email": str(payload.email), "password": payload.password,
            "email_confirm": True, "user_metadata": {"full_name": payload.full_name.strip()},
        })
        if not created.user:
            raise RuntimeError("Auth user missing")
        auth_id = str(created.user.id)
        inserted = client.table("profiles").insert({
            "auth_user_id": auth_id, "full_name": payload.full_name.strip(),
            "role": payload.role, "is_active": True,
        }).execute()
        profile = inserted.data[0]
        write_audit("CREATE_PROFILE", context["profile"]["id"], profile["id"],
                    new_data={"full_name": payload.full_name, "role": payload.role, "is_active": True})
        return {"user": profile}
    except Exception:
        logger.exception("Création de compte impossible")
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
            except Exception:
                logger.exception("Nettoyage Auth impossible après erreur")
        raise HTTPException(status_code=400, detail="Création impossible. Vérifiez l'adresse e-mail et réessayez.")


@app.patch("/api/admin/users/{profile_id}")
def update_user(profile_id: UUID, payload: UpdateUserInput, context=Depends(require_admin)):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification fournie.")
    client = admin_client()
    try:
        before = client.table("profiles").select(
            "id,auth_user_id,full_name,role,is_active"
        ).eq("id", str(profile_id)).in_("role", ["PREFET", "CAISSIER"]).maybe_single().execute().data
        if not before:
            raise HTTPException(status_code=404, detail="Compte introuvable.")
        after_rows = client.table("profiles").update(changes).eq("id", str(profile_id)).execute().data
        if not after_rows:
            raise RuntimeError("Profil non modifié")
        after = after_rows[0]
        write_audit("UPDATE_PROFILE", context["profile"]["id"], str(profile_id),
                    old_data={k: before.get(k) for k in changes},
                    new_data={k: after.get(k) for k in changes})
        return {"user": after}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Modification de compte impossible")
        raise HTTPException(status_code=400, detail="Modification du compte impossible.")

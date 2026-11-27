import os
import logging
import secrets
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from supabase import create_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gestion-beatrice")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://gestion-beatrice-officielle.onrender.com").strip()
BOOTSTRAP_ADMIN_ENABLED = os.getenv("BOOTSTRAP_ADMIN_ENABLED", "false").strip().lower() == "true"
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_ADMIN_NAME = os.getenv("BOOTSTRAP_ADMIN_NAME", "").strip()
TEMP_ADMIN_RESET_ENABLED = os.getenv("TEMP_ADMIN_RESET_ENABLED", "false").strip().lower() == "true"
TEMP_ADMIN_PASSWORD = os.getenv("TEMP_ADMIN_PASSWORD", "").strip()

app = FastAPI(title="GESTION BÉATRICE API", version="0.1.0")

@app.on_event("startup")
def apply_one_time_temporary_admin_password():
    """Apply a one-time temporary password only when explicitly enabled in Render."""
    if not TEMP_ADMIN_RESET_ENABLED:
        return
    if not TEMP_ADMIN_PASSWORD or len(TEMP_ADMIN_PASSWORD) < 16:
        logger.error("Réinitialisation temporaire ignorée: mot de passe temporaire absent ou trop court.")
        return
    try:
        client = admin_client()
        profiles = client.table("profiles").select("auth_user_id").eq(
            "id", "cef9d861-a921-40cf-8410-6af9ac4bf7a0"
        ).eq("is_active", True).limit(1).execute().data or []
        if not profiles:
            logger.error("Réinitialisation temporaire ignorée: profil administrateur actif introuvable.")
            return
        client.auth.admin.update_user_by_id(
            profiles[0]["auth_user_id"], {"password": TEMP_ADMIN_PASSWORD}
        )
        logger.info("Mot de passe temporaire administrateur appliqué avec succès.")
    except Exception:
        logger.exception("Échec de l'application du mot de passe temporaire administrateur.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def public_client():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Authentification non configurée.")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def admin_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Service administratif non configuré.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


class SetPasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: Optional[str] = Field(default=None, min_length=20, max_length=8192)
    refresh_token: Optional[str] = Field(default=None, min_length=20, max_length=8192)
    code: Optional[str] = Field(default=None, min_length=8, max_length=2048)
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CreateUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    username: str = Field(min_length=3, max_length=40, pattern="^[A-Za-z0-9_.-]+$")
    role: str = Field(pattern="^(PROMOTEUR|PREFET|CAISSIER)$")


class UpdateUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    username: Optional[str] = Field(default=None, min_length=3, max_length=40, pattern="^[A-Za-z0-9_.-]+$")
    role: Optional[str] = Field(default=None, pattern="^(PROMOTEUR|PREFET|CAISSIER)$")
    is_active: Optional[bool] = None


class ResetUserPasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)


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



@app.post("/api/bootstrap/admin")
def bootstrap_first_admin():
    """One-time bootstrap for the institution's preconfigured first administrator.
    The account receives a random unknown password; access is completed only
    through Supabase's password-recovery email sent to the fixed mailbox.
    """
    if not BOOTSTRAP_ADMIN_ENABLED or not BOOTSTRAP_ADMIN_EMAIL or not BOOTSTRAP_ADMIN_NAME:
        raise HTTPException(status_code=404, detail="Initialisation indisponible.")
    client = admin_client()
    auth_id = None
    profile_id = None
    try:
        existing = client.table("profiles").select("id").limit(1).execute().data or []
        if existing:
            raise HTTPException(status_code=409, detail="Le compte administrateur initial a déjà été créé.")
        created = client.auth.admin.create_user({
            "email": BOOTSTRAP_ADMIN_EMAIL,
            "password": secrets.token_urlsafe(48),
            "email_confirm": True,
            "user_metadata": {"full_name": BOOTSTRAP_ADMIN_NAME},
        })
        if not created.user:
            raise RuntimeError("Création Auth incomplète")
        auth_id = str(created.user.id)
        inserted = client.table("profiles").insert({
            "auth_user_id": auth_id,
            "full_name": BOOTSTRAP_ADMIN_NAME,
            "role": "ADMINISTRATEUR",
            "is_active": True,
        }).execute()
        if not inserted.data:
            raise RuntimeError("Création du profil impossible")
        profile_id = inserted.data[0]["id"]
        client.table("audit_logs").insert({
            "actor_profile_id": profile_id,
            "action": "INITIAL_ADMIN_CREATED",
            "table_name": "profiles",
            "record_id": str(profile_id),
            "new_data": {"full_name": BOOTSTRAP_ADMIN_NAME, "role": "ADMINISTRATEUR", "email": BOOTSTRAP_ADMIN_EMAIL},
        }).execute()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Initialisation du premier administrateur impossible")
        if profile_id:
            try:
                client.table("profiles").delete().eq("id", profile_id).execute()
            except Exception:
                logger.exception("Nettoyage du profil initial impossible")
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
            except Exception:
                logger.exception("Nettoyage du compte Auth initial impossible")
        raise HTTPException(status_code=400, detail="Initialisation impossible. Vérifiez la configuration puis réessayez.")
    try:
        public_client().auth.reset_password_for_email(BOOTSTRAP_ADMIN_EMAIL)
        return {"status": "created", "message": "Compte administrateur créé. Un e-mail de définition du mot de passe vient d'être demandé."}
    except Exception:
        logger.exception("Compte initial créé mais e-mail de récupération non envoyé")
        return {"status": "created", "message": "Compte créé. Utilisez la fonction de réinitialisation du mot de passe ou vérifiez la configuration e-mail Supabase."}


@app.post("/api/bootstrap/admin/send-recovery")
def send_initial_admin_recovery():
    """Send a fresh recovery link only for the preconfigured first administrator."""
    if not BOOTSTRAP_ADMIN_ENABLED or not BOOTSTRAP_ADMIN_EMAIL:
        raise HTTPException(status_code=404, detail="Fonction indisponible.")
    try:
        client = public_client()
        client.auth.reset_password_for_email(
            BOOTSTRAP_ADMIN_EMAIL,
            {"redirect_to": FRONTEND_ORIGIN},
        )
        return {"status": "requested", "message": "Si le compte existe, un e-mail de réinitialisation a été demandé."}
    except Exception as exc:
        # Supabase enforces its own email rate limits; do not retry automatically.
        status_code = getattr(exc, "status", None) or getattr(exc, "status_code", None)
        logger.warning("Demande de récupération impossible (status=%s)", status_code or "unknown")
        if str(status_code) == "429" or "rate limit" in str(exc).lower() or "too many" in str(exc).lower():
            raise HTTPException(status_code=429, detail="Supabase limite temporairement les envois. Attendez le délai indiqué avant de demander un nouveau lien.")
        raise HTTPException(status_code=400, detail="Envoi impossible. Vérifiez la configuration e-mail Supabase et réessayez plus tard.")


@app.post("/api/auth/set-password")
def set_password(payload: SetPasswordInput):
    """Complete a password-recovery session using the user's one-time tokens."""
    try:
        client = public_client()
        if payload.code:
            client.auth.exchange_code_for_session(payload.code)
        elif payload.access_token and payload.refresh_token:
            client.auth.set_session(payload.access_token, payload.refresh_token)
        else:
            raise HTTPException(status_code=422, detail="Le lien de réinitialisation est incomplet.")
        result = client.auth.update_user({"password": payload.password})
        if not result or not result.user:
            raise RuntimeError("Mise à jour du mot de passe non confirmée")
        return {"status": "updated", "message": "Mot de passe défini. Vous pouvez maintenant vous connecter."}
    except HTTPException:
        raise
    except Exception:
        # Never log recovery tokens, authorization codes, or passwords.
        logger.warning("Définition du mot de passe refusée")
        raise HTTPException(status_code=400, detail="Lien invalide ou expiré. Demandez un nouvel e-mail de réinitialisation.")


@app.post("/api/auth/login")
def login(payload: LoginInput):
    try:
        client = public_client()
        identifier = payload.identifier.strip()
        login_email = identifier.lower()
        if "@" not in identifier:
            profile = admin_client().table("profiles").select(
                "auth_user_id,is_active"
            ).ilike("username", identifier).maybe_single().execute().data
            if not profile or not profile.get("is_active"):
                raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
            auth_user = admin_client().auth.admin.get_user_by_id(profile["auth_user_id"]).user
            if not auth_user or not auth_user.email:
                raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
            login_email = auth_user.email
        session = client.auth.sign_in_with_password({"email": login_email, "password": payload.password})
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
        ).in_("role", ["PROMOTEUR", "PREFET", "CAISSIER"]).order("created_at", desc=True).execute().data
        return {"users": rows or []}
    except Exception:
        logger.exception("Liste des comptes indisponible")
        raise HTTPException(status_code=500, detail="Impossible de charger les comptes.")


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserInput, context=Depends(require_admin)):
    client = admin_client()
    auth_id = None
    username = payload.username.strip().upper()
    try:
        duplicate = client.table("profiles").select("id").ilike("username", username).limit(1).execute().data
        if duplicate:
            raise HTTPException(status_code=409, detail="Cet identifiant est déjà utilisé.")
        # Adresse synthétique unique sur le domaine réservé example.com ; aucune adresse personnelle n'est requise.
        internal_email = f"{username.lower()}.{secrets.token_hex(6)}@example.com"
        created = client.auth.admin.create_user({
            "email": internal_email, "password": payload.password,
            "email_confirm": True, "user_metadata": {"full_name": payload.full_name.strip(), "username": username},
        })
        if not created.user:
            raise RuntimeError("Auth user missing")
        auth_id = str(created.user.id)
        inserted = client.table("profiles").insert({
            "auth_user_id": auth_id, "full_name": payload.full_name.strip(),
            "username": username, "role": payload.role, "is_active": True,
        }).execute()
        profile = inserted.data[0]
        write_audit("CREATE_PROFILE", context["profile"]["id"], profile["id"],
                    new_data={"full_name": payload.full_name, "role": payload.role, "is_active": True})
        return {"user": profile}
    except HTTPException:
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
            except Exception:
                logger.exception("Nettoyage Auth impossible après refus de création")
        raise
    except Exception:
        logger.exception("Création de compte impossible")
        if auth_id:
            try:
                client.auth.admin.delete_user(auth_id)
            except Exception:
                logger.exception("Nettoyage Auth impossible après erreur")
        raise HTTPException(status_code=400, detail="Création impossible. Vérifiez l'identifiant et le mot de passe puis réessayez.")


@app.patch("/api/admin/users/{profile_id}")
def update_user(profile_id: UUID, payload: UpdateUserInput, context=Depends(require_admin)):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "username" in changes:
        changes["username"] = changes["username"].strip().upper()
        duplicate = admin_client().table("profiles").select("id").ilike("username", changes["username"]).neq("id", str(profile_id)).limit(1).execute().data
        if duplicate:
            raise HTTPException(status_code=409, detail="Cet identifiant est déjà utilisé.")
    if not changes:
        raise HTTPException(status_code=400, detail="Aucune modification fournie.")
    client = admin_client()
    try:
        before = client.table("profiles").select(
            "id,auth_user_id,full_name,username,role,is_active"
        ).eq("id", str(profile_id)).in_("role", ["PROMOTEUR", "PREFET", "CAISSIER"]).maybe_single().execute().data
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


@app.post("/api/admin/users/{profile_id}/reset-password")
def reset_user_password(profile_id: UUID, payload: ResetUserPasswordInput, context=Depends(require_admin)):
    client = admin_client()
    try:
        target = client.table("profiles").select("id,auth_user_id,full_name,role").eq(
            "id", str(profile_id)
        ).in_("role", ["PROMOTEUR", "PREFET", "CAISSIER"]).maybe_single().execute().data
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable ou non réinitialisable.")
        client.auth.admin.update_user_by_id(target["auth_user_id"], {"password": payload.password})
        write_audit("RESET_USER_PASSWORD", context["profile"]["id"], str(profile_id),
                    new_data={"password_reset": True, "role": target["role"]})
        return {"status": "updated", "message": "Nouveau mot de passe enregistré. Communiquez-le directement à l'utilisateur."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Réinitialisation du mot de passe impossible")
        raise HTTPException(status_code=400, detail="Impossible de modifier le mot de passe.")


@app.delete("/api/admin/users/{profile_id}")
def delete_user(profile_id: UUID, context=Depends(require_admin)):
    client = admin_client()
    try:
        target = client.table("profiles").select("id,auth_user_id,full_name,username,role").eq(
            "id", str(profile_id)
        ).in_("role", ["PROMOTEUR", "PREFET", "CAISSIER"]).maybe_single().execute().data
        if not target:
            raise HTTPException(status_code=404, detail="Compte introuvable ou suppression interdite.")
        # Conserver l'intégrité financière : tout compte ayant encaissé un paiement
        # reste dans l'historique et doit être désactivé plutôt que supprimé.
        linked = client.table("payments").select("id").eq("cashier_id", str(profile_id)).limit(1).execute().data
        if linked:
            raise HTTPException(status_code=409, detail="Ce compte est associé à des paiements enregistrés. Désactivez-le pour conserver l'historique financier.")
        write_audit("DELETE_PROFILE", context["profile"]["id"], str(profile_id),
                    old_data={"full_name": target["full_name"], "username": target["username"], "role": target["role"]})
        client.table("payments").update({"annulled_by": None}).eq("annulled_by", str(profile_id)).execute()
        client.table("student_enrollments").update({"decision_validated_by": None}).eq("decision_validated_by", str(profile_id)).execute()
        client.auth.admin.delete_user(target["auth_user_id"])
        return {"status": "deleted", "message": "Compte supprimé. Les inscriptions, paiements et journaux sont conservés."}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Suppression définitive du compte impossible")
        raise HTTPException(status_code=400, detail="Suppression impossible. Les données liées à ce compte doivent être vérifiées.")


# ---------------------------------------------------------------------------
# Modules métier GESTION BÉATRICE — API protégée par rôle
# ---------------------------------------------------------------------------
from datetime import date as Date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


EXCHANGE_RATE_CDF_PER_USD = Decimal("2300")
MONEY_QUANTUM = Decimal("0.01")


def amount_to_usd(amount, currency):
    """Convertit un montant source en USD avec le taux fixe et un arrondi monétaire."""
    value = Decimal(str(amount))
    code = str(currency or "").strip().upper()
    if code == "USD":
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if code == "CDF":
        converted = (value / EXCHANGE_RATE_CDF_PER_USD).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
        if converted <= 0:
            raise HTTPException(status_code=422, detail="Le montant en CDF est trop faible après conversion en USD.")
        return converted
    raise HTTPException(status_code=422, detail="La devise doit être USD ou CDF.")


def payment_amount_usd(payment):
    """Lit l'équivalent USD figé; les anciens paiements USD restent compatibles."""
    stored = payment.get("amount_usd")
    if stored is not None:
        return Decimal(str(stored))
    if str(payment.get("currency", "")).strip().upper() == "USD":
        return Decimal(str(payment["amount_paid"])).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
    # Ne jamais recalculer un ancien paiement CDF avec le nouveau taux.
    return Decimal("0")


def require_roles(*roles):
    def dependency(context=Depends(current_profile)):
        if context["profile"]["role"] not in roles:
            raise HTTPException(status_code=403, detail="Vous n'avez pas l'autorisation d'accéder à ce module.")
        return context
    return dependency


def _rows(table, columns="*"):
    return admin_client().table(table).select(columns).execute().data or []


def _audit_business(context, action, table_name, record_id, old_data=None, new_data=None):
    admin_client().table("audit_logs").insert({
        "actor_profile_id": context["profile"]["id"],
        "action": action,
        "table_name": table_name,
        "record_id": str(record_id),
        "old_data": old_data,
        "new_data": new_data,
    }).execute()


@app.get("/api/references")
def references(context=Depends(current_profile)):
    client = admin_client()
    years = client.table("school_years").select("*").order("start_date", desc=True).execute().data or []
    active = next((y for y in years if y.get("is_active")), None)
    return {
        "categories": _rows("categories", "id,code,name"),
        "classes": _rows("classes", "id,category_id,code,name,level_order"),
        "options": _rows("options", "id,code,name,is_active"),
        "fee_types": _rows("fee_types", "id,code,name,is_active"),
        "active_year": active,
        "school_years": years,
        "tariffs": client.table("fee_tariffs").select(
            "id,school_year_id,fee_type_id,category_id,class_id,amount,currency,is_active"
        ).eq("school_year_id", active["id"]).execute().data if active else [],
    }


@app.get("/api/dashboard")
def dashboard(context=Depends(current_profile)):
    client = admin_client()
    profile = context["profile"]
    role = profile["role"]
    # Aucune année active est un état métier normal (avant la rentrée), pas une erreur API.
    # Ne pas utiliser maybe_single() ici : selon la version du client PostgREST,
    # une réponse vide peut produire None au lieu d’un objet réponse.
    year_rows = client.table("school_years").select("id,label").eq("is_active", True).limit(1).execute()
    year_data = year_rows.data if year_rows is not None else None
    year = year_data[0] if year_data else None
    if not year:
        return {"active_year": None, "students": 0, "payments": 0, "revenue": [],
                "balances": [], "recent_payments": [],
                "message": "Aucune année scolaire active. Le tableau de bord sera complet après l’ouverture de l’année scolaire."}

    enrollments = client.table("student_enrollments").select(
        "id,student_id,class_id,category_id,option_id"
    ).eq("school_year_id", year["id"]).execute().data or []
    enrollment_ids = [e["id"] for e in enrollments]
    tariffs = client.table("fee_tariffs").select(
        "id,fee_type_id,class_id,amount,currency"
    ).eq("school_year_id", year["id"]).eq("is_active", True).execute().data or []

    all_valid = []
    if enrollment_ids:
        all_valid = client.table("payments").select(
            "id,enrollment_id,cashier_id,fee_tariff_id,amount_paid,currency,amount_usd,exchange_rate,payment_reference,payment_date,status"
        ).eq("status", "VALIDE").in_("enrollment_id", enrollment_ids).execute().data or []
    visible_payments = [p for p in all_valid if role != "CAISSIER" or p["cashier_id"] == profile["id"]]

    paid_by_key = {}
    for payment in all_valid:
        key = (payment["enrollment_id"], payment["fee_tariff_id"])
        paid_by_key[key] = paid_by_key.get(key, Decimal("0")) + payment_amount_usd(payment)

    tariff_by_id = {t["id"]: t for t in tariffs}
    balances_by_currency = {}
    for enrollment in enrollments:
        for tariff in tariffs:
            if tariff["class_id"] != enrollment["class_id"]:
                continue
            due = amount_to_usd(tariff["amount"], tariff["currency"])
            paid = paid_by_key.get((enrollment["id"], tariff["id"]), Decimal("0"))
            remaining = max(due - paid, Decimal("0"))
            if remaining:
                balances_by_currency["USD"] = balances_by_currency.get("USD", Decimal("0")) + remaining

    revenue = {}
    for payment in visible_payments:
        revenue["USD"] = revenue.get("USD", Decimal("0")) + payment_amount_usd(payment)

    return {
        "active_year": year,
        "students": len({e["student_id"] for e in enrollments}),
        "payments": len(visible_payments),
        "revenue": [{"currency": k, "amount": str(v)} for k, v in revenue.items()],
        "balances": [{"currency": k, "amount": str(v)} for k, v in balances_by_currency.items()],
        "recent_payments": sorted(visible_payments, key=lambda p: p["payment_date"], reverse=True)[:8],
    }

@app.get("/api/admin/school-years")
def list_school_years(context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR"))):
    return {"school_years": _rows("school_years")}


class SchoolYearInput(BaseModel):
    label: str = Field(min_length=9, max_length=9)
    activate: bool = False


def school_year_dates(label: str):
    """Calcule automatiquement la rentrée et la fermeture réglementaires."""
    try:
        opening_year, closing_year = (int(part) for part in label.split("-"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Le libellé doit suivre le format AAAA-AAAA (ex. 2026-2027).")
    if closing_year != opening_year + 1:
        raise HTTPException(status_code=422, detail="L'année scolaire doit couvrir deux années consécutives.")
    september_first = Date(opening_year, 9, 1)
    opening_date = Date(opening_year, 9, 1 + ((7 - september_first.weekday()) % 7))
    closing_date = Date(closing_year, 7, 2)
    # Si le 2 juillet tombe un samedi ou un dimanche, reporter au lundi suivant.
    if closing_date.weekday() == 5:
        closing_date = Date(closing_year, 7, 4)
    elif closing_date.weekday() == 6:
        closing_date = Date(closing_year, 7, 3)
    return opening_date, closing_date


@app.post("/api/admin/school-years", status_code=201)
def create_school_year(payload: SchoolYearInput, context=Depends(require_roles("ADMINISTRATEUR"))):
    label = payload.label.strip()
    opening_date, closing_date = school_year_dates(label)
    client = admin_client()
    try:
        if payload.activate:
            client.table("school_years").update({"is_active": False}).eq("is_active", True).execute()
        result = client.table("school_years").insert({
            "label": label,
            "start_date": opening_date.isoformat(),
            "end_date": closing_date.isoformat(),
            "opening_date": opening_date.isoformat(),
            "is_active": payload.activate,
        }).execute()
        year = result.data[0]
        _audit_business(context, "CREATE_SCHOOL_YEAR", "school_years", year["id"], new_data=year)
        return {"school_year": year, "message": f"Année créée. Ouverture : {opening_date.strftime('%d/%m/%Y')} ; fermeture : {closing_date.strftime('%d/%m/%Y')}. Les tarifs de référence ont été copiés automatiquement."}
    except Exception as exc:
        logger.exception("Création année scolaire impossible")
        raise HTTPException(status_code=400, detail="Création impossible : vérifiez que cette année n'existe pas déjà.")


@app.post("/api/admin/school-years/{year_id}/activate")
def activate_school_year(year_id: UUID, context=Depends(require_roles("ADMINISTRATEUR"))):
    client = admin_client()
    target = client.table("school_years").select("*").eq("id", str(year_id)).maybe_single().execute().data
    if not target:
        raise HTTPException(status_code=404, detail="Année scolaire introuvable.")
    client.table("school_years").update({"is_active": False}).eq("is_active", True).execute()
    updated = client.table("school_years").update({"is_active": True}).eq("id", str(year_id)).execute().data[0]
    _audit_business(context, "ACTIVATE_SCHOOL_YEAR", "school_years", year_id, old_data={"is_active": False}, new_data={"is_active": True})
    return {"school_year": updated}


@app.get("/api/students")
def list_students(q: str = "", context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR", "CAISSIER"))):
    client = admin_client()
    year_rows = client.table("school_years").select("id,label").eq("is_active", True).limit(1).execute()
    year_data = year_rows.data if year_rows is not None else None
    year = year_data[0] if year_data else None
    if not year:
        return {"students": [], "active_year": None}

    enrollments = client.table("student_enrollments").select("*").eq(
        "school_year_id", year["id"]
    ).execute().data or []
    ids = [e["student_id"] for e in enrollments]
    if not ids:
        return {"students": [], "active_year": year}

    students = client.table("students").select("*").in_("id", ids).order("full_name").execute().data or []
    classes = {x["id"]: x for x in _rows("classes", "id,name,category_id")}
    categories = {x["id"]: x for x in _rows("categories", "id,name,code")}
    options = {x["id"]: x for x in _rows("options", "id,name")}
    fee_types = {x["id"]: x for x in _rows("fee_types", "id,name")}
    tariffs = client.table("fee_tariffs").select(
        "id,fee_type_id,category_id,class_id,amount,currency,is_active"
    ).eq("school_year_id", year["id"]).eq("is_active", True).execute().data or []
    enrollment_ids = [e["id"] for e in enrollments]
    payments = client.table("payments").select(
        "enrollment_id,fee_tariff_id,amount_paid,currency,amount_usd"
    ).eq("status", "VALIDE").in_("enrollment_id", enrollment_ids).execute().data if enrollment_ids else []
    paid_by_key = {}
    for payment in payments or []:
        key = (payment["enrollment_id"], payment["fee_tariff_id"])
        paid_by_key[key] = paid_by_key.get(key, Decimal("0")) + payment_amount_usd(payment)

    enrolled_by_student = {e["student_id"]: e for e in enrollments}
    needle = q.strip().casefold()
    result = []
    for student in students:
        enrollment = enrolled_by_student.get(student["id"], {})
        if needle and needle not in student["full_name"].casefold() and needle not in student["student_number"].casefold():
            continue
        class_row = classes.get(enrollment.get("class_id"), {})
        category = categories.get(enrollment.get("category_id"), {})
        option = options.get(enrollment.get("option_id"), {})
        fee_balances = []
        for tariff in tariffs:
            if tariff["class_id"] != enrollment.get("class_id"):
                continue
            due = amount_to_usd(tariff["amount"], tariff["currency"])
            paid = paid_by_key.get((enrollment.get("id"), tariff["id"]), Decimal("0"))
            fee_type = fee_types.get(tariff["fee_type_id"], {})
            fee_balances.append({
                "fee_tariff_id": tariff["id"],
                "fee_type_id": tariff["fee_type_id"],
                "fee_type_name": fee_type.get("name", "Frais"),
                "amount_due": str(due),
                "amount_paid": str(paid),
                "remaining_balance": str(max(due - paid, Decimal("0"))),
                "currency": "USD",
                "tariff_currency": tariff["currency"].strip(),
            })
        result.append({
            **student,
            "enrollment_id": enrollment.get("id"),
            "class_name": class_row.get("name"),
            "category_name": category.get("name"),
            "category_code": category.get("code"),
            "option_name": option.get("name"),
            "decision": enrollment.get("decision"),
            "fee_balances": fee_balances,
        })
    return {"students": result, "active_year": year}

@app.get("/api/students/search")
def search_students_for_cashier(q: str = "", context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR", "CAISSIER"))):
    """Recherche les fiches élèves existantes, même si elles n'ont pas encore d'inscription pour l'année active."""
    needle = q.strip()
    if len(needle) < 2:
        return {"students": []}
    client = admin_client()
    by_name = client.table("students").select(
        "id,student_number,full_name,date_of_birth"
    ).ilike("full_name", f"%{needle}%").order("full_name").limit(20).execute().data or []
    by_number = client.table("students").select(
        "id,student_number,full_name,date_of_birth"
    ).ilike("student_number", f"%{needle}%").limit(20).execute().data or []
    matches_by_id = {row["id"]: row for row in by_name}
    matches_by_id.update({row["id"]: row for row in by_number})
    matches = sorted(matches_by_id.values(), key=lambda row: row["full_name"].casefold())[:20]
    if not matches:
        return {"students": []}

    year_rows = client.table("school_years").select("id,label").eq("is_active", True).limit(1).execute()
    year = year_rows.data[0] if year_rows and year_rows.data else None
    student_ids = [s["id"] for s in matches]
    enrollments = []
    if year:
        enrollments = client.table("student_enrollments").select("*").eq(
            "school_year_id", year["id"]
        ).in_("student_id", student_ids).execute().data or []
    enrollment_map = {e["student_id"]: e for e in enrollments}
    class_ids = list({e["class_id"] for e in enrollments})
    category_ids = list({e["category_id"] for e in enrollments})
    option_ids = list({e["option_id"] for e in enrollments if e.get("option_id")})
    classes = {x["id"]: x for x in (client.table("classes").select("id,name,category_id").in_("id", class_ids).execute().data or [])} if class_ids else {}
    categories = {x["id"]: x for x in (client.table("categories").select("id,name,code").in_("id", category_ids).execute().data or [])} if category_ids else {}
    options = {x["id"]: x for x in (client.table("options").select("id,name").in_("id", option_ids).execute().data or [])} if option_ids else {}
    tariffs = client.table("fee_tariffs").select(
        "id,fee_type_id,category_id,class_id,amount,currency,is_active"
    ).eq("school_year_id", year["id"]).eq("is_active", True).execute().data or [] if year else []
    fee_types = {x["id"]: x for x in _rows("fee_types", "id,name")}
    enrollment_ids = [e["id"] for e in enrollments]
    payments = client.table("payments").select(
        "enrollment_id,fee_tariff_id,amount_paid,currency,amount_usd"
    ).eq("status", "VALIDE").in_("enrollment_id", enrollment_ids).execute().data or [] if enrollment_ids else []
    paid = {}
    for p in payments:
        key = (p["enrollment_id"], p["fee_tariff_id"])
        paid[key] = paid.get(key, Decimal("0")) + payment_amount_usd(p)

    result = []
    for student in matches:
        enrollment = enrollment_map.get(student["id"])
        class_row = classes.get(enrollment.get("class_id"), {}) if enrollment else {}
        category = categories.get(enrollment.get("category_id"), {}) if enrollment else {}
        option = options.get(enrollment.get("option_id"), {}) if enrollment else {}
        balances = []
        if enrollment:
            for tariff in tariffs:
                if tariff["class_id"] != enrollment["class_id"] or tariff["category_id"] != enrollment["category_id"]:
                    continue
                due = amount_to_usd(tariff["amount"], tariff["currency"])
                already = paid.get((enrollment["id"], tariff["id"]), Decimal("0"))
                balances.append({
                    "fee_tariff_id": tariff["id"],
                    "fee_type_name": fee_types.get(tariff["fee_type_id"], {}).get("name", "Frais"),
                    "amount_due": str(due), "amount_paid": str(already),
                    "remaining_balance": str(max(due - already, Decimal("0"))),
                    "currency": "USD",
                    "tariff_currency": tariff["currency"].strip(),
                })
        result.append({
            **student,
            "enrollment_id": enrollment.get("id") if enrollment else None,
            "category_id": enrollment.get("category_id") if enrollment else None,
            "category_name": category.get("name"),
            "category_code": category.get("code"),
            "class_id": enrollment.get("class_id") if enrollment else None,
            "class_name": class_row.get("name"),
            "option_id": enrollment.get("option_id") if enrollment else None,
            "option_name": option.get("name"),
            "fee_balances": balances,
        })
    return {"students": result, "active_year": year}


class EnrollmentInput(BaseModel):
    student_id: Optional[UUID] = None
    full_name: str = Field(min_length=2, max_length=180)
    date_of_birth: Optional[Date] = None
    category_id: int
    class_id: int
    option_id: Optional[int] = None


@app.post("/api/enrollments", status_code=201)
def create_enrollment(payload: EnrollmentInput, context=Depends(require_roles("ADMINISTRATEUR"))):
    client = admin_client()
    year = client.table("school_years").select("id").eq("is_active", True).maybe_single().execute().data
    if not year:
        raise HTTPException(status_code=409, detail="Aucune année scolaire active. L'administrateur doit d'abord ouvrir une année.")
    cls = client.table("classes").select("id,category_id").eq("id", payload.class_id).maybe_single().execute().data
    if not cls or cls["category_id"] != payload.category_id:
        raise HTTPException(status_code=422, detail="La classe ne correspond pas à la catégorie sélectionnée.")
    cat = client.table("categories").select("code").eq("id", payload.category_id).single().execute().data
    if cat["code"] == "HUMANITE" and not payload.option_id:
        raise HTTPException(status_code=422, detail="L'option est obligatoire pour les humanités.")
    if cat["code"] != "HUMANITE" and payload.option_id:
        raise HTTPException(status_code=422, detail="L'option est réservée aux humanités.")
    if payload.option_id:
        valid_option = client.table("options").select("id").eq("id", payload.option_id).eq("is_active", True).maybe_single().execute().data
        if not valid_option:
            raise HTTPException(status_code=422, detail="Option invalide.")
    student_id = str(payload.student_id) if payload.student_id else None
    if not student_id:
        duplicate = client.table("students").select("id").ilike(
            "full_name", payload.full_name.strip()
        ).limit(1).execute().data or []
        if duplicate:
            raise HTTPException(status_code=409, detail="Cette fiche élève existe déjà. Recherchez son nom et sélectionnez la fiche correspondante.")
    try:
        if student_id:
            student = client.table("students").select("id,full_name").eq("id", student_id).single().execute().data
            if not student:
                raise HTTPException(status_code=404, detail="Élève introuvable.")
        else:
            created_student = client.table("students").insert({
                "full_name": payload.full_name.strip(),
                "date_of_birth": payload.date_of_birth.isoformat() if payload.date_of_birth else None,
            }).execute().data[0]
            student_id = created_student["id"]
            student = created_student
        created = client.table("student_enrollments").insert({
            "student_id": student_id, "school_year_id": year["id"],
            "category_id": payload.category_id, "class_id": payload.class_id,
            "option_id": payload.option_id,
        }).execute().data[0]
        _audit_business(context, "CREATE_ENROLLMENT", "student_enrollments", created["id"],
                        new_data={"student_id": student_id, "school_year_id": year["id"]})
        return {"student": student, "enrollment": created}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Inscription impossible")
        raise HTTPException(status_code=400, detail="Inscription impossible. Vérifiez que l'élève n'est pas déjà inscrit pour cette année.")


@app.get("/api/payments")
def list_payments(context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR", "CAISSIER"))):
    client = admin_client()
    profile = context["profile"]
    query = client.table("payments").select("*").order("payment_date", desc=True).limit(500)
    if profile["role"] == "CAISSIER":
        query = query.eq("cashier_id", profile["id"])
    payments = query.execute().data or []
    enrollment_ids = list({p["enrollment_id"] for p in payments})
    enrollments = client.table("student_enrollments").select("*").in_("id", enrollment_ids).execute().data if enrollment_ids else []
    enrollment_map = {e["id"]: e for e in (enrollments or [])}
    student_ids = list({e["student_id"] for e in (enrollments or [])})
    students = client.table("students").select("id,student_number,full_name").in_("id", student_ids).execute().data if student_ids else []
    student_map = {s["id"]: s for s in (students or [])}
    tariff_ids = list({p["fee_tariff_id"] for p in payments})
    tariffs = client.table("fee_tariffs").select("id,fee_type_id,class_id,amount,currency").in_("id", tariff_ids).execute().data if tariff_ids else []
    tariff_map = {t["id"]: t for t in (tariffs or [])}
    fee_types = {x["id"]: x for x in _rows("fee_types", "id,name")}
    classes = {x["id"]: x for x in _rows("classes", "id,name")}
    options = {x["id"]: x for x in _rows("options", "id,name")}
    cashier_ids = list({p["cashier_id"] for p in payments})
    cashiers = client.table("profiles").select("id,full_name").in_("id", cashier_ids).execute().data if cashier_ids else []
    cashier_map = {x["id"]: x["full_name"] for x in (cashiers or [])}
    tickets = client.table("tickets").select("payment_id,ticket_number").in_(
        "payment_id", [p["id"] for p in payments]
    ).execute().data if payments else []
    ticket_map = {t["payment_id"]: t["ticket_number"] for t in (tickets or [])}
    result = []
    for payment in payments:
        enrollment = enrollment_map.get(payment["enrollment_id"], {})
        tariff = tariff_map.get(payment["fee_tariff_id"], {})
        student = student_map.get(enrollment.get("student_id"), {})
        result.append({
            **payment,
            "student": student,
            "ticket_number": ticket_map.get(payment["id"]),
            "fee_type_name": fee_types.get(tariff.get("fee_type_id"), {}).get("name", "Frais"),
            "class_name": classes.get(enrollment.get("class_id"), {}).get("name"),
            "option_name": options.get(enrollment.get("option_id"), {}).get("name"),
            "tariff_amount": str(tariff.get("amount", "0")),
            "cashier_name": cashier_map.get(payment["cashier_id"], "Caissier"),
        })
    return {"payments": result}

@app.get("/api/students/{student_id}/payments")
def student_payment_history(student_id: UUID, context=Depends(require_roles("CAISSIER"))):
    """Historique complet des paiements de l'élève, toutes années scolaires confondues."""
    client = admin_client()
    student = client.table("students").select(
        "id,student_number,full_name"
    ).eq("id", str(student_id)).maybe_single().execute().data
    if not student:
        raise HTTPException(status_code=404, detail="Élève introuvable.")
    enrollments = client.table("student_enrollments").select(
        "id,school_year_id,class_id,category_id,option_id"
    ).eq("student_id", str(student_id)).execute().data or []
    enrollment_ids = [row["id"] for row in enrollments]
    if not enrollment_ids:
        return {"student": student, "payments": [], "fee_balances": []}
    payments = client.table("payments").select("*").in_(
        "enrollment_id", enrollment_ids
    ).order("payment_date", desc=True).execute().data or []
    year_ids = list({row["school_year_id"] for row in enrollments})
    years = client.table("school_years").select("id,label,is_active").in_("id", year_ids).execute().data or []
    year_map = {row["id"]: row["label"] for row in years}
    class_ids = list({row["class_id"] for row in enrollments if row.get("class_id")})
    option_ids = list({row["option_id"] for row in enrollments if row.get("option_id")})
    classes = client.table("classes").select("id,name").in_("id", class_ids).execute().data if class_ids else []
    options = client.table("options").select("id,name").in_("id", option_ids).execute().data if option_ids else []
    class_map = {row["id"]: row["name"] for row in (classes or [])}
    option_map = {row["id"]: row["name"] for row in (options or [])}
    tariff_ids = list({row["fee_tariff_id"] for row in payments})
    tariffs = client.table("fee_tariffs").select(
        "id,fee_type_id,amount,currency"
    ).in_("id", tariff_ids).execute().data if tariff_ids else []
    tariff_map = {row["id"]: row for row in (tariffs or [])}
    fee_types = {row["id"]: row for row in _rows("fee_types", "id,name")}
    tickets = client.table("tickets").select(
        "payment_id,ticket_number"
    ).in_("payment_id", [row["id"] for row in payments]).execute().data if payments else []
    ticket_map = {row["payment_id"]: row["ticket_number"] for row in (tickets or [])}
    cashier_ids = list({row["cashier_id"] for row in payments if row.get("cashier_id")})
    cashiers = client.table("profiles").select(
        "id,full_name"
    ).in_("id", cashier_ids).execute().data if cashier_ids else []
    cashier_map = {row["id"]: row["full_name"] for row in (cashiers or [])}
    enrollment_map = {row["id"]: row for row in enrollments}
    results = []
    for payment in payments:
        enrollment = enrollment_map.get(payment["enrollment_id"], {})
        tariff = tariff_map.get(payment["fee_tariff_id"], {})
        fee_type = fee_types.get(tariff.get("fee_type_id"), {})
        results.append({
            **payment,
            "school_year_label": year_map.get(enrollment.get("school_year_id"), "—"),
            "ticket_number": ticket_map.get(payment["id"]),
            "fee_type_name": fee_type.get("name", "Frais"),
            "class_name": class_map.get(enrollment.get("class_id"), "—"),
            "option_name": option_map.get(enrollment.get("option_id"), ""),
            "cashier_name": cashier_map.get(payment.get("cashier_id"), "Caissier"),
        })
    active_year = next((row for row in enrollments if year_map.get(row["school_year_id"]) and any(
        year.get("id") == row["school_year_id"] and year.get("is_active") for year in years
    )), None)
    fee_balances = []
    if active_year:
        active_tariffs = client.table("fee_tariffs").select(
            "id,fee_type_id,amount,currency"
        ).eq("school_year_id", active_year["school_year_id"]).eq(
            "category_id", active_year["category_id"]
        ).eq("class_id", active_year["class_id"]).eq("is_active", True).execute().data or []
        active_payments = [row for row in payments if row["enrollment_id"] == active_year["id"] and row["status"] == "VALIDE"]
        paid_by_tariff = {}
        for row in active_payments:
            paid_by_tariff[row["fee_tariff_id"]] = paid_by_tariff.get(row["fee_tariff_id"], Decimal("0")) + payment_amount_usd(row)
        for tariff in active_tariffs:
            due = amount_to_usd(tariff["amount"], tariff["currency"])
            paid = paid_by_tariff.get(tariff["id"], Decimal("0"))
            fee_balances.append({
                "fee_type_name": fee_types.get(tariff["fee_type_id"], {}).get("name", "Frais"),
                "amount_due": str(due), "amount_paid": str(paid),
                "remaining_balance": str(max(due - paid, Decimal("0"))),
            })
    return {"student": student, "payments": results, "fee_balances": fee_balances}


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enrollment_id: Optional[UUID] = None
    student_id: Optional[UUID] = None
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    date_of_birth: Optional[Date] = None
    category_id: Optional[int] = None
    class_id: Optional[int] = None
    option_id: Optional[int] = None
    fee_tariff_id: UUID
    amount_paid: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", pattern="^(USD|CDF)$")
    notes: Optional[str] = Field(default=None, max_length=500)


@app.post("/api/payments", status_code=201)
def register_payment(payload: PaymentInput, context=Depends(require_roles("CAISSIER"))):
    client = admin_client()
    profile_id = context["profile"]["id"]
    year_rows = client.table("school_years").select("id,label").eq("is_active", True).limit(1).execute()
    year = year_rows.data[0] if year_rows and year_rows.data else None
    if not year:
        raise HTTPException(status_code=409, detail="Aucune année scolaire active. L'encaissement est suspendu.")

    created_student_id = None
    created_enrollment_id = None
    try:
        enrollment = None
        student = None
        if payload.enrollment_id:
            enrollment = client.table("student_enrollments").select("*").eq(
                "id", str(payload.enrollment_id)
            ).eq("school_year_id", year["id"]).maybe_single().execute().data
            if not enrollment:
                raise HTTPException(status_code=404, detail="Inscription active introuvable.")
            student = client.table("students").select(
                "id,student_number,full_name,date_of_birth"
            ).eq("id", enrollment["student_id"]).single().execute().data
        else:
            if payload.student_id:
                student = client.table("students").select(
                    "id,student_number,full_name,date_of_birth"
                ).eq("id", str(payload.student_id)).maybe_single().execute().data
                if not student:
                    raise HTTPException(status_code=404, detail="Fiche élève introuvable.")
            else:
                full_name = (payload.full_name or "").strip()
                if len(full_name) < 2:
                    raise HTTPException(status_code=422, detail="Le nom complet de l'élève est obligatoire.")
                duplicates = client.table("students").select(
                    "id,student_number,full_name"
                ).ilike("full_name", full_name).limit(5).execute().data or []
                if duplicates:
                    raise HTTPException(status_code=409, detail="Une fiche porte déjà ce nom. Recherchez-la et sélectionnez-la pour éviter un doublon.")

            if payload.category_id is None or payload.class_id is None:
                raise HTTPException(status_code=422, detail="Choisissez la catégorie et la classe de l'élève.")
            cls = client.table("classes").select("id,category_id").eq(
                "id", payload.class_id
            ).maybe_single().execute().data
            if not cls or cls["category_id"] != payload.category_id:
                raise HTTPException(status_code=422, detail="La classe ne correspond pas à la catégorie sélectionnée.")
            cat = client.table("categories").select("code").eq(
                "id", payload.category_id
            ).single().execute().data
            if cat["code"] == "HUMANITE" and not payload.option_id:
                raise HTTPException(status_code=422, detail="L'option est obligatoire pour les humanités.")
            if cat["code"] != "HUMANITE" and payload.option_id:
                raise HTTPException(status_code=422, detail="L'option est réservée aux humanités.")
            if payload.option_id:
                valid_option = client.table("options").select("id").eq(
                    "id", payload.option_id
                ).eq("is_active", True).maybe_single().execute().data
                if not valid_option:
                    raise HTTPException(status_code=422, detail="Option invalide.")

            existing_enrollment = None
            if student:
                existing_enrollment = client.table("student_enrollments").select("*").eq(
                    "student_id", student["id"]
                ).eq("school_year_id", year["id"]).maybe_single().execute().data
            if existing_enrollment:
                enrollment = existing_enrollment
            else:
                # Vérifier le tarif avant de créer la fiche ou l'inscription.
                tariff_check = client.table("fee_tariffs").select("*").eq(
                    "id", str(payload.fee_tariff_id)
                ).eq("school_year_id", year["id"]).eq("is_active", True).maybe_single().execute().data
                if not tariff_check or tariff_check["category_id"] != payload.category_id or tariff_check["class_id"] != payload.class_id:
                    raise HTTPException(status_code=422, detail="Le tarif sélectionné ne correspond pas à la classe.")
                if not student:
                    student = client.table("students").insert({
                        "full_name": full_name,
                        "date_of_birth": payload.date_of_birth.isoformat() if payload.date_of_birth else None,
                    }).execute().data[0]
                    created_student_id = student["id"]
                enrollment = client.table("student_enrollments").insert({
                    "student_id": student["id"], "school_year_id": year["id"],
                    "category_id": payload.category_id, "class_id": payload.class_id,
                    "option_id": payload.option_id,
                }).execute().data[0]
                created_enrollment_id = enrollment["id"]

        tariff = client.table("fee_tariffs").select("*").eq(
            "id", str(payload.fee_tariff_id)
        ).eq("school_year_id", year["id"]).eq("is_active", True).maybe_single().execute().data
        if not tariff or tariff["category_id"] != enrollment["category_id"] or tariff["class_id"] != enrollment["class_id"]:
            raise HTTPException(status_code=422, detail="Tarif non applicable à la classe de cet élève.")
        paid_rows = client.table("payments").select("amount_paid,currency,amount_usd").eq(
            "enrollment_id", enrollment["id"]
        ).eq("fee_tariff_id", str(payload.fee_tariff_id)).eq("status", "VALIDE").execute().data or []
        already_paid = sum((payment_amount_usd(x) for x in paid_rows), Decimal("0"))
        due = amount_to_usd(tariff["amount"], tariff["currency"])
        payment_usd = amount_to_usd(payload.amount_paid, payload.currency)
        remaining_before = max(due - already_paid, Decimal("0"))
        if already_paid + payment_usd > due:
            raise HTTPException(status_code=422, detail=f"Le versement dépasse le solde restant ({remaining_before:.2f} USD).")

        reference = "GB-P-" + secrets.token_hex(6).upper()
        ticket_number = "GB-T-" + secrets.token_hex(6).upper()
        result = client.rpc("register_school_payment", {
            "p_enrollment_id": enrollment["id"],
            "p_fee_tariff_id": str(payload.fee_tariff_id),
            "p_cashier_id": profile_id,
            "p_amount_paid": str(payload.amount_paid),
            "p_currency": payload.currency,
            "p_notes": payload.notes,
            "p_payment_reference": reference,
            "p_ticket_number": ticket_number,
        }).execute()
        row = result.data[0] if isinstance(result.data, list) and result.data else result.data
        exchange_rate = EXCHANGE_RATE_CDF_PER_USD if payload.currency == "CDF" else Decimal("1")
        remaining_after = max(due - already_paid - payment_usd, Decimal("0"))
        _audit_business(context, "REGISTER_PAYMENT", "payments", row["payment_id"],
                        new_data={"reference": reference, "amount": str(payload.amount_paid),
                                  "currency": payload.currency, "amount_usd": str(payment_usd),
                                  "exchange_rate": str(exchange_rate),
                                  "student_id": student["id"], "enrollment_id": enrollment["id"]})
        return {
            "payment_id": row["payment_id"], "ticket_number": ticket_number,
            "payment_reference": reference, "amount_paid": str(payload.amount_paid),
            "currency": payload.currency, "amount_usd": str(payment_usd),
            "exchange_rate": str(exchange_rate),
            "remaining_balance": str(remaining_after), "remaining_balance_currency": "USD",
            "student": student, "enrollment": enrollment,
        }
    except HTTPException:
        # Ne nettoyer que les enregistrements créés par cette requête et seulement si aucun paiement n'a été créé.
        if created_enrollment_id:
            existing_payment = client.table("payments").select("id").eq(
                "enrollment_id", created_enrollment_id
            ).limit(1).execute().data or []
            if not existing_payment:
                client.table("student_enrollments").delete().eq("id", created_enrollment_id).execute()
                if created_student_id:
                    client.table("students").delete().eq("id", created_student_id).execute()
        raise
    except Exception:
        logger.exception("Enregistrement paiement/ticket impossible")
        if created_enrollment_id:
            try:
                existing_payment = client.table("payments").select("id").eq(
                    "enrollment_id", created_enrollment_id
                ).limit(1).execute().data or []
                if not existing_payment:
                    client.table("student_enrollments").delete().eq("id", created_enrollment_id).execute()
                    if created_student_id:
                        client.table("students").delete().eq("id", created_student_id).execute()
            except Exception:
                logger.exception("Nettoyage des fiches temporaires impossible après échec d'encaissement")
        raise HTTPException(status_code=400, detail="Le paiement n'a pas pu être validé. Vérifiez le solde et réessayez.")


class CorrectPaymentInput(BaseModel):
    amount_paid: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=500)


@app.patch("/api/payments/{payment_id}/correct")
def correct_own_payment(payment_id: UUID, payload: CorrectPaymentInput, context=Depends(require_roles("CAISSIER"))):
    client = admin_client()
    profile_id = context["profile"]["id"]
    payment = client.table("payments").select("*").eq("id", str(payment_id)).maybe_single().execute().data
    if not payment or payment["cashier_id"] != profile_id or payment["status"] != "VALIDE":
        raise HTTPException(status_code=404, detail="Paiement introuvable ou non modifiable dans votre espace.")
    tariff = client.table("fee_tariffs").select("amount,currency").eq(
        "id", payment["fee_tariff_id"]
    ).single().execute().data
    other_rows = client.table("payments").select("amount_paid,currency,amount_usd").eq(
        "enrollment_id", payment["enrollment_id"]
    ).eq("fee_tariff_id", payment["fee_tariff_id"]).eq("status", "VALIDE").neq("id", str(payment_id)).execute().data or []
    already_paid = sum((payment_amount_usd(row) for row in other_rows), Decimal("0"))
    due_usd = amount_to_usd(tariff["amount"], tariff["currency"])
    original_currency = str(payment["currency"]).strip().upper()
    if original_currency == "USD":
        exchange_rate = Decimal("1")
    elif payment.get("exchange_rate") is not None:
        exchange_rate = Decimal(str(payment["exchange_rate"]))
    else:
        raise HTTPException(status_code=409, detail="Ce paiement ancien en CDF n'a pas de taux historique. Il ne peut pas être rectifié automatiquement.")
    amount_usd = (payload.amount_paid / exchange_rate).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if amount_usd <= 0 or already_paid + amount_usd > due_usd:
        raise HTTPException(status_code=422, detail=f"La rectification dépasse le tarif autorisé. Solde maximal : {max(due_usd - already_paid, Decimal('0')):.2f} USD.")
    before = payment
    updated = client.table("payments").update({
        "amount_paid": str(payload.amount_paid),
        "amount_usd": str(amount_usd),
        "exchange_rate": str(exchange_rate),
        "notes": payload.notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", str(payment_id)).eq("cashier_id", profile_id).eq("status", "VALIDE").execute().data
    if not updated:
        raise HTTPException(status_code=409, detail="Le paiement a changé entre-temps. Rechargez l'historique.")
    _audit_business(context, "CORRECT_OWN_PAYMENT", "payments", payment_id,
                    old_data=before, new_data=updated[0])
    return {"payment": updated[0], "message": "Paiement rectifié. L'ancienne valeur reste conservée dans l'historique d'audit."}


class CancelPaymentInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@app.post("/api/payments/{payment_id}/cancel")
def cancel_payment(payment_id: UUID, payload: CancelPaymentInput, context=Depends(require_roles("PROMOTEUR", "PREFET"))):
    client = admin_client()
    payment = client.table("payments").select("*").eq("id", str(payment_id)).maybe_single().execute().data
    if not payment:
        raise HTTPException(status_code=404, detail="Paiement introuvable.")
    if payment["status"] != "VALIDE":
        raise HTTPException(status_code=409, detail="Ce paiement est déjà annulé.")
    changes = {"status":"ANNULE","annulled_at":datetime.now(timezone.utc).isoformat(),
               "annulled_by":context["profile"]["id"],"annulment_reason":payload.reason.strip()}
    updated = client.table("payments").update(changes).eq("id", str(payment_id)).execute().data[0]
    _audit_business(context, "CANCEL_PAYMENT", "payments", payment_id, old_data=payment, new_data=updated)
    return {"payment": updated}


@app.get("/api/admin/tariffs")
def list_tariffs(context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR"))):
    return {"templates": _rows("fee_tariff_templates"), "tariffs": _rows("fee_tariffs")}


class TariffUpdateInput(BaseModel):
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    is_active: bool = True


@app.patch("/api/admin/tariffs/{tariff_id}")
def update_tariff(tariff_id: UUID, payload: TariffUpdateInput, context=Depends(require_roles("ADMINISTRATEUR"))):
    client = admin_client()
    before = client.table("fee_tariffs").select("*").eq("id", str(tariff_id)).maybe_single().execute().data
    if not before:
        raise HTTPException(status_code=404, detail="Tarif annuel introuvable.")
    updated = client.table("fee_tariffs").update({"amount":str(payload.amount),"is_active":payload.is_active}).eq("id", str(tariff_id)).execute().data[0]
    _audit_business(context, "UPDATE_ANNUAL_TARIFF", "fee_tariffs", tariff_id, old_data=before, new_data=updated)
    return {"tariff": updated}


class DecisionInput(BaseModel):
    decision: str = Field(pattern="^(PROMU|REDOUBLE|SORTANT|FIN_CYCLE)$")


@app.patch("/api/admin/enrollments/{enrollment_id}/decision")
def validate_decision(enrollment_id: UUID, payload: DecisionInput, context=Depends(require_roles("ADMINISTRATEUR"))):
    client = admin_client()
    enrollment = client.table("student_enrollments").select("*").eq("id", str(enrollment_id)).maybe_single().execute().data
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscription introuvable.")
    cls = client.table("classes").select("code").eq("id", enrollment["class_id"]).single().execute().data
    if payload.decision == "FIN_CYCLE" and cls["code"] != "SEC4":
        raise HTTPException(status_code=422, detail="La fin de cycle concerne uniquement la quatrième humanité.")
    changes = {"decision":payload.decision,"decision_validated_by":context["profile"]["id"],
               "decision_validated_at":datetime.now(timezone.utc).isoformat()}
    updated = client.table("student_enrollments").update(changes).eq("id", str(enrollment_id)).execute().data[0]
    _audit_business(context, "VALIDATE_STUDENT_DECISION", "student_enrollments", enrollment_id,
                    old_data=enrollment, new_data=updated)
    return {"enrollment": updated}



@app.get("/api/archive")
def archive_records(
    school_year_id: Optional[UUID] = None,
    category_id: Optional[int] = None,
    class_id: Optional[int] = None,
    option_id: Optional[int] = None,
    student_id: Optional[UUID] = None,
    context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR", "CAISSIER")),
):
    """Consultation historique par année, section, classe, option et élève; aucune écriture."""
    client = admin_client()
    years = client.table("school_years").select("id,label,start_date,end_date,is_active").order("start_date", desc=True).execute().data or []
    categories = _rows("categories", "id,code,name")
    classes = _rows("classes", "id,category_id,code,name,level_order")
    options = _rows("options", "id,code,name,is_active")
    fee_types = _rows("fee_types", "id,code,name,is_active")
    if not school_year_id:
        return {"school_years": years, "categories": categories, "classes": classes,
                "options": options, "fee_types": fee_types, "students": [], "payments": []}

    enrollment_query = client.table("student_enrollments").select("*").eq("school_year_id", str(school_year_id))
    if category_id is not None:
        enrollment_query = enrollment_query.eq("category_id", category_id)
    if class_id is not None:
        enrollment_query = enrollment_query.eq("class_id", class_id)
    if option_id is not None:
        enrollment_query = enrollment_query.eq("option_id", option_id)
    if student_id:
        enrollment_query = enrollment_query.eq("student_id", str(student_id))
    enrollments = enrollment_query.execute().data or []
    enrollment_ids = [e["id"] for e in enrollments]
    if not enrollment_ids:
        return {"school_years": years, "categories": categories, "classes": classes,
                "options": options, "fee_types": fee_types, "students": [], "payments": []}

    students_rows = client.table("students").select("id,student_number,full_name").in_(
        "id", list({e["student_id"] for e in enrollments})
    ).order("full_name").execute().data or []
    student_map = {s["id"]: s for s in students_rows}
    class_map = {x["id"]: x for x in classes}
    category_map = {x["id"]: x for x in categories}
    option_map = {x["id"]: x for x in options}
    fee_type_map = {x["id"]: x for x in fee_types}
    tariffs = client.table("fee_tariffs").select("id,fee_type_id,class_id,amount,currency").eq(
        "school_year_id", str(school_year_id)
    ).execute().data or []
    tariff_map = {t["id"]: t for t in tariffs}
    payments = client.table("payments").select("*").in_(
        "enrollment_id", enrollment_ids
    ).order("payment_date", desc=True).execute().data or []
    tickets = client.table("tickets").select("payment_id,ticket_number").in_(
        "payment_id", [p["id"] for p in payments]
    ).execute().data if payments else []
    ticket_map = {t["payment_id"]: t["ticket_number"] for t in (tickets or [])}
    cashier_ids = list({p["cashier_id"] for p in payments if p.get("cashier_id")})
    cashiers = client.table("profiles").select("id,full_name").in_("id", cashier_ids).execute().data if cashier_ids else []
    cashier_map = {x["id"]: x["full_name"] for x in (cashiers or [])}
    enrollment_map = {e["id"]: e for e in enrollments}

    student_results = []
    for enrollment in enrollments:
        student = student_map.get(enrollment["student_id"], {})
        cls = class_map.get(enrollment["class_id"], {})
        cat = category_map.get(enrollment["category_id"], {})
        opt = option_map.get(enrollment.get("option_id"), {})
        student_results.append({
            **student, "enrollment_id": enrollment["id"],
            "category_id": enrollment["category_id"], "category_name": cat.get("name"),
            "category_code": cat.get("code"), "class_id": enrollment["class_id"],
            "class_name": cls.get("name"), "option_id": enrollment.get("option_id"),
            "option_name": opt.get("name"),
        })

    payment_results = []
    for payment in payments:
        enrollment = enrollment_map.get(payment["enrollment_id"], {})
        tariff = tariff_map.get(payment["fee_tariff_id"], {})
        fee_type = fee_type_map.get(tariff.get("fee_type_id"), {})
        student = student_map.get(enrollment.get("student_id"), {})
        cls = class_map.get(enrollment.get("class_id"), {})
        opt = option_map.get(enrollment.get("option_id"), {})
        payment_results.append({
            **payment, "ticket_number": ticket_map.get(payment["id"]),
            "student": student, "class_name": cls.get("name"),
            "option_name": opt.get("name"), "fee_type_name": fee_type.get("name", "Frais"),
            "fee_type_code": fee_type.get("code"), "cashier_name": cashier_map.get(payment.get("cashier_id"), "Caissier"),
        })
    return {"school_years": years, "categories": categories, "classes": classes,
            "options": options, "fee_types": fee_types, "students": student_results,
            "payments": payment_results}


@app.get("/api/reports/summary")
def report_summary(context=Depends(require_roles("ADMINISTRATEUR", "PREFET", "PROMOTEUR"))):
    client = admin_client()
    years = client.table("school_years").select("*").order("start_date", desc=True).execute().data or []
    payments = client.table("payments").select("*").order("payment_date", desc=True).limit(2000).execute().data or []
    valid = [p for p in payments if p["status"] == "VALIDE"]
    total_usd = sum((payment_amount_usd(p) for p in valid), Decimal("0"))
    unconverted_legacy = sum(
        1 for p in valid
        if p.get("amount_usd") is None and str(p.get("currency", "")).strip().upper() != "USD"
    )
    return {"school_years":years,"valid_payments":len(valid),
            "revenue":[{"currency":"USD","amount":str(total_usd)}],
            "unconverted_legacy_payments":unconverted_legacy,
            "annulled_payments":len(payments)-len(valid)}



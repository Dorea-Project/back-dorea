"""Configuration applicative — chargée depuis l'environnement (.env).

Source de vérité unique pour les paramètres runtime. Aucune valeur secrète
n'est committée : `.env.example` documente les clés, `.env` (git-ignoré) porte
les valeurs locales.
"""

from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compte système « Dorea Platform » (Phase 0 P0.1) — UUID constant bien connu.
# Tracé comme `created_by`/`assigned_by` de toute genèse ; jamais authentifiable.
PLATFORM_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")

# Valeurs de développement à ne JAMAIS voir en prod (voir le validateur de durcissement).
_INSECURE_SECRETS = frozenset({"", "change-me-in-env", "change-me-service-token"})
_HARDENED_ENVS = frozenset({"staging", "production"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "dorea-mobile-api"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_prefix: str = "/api/mobile"
    backoffice_prefix: str = "/api/backoffice"

    # --- Backoffice (surface PWA) ---
    # Le provisionnement est un acte **Plateforme** (pas un Owner connecté) : protégé
    # par un jeton de service statique, en attendant l'auth session backoffice (S3/M2).
    platform_account_id: UUID = PLATFORM_ACCOUNT_ID
    backoffice_service_token: str = Field(
        default="change-me-service-token",
        description="Jeton de service pour les actes Plateforme (en-tête X-Service-Token).",
    )

    # --- Base de données PostgreSQL (schéma détenu par ce backend) ---
    # NB : ce backend lit, écrit et fait évoluer le schéma (migrations à venir).
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://dorea:dorea@localhost:5432/dorea",
        description="DSN asyncpg vers la base PostgreSQL partagée.",
    )
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Auth (M2) ---
    # Le « code secret » (PIN) est hashé en argon2id ; l'algo/paramètres doivent
    # rester cohérents entre les canaux d'auth (session backoffice + JWT mobile)
    # du même backend, qui écrit password_hash (faiblesse R5).
    jwt_secret: str = Field(
        default="change-me-in-env", description="Secret de signature JWT mobile."
    )
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600  # 1 h
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 j
    jwt_session_ttl_seconds: int = 60 * 60 * 12  # 12 h — session backoffice (cookie)
    # Cookie de session backoffice : `Secure` désactivé en local (HTTP), activé en prod.
    backoffice_cookie_secure: bool = False

    # --- OTP (vérification contact / nouvel appareil) ---
    otp_ttl_seconds: int = 600  # 10 min
    otp_code_length: int = 6
    # Acheminement réel de l'OTP. **Non configuré → repli sur le log** (dev inchangé).
    # Email (Owner / backoffice) via SMTP :
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    otp_email_from: str = "no-reply@dorea.church"
    # SMS (membre / mobile) via un fournisseur HTTP générique (Twilio / Africa's Talking…) :
    sms_provider_url: str | None = None  # endpoint POST du fournisseur
    sms_provider_token: str | None = None  # jeton d'API (Authorization: Bearer)
    sms_sender_id: str = "Dorea"

    # --- Messagerie (Infobip : WhatsApp + SMS de repli) ---
    # Un seul fournisseur pour les deux canaux, et **un seul numéro** pour toute
    # la plateforme (décision M1) : c'est Dorea qui parle, le nom de l'église
    # est une variable du modèle.
    # L'hôte est propre au compte Infobip (`xxxxx.api.infobip.com`).
    infobip_base_url: str | None = None
    infobip_api_key: str | None = None
    whatsapp_sender: str | None = None  # numéro émetteur, international sans `+`
    # Modèle approuvé pour les codes de connexion. Catégorie `authentication`
    # chez l'opérateur : la moins chère, et la seule autorisée à porter un code.
    whatsapp_otp_template: str = "dorea_otp"
    whatsapp_otp_language: str = "fr"
    # Le modèle porte-t-il un bouton « Copier le code » ? Les modèles
    # d'authentification de WhatsApp en ont presque toujours un, et sa variable
    # se renseigne à part du corps : l'oublier fait refuser l'envoi.
    whatsapp_otp_copy_code_button: bool = True
    # Secret partagé des webhooks Infobip. Ils ne signent pas leurs appels : ce
    # jeton est la seule barrière, à traiter comme un mot de passe. Non
    # configuré → les routes répondent 404 plutôt que d'accepter n'importe qui.
    messaging_webhook_token: str | None = None
    # Où le fournisseur nous rappelle. Posée sur chaque envoi plutôt que dans
    # leur portail : le compte est unique, les environnements ne le sont pas —
    # sans cela, les accusés du poste de développement partiraient en production.
    # Non configurée → aucun accusé, et l'on envoie à l'aveugle.
    messaging_notify_url: str | None = None

    @property
    def otp_email_enabled(self) -> bool:
        return self.smtp_host is not None

    @property
    def messaging_enabled(self) -> bool:
        """Vrai quand un vrai fournisseur répond — sinon, tout part au journal."""
        return (
            self.infobip_base_url is not None
            and self.infobip_api_key is not None
            and self.whatsapp_sender is not None
        )

    @property
    def otp_sms_enabled(self) -> bool:
        """L'OTP mobile a-t-il un acheminement réel ?

        WhatsApp d'abord, l'ancien fournisseur SMS générique ensuite : le temps
        de la bascule, les deux valent.
        """
        return self.messaging_enabled or self.sms_provider_url is not None

    # --- Média (images d'annonces) ---
    # Dev : stockage **local** servi en statique. Prod : S3/MinIO si `s3_endpoint_url` défini.
    media_dir: str = "media_uploads"  # répertoire local (dev)
    media_base_url: str = "/media"  # préfixe public des fichiers locaux
    media_max_bytes: int = 5 * 1024 * 1024  # 5 Mo par image
    sermon_max_bytes: int = 15 * 1024 * 1024  # 15 Mo par fichier de sermon (PDF/PPTX)
    media_allowed_types: list[str] = [
        "image/png", "image/jpeg", "image/webp", "image/gif", "video/mp4",
    ]
    # La vidéo de couverture d'un événement. Deux bornes, parce qu'un poids ne dit pas une durée :
    # trente secondes pèsent deux mégaoctets ou deux cents selon l'encodeur.
    media_video_max_bytes: int = 40 * 1024 * 1024
    media_video_max_seconds: int = 30
    s3_endpoint_url: str | None = None  # ex. "minio:9000" → bascule sur S3/MinIO
    s3_bucket: str = "dorea-media"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_secure: bool = True
    s3_public_base_url: str = ""  # base publique des objets S3 (CDN / endpoint)

    # --- Mission / IA (M9-1 : générateur de carte à partir d'un verset) ---
    # L'IA **retrouve la référence**, jamais le texte (zéro hallucination sur l'Écriture).
    # Moteur : Mistral (bon marché). Non configuré → repli mots-clés (le dev tourne sans clé).
    mistral_api_key: str | None = None  # clé API Mistral (moteur de reconnaissance)
    mistral_model: str = "mistral-small-latest"  # petit modèle : la tâche est simple, économe
    # Bible canonique : Louis Segond 1910 (domaine public). Fichier JSON { "Jean 3.16": "..." }.
    # Non configuré → poignée de versets embarqués (extrait dev, remplacé par le dataset complet).
    lsg_dataset_path: str | None = None
    # La Bible anglaise (World English Bible, domaine public) — `scripts/build_web_dataset.py`.
    # Absente, Mission sert l'extrait dev embarqué : la carte sort, avec huit versets seulement.
    web_dataset_path: str | None = None

    @property
    def verse_resolver_enabled(self) -> bool:
        return self.mistral_api_key is not None

    @property
    def sermon_digester_enabled(self) -> bool:
        # Partage la clé Mistral de Mission ; non configurée → repli déterministe (dev sans clé).
        return self.mistral_api_key is not None

    # --- Notifications push (transverse : Event / Annonces / RDV) ---
    # Fournisseur HTTP (FCM HTTP v1 ou passerelle générique). **Non configuré → repli sur le log**
    # (le dev tourne sans fournisseur ; une push ne casse jamais l'action qui la déclenche).
    push_provider_url: str | None = None  # endpoint POST du fournisseur
    push_provider_key: str | None = None  # jeton d'API (Authorization: Bearer)

    @property
    def push_enabled(self) -> bool:
        return self.push_provider_url is not None

    # --- CORS ---
    # Le client mobile Flutter est natif → le CORS navigateur ne s'y applique pas.
    # Ne compte que pour Flutter Web (si ciblé) et l'UI /docs. Le joker est **refusé en prod**
    # (voir `_enforce_prod_hardening`) ; en local il est toléré (dev).
    cors_origins: list[str] = ["*"]

    @model_validator(mode="after")
    def _enforce_prod_hardening(self) -> "Settings":
        """Échoue au démarrage en `staging`/`production` si une config faible subsiste.

        Neutralise le risque n°1 (secrets par défaut → forge de jeton / bypass admin) : l'app ne
        démarre pas avec un secret laissé au défaut. En `local`/`test` rien n'est imposé (dev)."""
        if self.environment in _HARDENED_ENVS:
            errs: list[str] = []
            if self.jwt_secret in _INSECURE_SECRETS or len(self.jwt_secret) < 32:
                errs.append("JWT_SECRET doit être un secret fort (≥ 32 caractères) propre à l'env.")
            if self.backoffice_service_token in _INSECURE_SECRETS:
                errs.append("BACKOFFICE_SERVICE_TOKEN doit être défini (pas la valeur par défaut).")
            if "*" in self.cors_origins:
                errs.append("CORS_ORIGINS doit être une liste blanche explicite (pas de joker).")
            if not self.backoffice_cookie_secure:
                errs.append("BACKOFFICE_COOKIE_SECURE doit être vrai hors HTTP local.")
            if errs:
                raise ValueError("Durcissement production requis : " + " ".join(errs))
        return self


@lru_cache
def get_settings() -> Settings:
    """Instance mise en cache — évite de relire l'environnement à chaque appel."""
    return Settings()

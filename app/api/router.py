"""Composition root HTTP — deux surfaces d'un même backend (spec §14).

- `api_router` : surface **mobile** (`/api/mobile/*`, front Flutter).
- `backoffice_router` : surface **backoffice** (`/api/backoffice/*`, front PWA Next.js).

Chaque contexte expose son propre routeur (`<contexte>/interface/router.py`) monté
ici sous son préfixe. `main.py` monte chaque surface sous son préfixe respectif.
"""

from fastapi import APIRouter

from app.api import system
from app.contexts.announcements.interface.backoffice_router import (
    router as backoffice_announcements_router,
)
from app.contexts.announcements.interface.mobile_router import (
    router as mobile_announcements_router,
)
from app.contexts.announcements.interface.platform_router import (
    router as platform_announcements_router,
)
from app.contexts.appointments.interface.backoffice_router import (
    router as backoffice_appointments_router,
)
from app.contexts.appointments.interface.mobile_router import (
    router as mobile_appointments_router,
)
from app.contexts.attendance.interface.backoffice_router import (
    router as backoffice_attendance_router,
)
from app.contexts.attendance.interface.mobile_router import router as mobile_attendance_router
from app.contexts.auth.interface.account_router import router as account_router
from app.contexts.auth.interface.backoffice_router import router as backoffice_auth_router
from app.contexts.auth.interface.router import router as auth_router
from app.contexts.billing.interface.mobile_router import router as mobile_billing_router
from app.contexts.events.interface.mobile_router import router as mobile_events_router
from app.contexts.events.interface.platform_router import router as platform_events_router
from app.contexts.events.interface.public_router import router as public_events_router
from app.contexts.groups.interface.backoffice_router import router as backoffice_groups_router
from app.contexts.groups.interface.mobile_router import router as mobile_groups_router
from app.contexts.iam.interface.backoffice_router import router as backoffice_iam_router
from app.contexts.iam.interface.router import router as iam_router
from app.contexts.media.interface.router import (
    backoffice_router as backoffice_media_router,
)
from app.contexts.media.interface.router import mobile_router as mobile_media_router
from app.contexts.mission.interface.mobile_router import router as mobile_mission_router
from app.contexts.mission.interface.public_router import router as public_mission_router
from app.contexts.notifications.interface.mobile_router import (
    router as mobile_notifications_router,
)
from app.contexts.notifications.interface.platform_router import (
    router as platform_notifications_router,
)
from app.contexts.sermon.interface.mobile_router import router as mobile_sermon_router
from app.contexts.tenant.interface.onboarding_router import (
    backoffice_router as onboarding_bo_router,
)
from app.contexts.tenant.interface.onboarding_router import (
    public_router as onboarding_public_router,
)
from app.contexts.tenant.interface.router import router as tenant_router
from app.contexts.urim.interface.mobile_router import router as mobile_urim_router
from app.contexts.urim.interface.platform_router import router as platform_urim_router
from app.contexts.watch.interface.backoffice_router import (
    router as backoffice_watch_router,
)
from app.contexts.watch.interface.mobile_router import router as mobile_watch_router
from app.contexts.watch.interface.platform_router import router as platform_watch_router

# --- Surface mobile ---
api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth_router, prefix="/auth", tags=["Membres · auth"])
api_router.include_router(account_router, prefix="/account", tags=["Membres · account"])
api_router.include_router(iam_router, prefix="/iam", tags=["Membres · iam"])
api_router.include_router(mobile_groups_router, prefix="/groups", tags=["Membres · groups"])
api_router.include_router(
    mobile_attendance_router, prefix="/attendance", tags=["Vie d'église · attendance"]
)
api_router.include_router(
    mobile_announcements_router, prefix="/announcements", tags=["Communication · announcements"]
)
api_router.include_router(mobile_media_router, tags=["Communication · media"])
api_router.include_router(mobile_mission_router, prefix="/mission", tags=["Vie d'église · mission"])
api_router.include_router(
    mobile_appointments_router, prefix="/appointments", tags=["Vie d'église · appointments"]
)
api_router.include_router(mobile_events_router, prefix="/events", tags=["Vie d'église · events"])
api_router.include_router(mobile_billing_router, prefix="/billing", tags=["Membres · billing"])
api_router.include_router(
    mobile_notifications_router, prefix="/notifications", tags=["Communication · notifications"]
)
api_router.include_router(mobile_sermon_router, prefix="/sermons", tags=["Vie d'église · sermons"])
# Urim — la **préparation**, distincte du sermon publié. Le quatrième mur (S29) sépare les
# deux modèles ; ce sont deux moments d'un même travail, pas deux vues d'une même table.
api_router.include_router(mobile_urim_router, prefix="/urim", tags=["Urim · préparation"])
# La première surface du moteur de veille. Elle n'expose pas la file des cas — seulement le
# geste qui l'alimente : quelqu'un pense à quelqu'un, et il l'écrit une fois.
api_router.include_router(mobile_watch_router, prefix="/watch", tags=["Veille · watch"])

# --- Surface backoffice ---
backoffice_router = APIRouter()
backoffice_router.include_router(
    backoffice_auth_router, prefix="/auth", tags=["Membres · auth (backoffice)"]
)
backoffice_router.include_router(tenant_router, tags=["Vie d'église · tenant (backoffice)"])
backoffice_router.include_router(
    backoffice_iam_router, prefix="/iam", tags=["Membres · iam (backoffice)"]
)
backoffice_router.include_router(backoffice_groups_router, tags=["Membres · groups (backoffice)"])
backoffice_router.include_router(
    backoffice_attendance_router,
    prefix="/attendance",
    tags=["Vie d'église · attendance (backoffice)"],
)
# Le rodage : ce que Dorea aurait signalé, et la décision de la laisser parler.
backoffice_router.include_router(backoffice_watch_router, tags=["Veille · watch (backoffice)"])
backoffice_router.include_router(
    backoffice_announcements_router,
    prefix="/announcements",
    tags=["Communication · announcements (backoffice)"],
)
backoffice_router.include_router(
    backoffice_media_router, tags=["Communication · media (backoffice)"]
)
backoffice_router.include_router(
    backoffice_appointments_router,
    prefix="/appointments",
    tags=["Vie d'église · appointments (backoffice)"],
)
backoffice_router.include_router(
    onboarding_bo_router, prefix="/onboarding", tags=["Vie d'église · onboarding (backoffice)"]
)
# Annonces Dorea (admin central) — gardées par le jeton de service Plateforme.
backoffice_router.include_router(
    platform_announcements_router,
    prefix="/platform",
    tags=["Communication · announcements (Dorea)"],
)
# Modération des événements (retrait) — même garde Plateforme.
backoffice_router.include_router(
    platform_events_router, prefix="/platform", tags=["Vie d'église · events (modération)"]
)
# Dispatcher du fan-out asynchrone (cron externe) — même garde Plateforme.
backoffice_router.include_router(
    platform_notifications_router, prefix="/platform", tags=["Communication · notifications (cron)"]
)
# La curation d'Urim — **Plateforme**, pas tenant : le corpus est global, aucune table ne
# porte de `church_id`, et curer change ce que TOUTES les églises lisent.
backoffice_router.include_router(
    platform_urim_router, prefix="/platform", tags=["Urim · curation (plateforme)"]
)
# Cadence du moteur de veille (cron externe) — escalade + garde-fou anti-déversoir.
backoffice_router.include_router(
    platform_watch_router, prefix="/platform", tags=["Veille · watch (cron)"]
)

# --- Surface publique (onboarding aspirant Owner, sans auth) ---
public_router = APIRouter()
public_router.include_router(
    onboarding_public_router, prefix="/onboarding", tags=["Vie d'église · onboarding (public)"]
)
# Carte d'invitation missionnaire — publique (le code EST l'entrée, pas d'auth).
public_router.include_router(
    public_mission_router, prefix="/mission", tags=["Vie d'église · mission (public)"]
)
# La carte d'un événement : la contrepartie de la cadence de publication. Ce qui est rationné est
# la notification, jamais la diffusion — le lien se partage hors de Dorea autant qu'on veut.
public_router.include_router(public_events_router, tags=["Vie d'église · events (public)"])

# Contextes à brancher au fil des modules :
#   from app.contexts.attendance.interface.router import router as attendance_router  # M6
#   api_router.include_router(
#       attendance_router, prefix="/attendance", tags=["Vie d'église · attendance"]
#   )

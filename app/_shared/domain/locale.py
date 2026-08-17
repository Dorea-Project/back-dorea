"""La langue dans laquelle **Dorea** parle — un objet-valeur, et une seule façon de la lire.

Rappel de la frontière (`docs/Chantier_Bilingue_2026-08-16.md` §0) : *Dorea traduit ce que Dorea
dit, jamais ce qu'un humain a écrit.* `Locale` n'habille donc que la voix du produit — une push,
un code de vérification, la consigne donnée à un modèle. Le titre d'une annonce, le mot du
pasteur qui décline un rendez-vous, le texte d'un sermon ne passent jamais par ici.

Ce module vit dans `_shared` parce qu'il ne dépend d'aucun contexte : le catalogue de messages,
la messagerie, Mission et Sermon le liront tous sans se traîner l'IAM. La *résolution* (à qui
appartient quelle langue), elle, est un fait de l'IAM et vit là-bas — voir `LocaleResolver`.
"""

from __future__ import annotations

from enum import StrEnum


class Locale(StrEnum):
    """Les langues que Dorea parle. Les *valeurs* sont la source de vérité — elles vont en base
    (`accounts.language`, `tenants.language`), chez le fournisseur WhatsApp, et dans le
    catalogue. On peut en ajouter une ; on ne renomme jamais celles-ci."""

    FR = "fr"
    EN = "en"


#: La langue de repli. Pas un choix esthétique : Dorea est né en Côte d'Ivoire et la quasi-
#: totalité des lignes existantes portent déjà `'fr'` en base.
DEFAULT_LOCALE = Locale.FR


def parse_locale(raw: str | None) -> Locale | None:
    """Lit une langue déclarée — **`None` quand ce n'est pas une langue que Dorea parle**.

    ⚠️ `None` plutôt que `DEFAULT_LOCALE`, et c'est tout l'intérêt de cette fonction. La
    résolution enchaîne *personne → église → défaut* : si une valeur illisible renvoyait déjà
    le défaut, la chaîne s'arrêterait au premier maillon et l'église ne serait jamais consultée.
    Un membre dont le champ vaut `''` ou `'es'` doit hériter de la langue de son église, pas
    tomber directement sur le français.

    Tolérante à l'entrée, parce que la valeur vient d'un client mobile, d'un en-tête HTTP ou
    d'une ligne ancienne : `'FR'`, `' fr '`, `'fr-CI'`, `'en_GB'` désignent tous une langue que
    l'on sait parler. On ne garde que la sous-étiquette primaire — Dorea distingue les langues,
    pas les régions : un anglophone d'Abidjan et un anglophone de Londres lisent le même
    « Appointment confirmed ».
    """
    if raw is None:
        return None
    primary = raw.strip().lower().replace("_", "-").split("-")[0]
    try:
        return Locale(primary)
    except ValueError:
        return None


def coerce_locale(raw: str | None) -> Locale:
    """Comme `parse_locale`, mais rend toujours une langue — pour les bouts de chaîne où il n'y
    a plus rien derrière à consulter (le dernier maillon, ou une entrée sans contexte)."""
    return parse_locale(raw) or DEFAULT_LOCALE

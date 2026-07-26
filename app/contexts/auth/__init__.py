"""Contexte borné Auth (M2) — authentification mobile.

Prouve *qui* est la personne (login téléphone + code secret → JWT), distinct de
l'IAM qui gère *ce qu'elle a le droit de faire*. Ne porte que le **canal mobile**
(JWT) ; le canal backoffice (session, owner/pasteur) est l'autre surface d'auth
du même backend (spec §14).
"""

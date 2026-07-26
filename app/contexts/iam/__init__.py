"""Contexte borné IAM (M1) — Compte · Appartenance · Attribution de rôle.

Sur la surface mobile (`/api/mobile`), la lecture est volontairement réduite
(M1 §9) : essentiellement statut d'appartenance et rôles actifs. Les commandes
IAM (création de compte, transitions de statut, attribution de rôle…) relèvent
de la surface backoffice (`/api/backoffice`) du même backend.
"""

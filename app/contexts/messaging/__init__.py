"""Contexte `messaging` — acheminer un message vers une personne.

Il possède les **canaux opérateur** (WhatsApp, SMS), les modèles approuvés et
l'état d'acheminement. Il ne possède jamais la *raison* d'écrire : ses appelants
lui passent une intention, il choisit comment elle part.

Deux portes, et pas une de plus (voir `docs/Messagerie_Architecture.md`) :

- `OtpSender` — le port d'`auth`, inchangé, branché ici sur la voie
  transactionnelle ;
- `MemberMessenger` — la diffusion, pour l'invitation à un `Event` (étape 3).

Pas de bus : la spec §14 a tranché, les faits métier sont tirés, jamais publiés.
"""

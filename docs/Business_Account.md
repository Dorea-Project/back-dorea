# Compte Business — le tier de la personne (source de vérité)

> Établi par cas d'usage (2026-07-18), dans le sillage d'Event. Contexte `billing`. **Le premier
> germe de monétisation de Dorea** — gardé, mais **pas encore facturé**.

---

## 1. La philosophie

Rayonner au-delà de son église est un **acte institutionnel** (cf. `docs/Event_Model.md` §2) : ça
demande un **compte Business**. Décision figée : le tier appartient à la **personne** (l'Owner / le
membre qui publie), pas à l'église. Il s'active en **enregistrant une carte prépayée Visa** — et
**pour l'instant, enregistrer la carte suffit** (aucun prélèvement). L'échafaudage de facturation
(un vrai PSP, la tokenisation, les prélèvements) viendra ; le **modèle et la porte** existent déjà.

## 2. Le modèle

- **`BusinessAccount`** (un par compte, clé `account_id`) : porte au plus **une** `PaymentCard`.
  `is_business` = une carte est enregistrée. Pas de compte = tier **gratuit** (l'état par défaut).
- **`PaymentCard`** (objet-valeur) : `brand`, `last4`, `prepaid`, `exp_month`/`exp_year`,
  `provider_token?`, `added_at`. `validate()` exige **`brand == "visa"` ET `prepaid`** (sinon
  `PrepaidVisaRequiredError` 422) + 4 derniers chiffres valides (`InvalidPaymentCardError` 422).
- **Sécurité (PCI)** : on ne reçoit ni ne stocke **jamais** le numéro complet (PAN). Seulement des
  données non sensibles (marque, 4 derniers, expiration) et un jeton d'un futur PSP. Le client
  tokenise sa carte ; le backend n'enregistre que la référence.

## 3. Les surfaces (mobile — la personne gère son compte)

- `GET /api/mobile/billing/status` → `{tier, is_business, card_brand, card_last4, card_prepaid}`.
- `POST /api/mobile/billing/card` (enregistrer → **Business**) — corps : marque, 4 derniers,
  prépayée, expiration, jeton optionnel.
- `POST /api/mobile/billing/card/remove` (retirer → **gratuit**, idempotent).

## 4. La porte (intégration Event)

Le contexte Event lit ce module par le port **`BusinessTierPort`** (adaptateur
`BillingBusinessTierAdapter`). `PublishEvent` : publier en portée **dénomination/plateforme** exige
`is_business(auteur)` — sinon `WiderReachRequiresBusinessError`. La portée **église** reste
gratuite pour tous. Et le **fil visible** (`ListVisibleEvents`) fait remonter : mon église + les
événements *dénomination* de ma dénomination + les événements *plateforme* de toute la plateforme.

## 5. Livré

Contexte `app/contexts/billing/`. Agrégat `BusinessAccount` + `PaymentCard`. Commandes
`AddPaymentCard` / `RemovePaymentCard` ; requête `GetBusinessStatus`. Table `business_accounts`
(migration `ff60718293a4`, **à appliquer quand Docker up**). Port `BusinessTierPort` + adaptateur
côté Event ; fil élargi `ListVisibleEvents`. **8 tests billing** (+ la porte testée côté Event).
Sans IA, **sans facturation** (le prélèvement viendra).

## 6. Reporté / à venir

- **Facturation réelle** : un PSP (tokenisation, prélèvements récurrents, échéances), le passage de
  « carte enregistrée = Business » à « abonnement actif payé = Business ».
- **Modération** de la diffusion élargie (dénomination/plateforme), notifications push des
  événements qui m'atteignent, tableau de bord de rayonnement *rempli* (les « vus par dénomination »
  prennent leur sens dès qu'un événement franchit les églises).

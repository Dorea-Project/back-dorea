# Abonnement du Tenant — note de design (église + annexes)

**Statut :** note de design (non implémentée). Décision produit posée le 2026-07-23.
**Portée :** l'abonnement payant d'une **église** (tenant), déterminé par sa taille et
ses annexes. À ne pas confondre avec le `BusinessAccount` d'une **personne**
(module Billing existant, tier `free`/`business` pour *Event*).

> Une église rejoint Dorea et souscrit un abonnement. Le prix dépend de deux
> choses : **combien de fidèles** elle déclare et **combien d'annexes** elle opère.
> Les annexes étant des **églises semi-autonomes** (tenants enfants, cf.
> `M0 §4` filiation), l'abonnement du **principal** porte la **famille**.

---

## 1. Les offres (source de vérité produit)

| Offre | Annexes | Membres (taille-famille) | Mensuel (FCFA) | Annuel (FCFA) |
| :-- | :-- | :-- | --: | --: |
| **Standard** | 0 | < 501 | 12 500 | 150 000 |
| **Professionnel** | 1 | < 1 001 | 17 500 | 210 000 |
| **Premium** | 2 et + | 1 001 et + | 35 000 | 420 000 |

**Observation** : l'annuel vaut exactement 12 × le mensuel (150 000 = 12 × 12 500,
etc.) — **aucune remise annuelle** dans ces chiffres. À confirmer (l'annuel est-il
une simple facilité de paiement, ou une remise viendra-t-elle ?). → *Décision D5*.

---

## 2. Le principe fondateur : facturer la **taille déclarée**, jamais l'effectif réel

L'assiette de facturation est `estimated_member_count` — la taille **auto-déclarée**
à l'inscription (« ≠ effectif réel », déjà dans l'agrégat `Tenant`). C'est délibéré :

- Facturer l'**effectif réel** (nombre d'appartenances) serait **pervers** : une
  église sous-enrôlerait pour payer moins, ce qui corromprait la donnée pastorale
  (le cœur de Dorea). Non négociable.
- La taille **déclarée** est honnête, stable, et **re-déclarable au renouvellement**.

**Corollaire annexes** : chaque annexe étant son propre tenant avec **sa** taille
déclarée, la **taille-famille se calcule**, elle ne se devine pas :

```
taille_famille(principal) = Σ estimated_member_count
                            sur { principal } ∪ { descendants via parent_id }
```

Le principal ne saisit donc **pas** un total inventé de tous ses fidèles : il déclare
**sa** taille, et le total se **remplit** à mesure que les annexes sont onboardées
« une par une, après » (cf. §5).

---

## 3. La règle de tarification (dérivée des offres)

Deux axes indépendants, chacun donnant un tier ; le tier facturé est le **plus élevé
des deux** :

**Axe taille** (taille-famille, bornes lues sur la table) :
| Taille-famille | Tier |
| :-- | :-- |
| 1 – 500 | Standard |
| 501 – 1 000 | Professionnel |
| 1 001 et + | Premium |

**Axe annexes** (nombre d'annexes actives dans la famille) :
| Annexes | Tier |
| :-- | :-- |
| 0 | Standard |
| 1 | Professionnel |
| 2 et + | Premium |

**Règle** :
```
tier_facturé = max(tier_par_taille, tier_par_annexes)      # Standard < Professionnel < Premium
```

**Vérification contre la table §1** :
- Standard : max(Standard, Standard) = Standard ✓
- Professionnel : 1 annexe (Pro) et ≤ 1 000 (≤ Pro) → max = Professionnel ✓
- Premium : 2+ annexes (Premium) et 1 001+ (Premium) → max = Premium ✓

**Cas mixtes** (que la table n'énumère pas, que la règle tranche) :
- 0 annexe mais 800 membres → **Professionnel** (poussé par la taille).
- 3 annexes mais 400 membres → **Premium** (poussé par les annexes).

→ *Décision D1* : confirmer que Premium se déclenche par **l'un OU l'autre** axe
(règle `max`), et non « 2+ annexes **ET** 1 001+ membres » simultanément. La règle
`max` maximise le revenu et reste logique (« on paie ce qu'on dépasse »).

---

## 4. Ce que l'inscription capture (et ce qu'elle ne capture pas)

À l'enregistrement du **principal** (`POST /backoffice/tenants`, acte Plateforme) :

| Champ | Nature | Usage |
| :-- | :-- | :-- |
| `estimated_member_count` | **existant** | assiette taille du principal |
| `operates_annexes: bool` | **nouveau** | (1) indice de **plan** attendu ; (2) arme l'attente des onboardings d'annexes ; **informatif**, pas facturé directement |
| `billing_period` | **nouveau** | `monthly` / `annual` — le seul **choix** de l'église |

**Le tier n'est pas choisi, il est *dérivé*.** Une église de 1 500 membres ne peut
pas « prendre Standard ». L'église choisit uniquement la **périodicité** ; le **tier**
est calculé par la règle §3 sur l'état réel de la famille.

Le drapeau `operates_annexes` sert à l'accueil (« combien d'annexes prévoyez-vous ? »)
et au choix du plan attendu — mais le **tier facturé** suit toujours les annexes
**réellement onboardées**, pas la déclaration d'intention.

---

## 5. Cycle de vie : un tier **dynamique**, ré-évalué

Le tier n'est pas figé à l'inscription — la famille grandit :

Ré-évaluation déclenchée quand :
- une **annexe est ajoutée** (nouveau tenant enfant) ou **retirée / clôturée** ;
- une **taille déclarée change** (principal ou annexe) ;
- **au renouvellement** de période.

Séquence type :
```
1. Principal s'enregistre : 300 membres, operates_annexes=oui
     → taille-famille=300, annexes=0 → tier = Standard
2. Dorea onboarde l'annexe A (250 membres, tenant enfant, parent_id=principal)
     → taille-famille=550, annexes=1 → tier = Professionnel   (ré-évalué)
3. Dorea onboarde l'annexe B (600 membres)
     → taille-famille=1150, annexes=2 → tier = Premium         (ré-évalué)
```

→ *Décision D2* : à la **hausse** (upgrade), applique-t-on un **prorata** immédiat,
ou l'upgrade prend-il effet au prochain cycle ? Idem à la **baisse** (downgrade :
prend effet au renouvellement, jamais de remboursement — recommandé).

---

## 6. Architecture proposée

Un **nouveau concept borné, scopé au tenant** — ne PAS surcharger le module `billing`
de personne. Deux options :

- **(a)** un petit **module `subscription`** (`app/contexts/subscription/`), agrégat
  `TenantSubscription(tenant_id, tier, period, started_at, renews_at, status)` ;
- **(b)** une **extension du contexte `tenant`** (l'abonnement comme facette du tenant).

Recommandation : **(a)** — l'abonnement a sa propre vie (tiers, périodes, renouvellement,
ré-évaluation, encaissement) et mérite son contexte. Il **lit** la famille via un
**port** exposé par Tenant :

```
port FamilySizePort (fourni par le contexte tenant) :
    - family_member_count(principal_id) -> int      # Σ sur l'arbre parent_id
    - active_annexe_count(principal_id) -> int       # nb d'enfants actifs
```

> ✅ **Ce port est déjà calculé — 2026-08-03.** `GetTenantFamily` (contexte `tenant`) rend
> `family_member_count` **et** `active_annexe_count`, exposés par
> `GET /api/backoffice/tenants/{id}/family`. Le module `subscription` n'aura qu'à consommer
> cette query (ou un port qui l'enveloppe) : **le calcul de l'assiette existe, il ne sera pas
> dupliqué**. Rappel des règles déjà tenues : tailles **déclarées** (jamais l'effectif réel),
> **enfants directs** (filiation plate), **annexes suspendues exclues** du décompte.

Le calcul du tier (règle §3) vit dans le domaine `subscription` ; la persistance
d'une table `tenant_subscriptions`.

**Encaissement** : aligné sur la philosophie Billing existante — d'abord **enregistrer
le plan** (tier + période + moyen de paiement), la **facturation réelle** (PSP,
prélèvements FCFA — Mobile Money ?) vient ensuite. → *Décision D3* : quel PSP /
canal (Mobile Money vs carte) pour le marché FCFA ?

---

## 7. Ce que ça suppose côté Tenant (prérequis)

L'abonnement famille repose sur une filiation **fiable** :

1. **Valider `parent_id` au provisioning** — la mère doit **exister et être active**
   (trou identifié en live : une annexe orpheline sur un `parent_id` fantôme est
   aujourd'hui acceptée en `201`). Sans ça, la somme sur l'arbre est fausse.
2. **Endpoint dédié** `POST /tenants/{parent_id}/annexes` (acte **Plateforme** —
   décidé) qui réutilise le cœur genesis, `parent_id` venant du chemin et validé.
3. **Lecture de la famille** `GET /tenants/{id}/annexes` pour piloter la ré-évaluation
   et l'affichage du forfait.
4. **Profondeur de filiation** : annexe-d'annexe permise ou arbre **plat** en V1 ?
   L'axe « nombre d'annexes » compte-t-il les **enfants directs** ou **tous les
   descendants** ? → *Décision D4* (recommandé V1 : plat, enfants directs).

---

## 7bis. Remises & promotions — **données gérées par l'admin** (décidé 2026-07-23)

Les **tiers et seuils** (Standard/Pro/Premium, bornes 501/1 001, nb d'annexes, prix de base) restent
**définis en code** — c'est le produit, stable. En revanche les **remises et promotions** sont de la
**donnée éditable depuis le backoffice** par l'admin — pas de prix en dur, pas de déploiement pour lancer
une promo.

**Modèle `Promotion`** (dans le module `subscription`) :
- `code` (ex. `RENTREE2026`), `kind` (`percent` | `fixed_amount`), `value`, `currency` (FCFA) ;
- `valid_from` / `valid_until`, `applicable_tiers[]` (ou tous), `applicable_periods[]` (mensuel/annuel) ;
- `stackable` (cumulable ou non), `max_redemptions` / `redeemed_count`, `active`.

**Calcul du prix facturé** :
```
prix_dû = prix_tier(tier, période) − remise(promotion_active)      # borné à ≥ 0
```
La promotion **ne touche jamais le tier** (qui reste dérivé de la taille + annexes, §3) — uniquement le
**montant**. Une promo invalide/expirée/épuisée est ignorée silencieusement.

**Surface backoffice** (admin, `X-Service-Token` ou rôle Plateforme) :
`POST/GET/PATCH/DELETE /api/backoffice/platform/promotions` — CRUD complet, plus l'historique des
`redemptions`.

→ *Décision D7* : les **offres elles-mêmes** (tiers/seuils/prix de base) doivent-elles aussi devenir
éditables par l'admin, ou seules les promos ? Recommandé : **offres en code** (rares, structurantes),
**promos en donnée** (fréquentes, marketing). À revisiter si le besoin de A/B pricing apparaît.

---

## 8. Décisions ouvertes (à trancher)

| # | Décision | Recommandation |
| :-- | :-- | :-- |
| **D1** | Premium = `max` (l'un OU l'autre axe) vs « ET » simultané | `max` (l'un OU l'autre) |
| **D2** | Upgrade au prorata immédiat vs prochain cycle ; downgrade au renouvellement | Upgrade prochain cycle, downgrade au renouvellement |
| **D3** | PSP / canal d'encaissement FCFA (Mobile Money vs carte) | à cadrer |
| **D4** | Profondeur de filiation + « annexes » = enfants directs vs tous descendants | ✅ **tranché (2026-07-23)** : filiation **plate** en V1, « annexes » = enfants directs (cf. M0 §4.1) |
| **D5** | Remise annuelle (aujourd'hui annuel = 12 × mensuel, 0 remise) | confirmer l'intention |
| **D6** | Que se passe-t-il si l'abonnement **expire** ? (lecture seule ? gel ? grâce ?) | période de grâce, puis lecture seule |
| **D7** | Offres (tiers/seuils/prix) éditables par l'admin, ou seules les promos ? (cf. §7bis) | offres en code, promos en donnée |

---

## 9. Ce qu'on ne fait **pas**

- On ne facture **pas** sur l'effectif réel (§2).
- On ne surcharge **pas** le `BusinessAccount` de personne (§6).
- Le principal ne **choisit pas** son tier — il est dérivé (§4).
- On ne demande **pas** un total de fidèles inventé — il se calcule (§2).

---

*Note de design — fait foi pour la décision, pas pour l'implémentation. À promouvoir
en spec `M-*` une fois les décisions D1–D6 tranchées.*

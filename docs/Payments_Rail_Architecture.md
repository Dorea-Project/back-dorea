# DOREA — ARCHITECTURE DU RAIL DE PAIEMENT

> **État : conception. Aucune ligne écrite.**
> Ce document est le contrat qu'on se donne avant de coder. Il fixe les frontières, les refus, et
> l'ordre de construction.

**Hypothèses de nommage retenues** (les deux noms du document d'origine sont déjà pris dans le
repo) : le moteur de tarification s'appellera **`pricing`** et non `billing` — `billing` désigne
déjà le tier Business d'une personne. La billetterie s'appellera **`ticketing`** et non `events` —
`events` désigne déjà le happening publié d'une église.

---

## 0. Le renversement de cadrage

> On ne construit pas un système de paiement. On construit un **système d'observation d'un monde
> extérieur peu fiable**.

L'argent ne bouge pas dans notre base : il bouge chez Wave et Orange. Le système ne *décide*
jamais qu'un paiement a réussi — il **constate**, à partir de sources contradictoires et décalées.

Cela a une conséquence de méthode, et elle gouverne tout ce qui suit :

> **La réconciliation se construit en premier.** Le chemin heureux, c'est trois jours de travail.
> C'est ailleurs qu'on perd de l'argent.

C'est exactement la discipline du moteur de veille, transposée : un journal append-only fait foi,
tout le reste est une projection, et **aucune anomalie n'est absorbée en silence**.

---

## 1. Trois contextes, et ce que chacun ignore

| Contexte | Répond à | Ne sait rien de |
|---|---|---|
| **`payments`** | *L'argent a-t-il bougé ?* | Ce qu'est un billet, une cotisation, un abonnement |
| **`pricing`** | *Combien doit-on demander ?* | Comment l'argent circule |
| **`treasury`** | *Qu'est-ce que ça donne dans les livres ?* | Les fournisseurs |

Le mode d'échec classique est connu : le module démarre comme rail, absorbe de la logique métier
(*« si c'est un billet alors… »*), et devient le module-dieu dont tout dépend.

> **Le spaghetti arrive par l'interprétation, pas par la mutualisation.**

`treasury` n'est pas au périmètre de la phase 1. Il est nommé ici pour que personne ne soit tenté
de mettre de la comptabilité dans `payments`.

---

## 2. Arborescence

Conventions du repo, à l'identique de `watch` :

```
app/contexts/payments/
├── domain/
│   ├── intent.py          # PaymentIntent — l'agrégat, la machine à états
│   ├── events.py          # PaymentEvent — l'observation, immuable
│   ├── discrepancy.py     # Discrepancy — le cas d'argent
│   ├── fees.py            # FeePolicy, FeeLine, l'arrondi déterministe
│   ├── enums.py           # IntentStatus, EventSource, DiscrepancyKind, Provider
│   └── errors.py          # PAY_*
├── application/
│   ├── ports.py           # ProviderGateway, StatementSource, OutboxWriter
│   ├── create_intent.py   # la seule porte d'entrée pour un contexte appelant
│   ├── converge.py        # observer → transitionner OU ouvrir un écart
│   ├── poll_pending.py
│   ├── reconcile_daily.py
│   └── discrepancies.py   # lister, s'attribuer, fermer
├── infrastructure/
│   ├── persistence/{models.py, intents.py, events.py, discrepancies.py, outbox.py}
│   └── providers/{fake.py, wave.py, orange.py}
└── interface/
    ├── dependencies.py
    ├── webhook_router.py     # public, signé
    ├── platform_router.py    # les trois crons (jeton de service)
    └── backoffice_router.py  # la file d'écarts
```

**`app/_shared/domain/money.py`** — nouveau, et partagé : `payments`, `pricing`, `collections` et
`ticketing` en ont tous besoin. Voir §7.

---

## 3. Le modèle

### `PaymentIntent` — notre vérité

```python
id, tenant_id
amount: Money                 # entier, jamais de flottant
payer_msisdn
beneficiary                   # compte marchand DE L'ÉGLISE
purpose_ref: (context, id)    # OPAQUE — jamais interprété
fee_lines: list[FeeLine]      # figées à la création
provider, provider_ref?
status: IntentStatus          # PROJECTION du journal
idempotency_key               # fournie par l'appelant
created_at
```

### `PaymentEvent` — append-only

```python
intent_id, source: {WEBHOOK, POLL, STATEMENT}
provider_event_id?            # déduplication
observed_status, observed_amount
raw_payload                   # tel quel, jamais normalisé à l'écriture
observed_at
```

### `Discrepancy` — le cas

```python
intent_id?, kind: DiscrepancyKind
owner_id, reason_text         # immuable après ouverture
status: {OPEN, INVESTIGATING, CLOSED}
closed_by, outcome, closed_at
```

**Aucun montant n'est jamais mis à jour.** Le statut d'une intention est une **projection** du
journal d'événements — au même titre que le `Signal` est une projection du ledger de veille. On
peut l'effacer et le reconstruire ; la vérité est la suite d'observations.

Ce n'est pas un raffinement théorique : le jour où un fournisseur nous enverra une séquence qu'on
n'avait pas prévue, on rejouera le journal avec une règle corrigée au lieu de réparer des lignes
à la main.

---

## 4. La machine à états

```
INITIATED → PENDING → SUCCEEDED | FAILED | EXPIRED
                          (états ABSORBANTS)
```

> **Toute observation contredisant un état terminal produit un écart, jamais une transition.**

C'est l'invariant le plus violé dans la nature et le plus coûteux : c'est lui qui produit les
doubles comptages. Un webhook « réussi » arrivant sur une intention `EXPIRED` n'est pas une
correction — c'est une anomalie qu'un humain doit trancher.

La règle vit **dans les transitions** de l'agrégat, pas dans une validation que la couche
applicative pense à appeler. Une transition qui n'existe pas ne peut pas être tentée. Même
dispositif que `Signal._move_to`, et pour la même raison.

### L'algorithme de convergence

```python
def converge(intent, event):
    append(event)                                   # toujours, sans condition
    if intent.status in TERMINAL:
        if event.observed_status != intent.status:
            open_discrepancy(intent, CONTRADICTS_TERMINAL)
        return
    if event.observed_amount != intent.amount:
        open_discrepancy(intent, AMOUNT_MISMATCH)
        return
    transition(intent, event.observed_status)
```

`append` d'abord, **sans condition** : on écrit ce qu'on a vu avant de décider ce qu'on en pense.
Une observation qu'on jette parce qu'elle dérange est une observation qu'on ne pourra pas rejouer.

---

## 5. Les trois canaux d'observation

| Canal | Vitesse | Confiance | Rôle |
|---|---|---|---|
| **Webhook** | Immédiat | **Faible** | Déclenche |
| **Interrogation de statut** | Minutes | Moyenne | Confirme |
| **Relevé fournisseur** | Quotidien | **Autoritaire** | Arbitre |

Il faut les trois. Un système qui ne fait confiance qu'aux webhooks perd des paiements.

### Idempotence aux trois frontières

| Frontière | Clé | Garantie |
|---|---|---|
| Client → API | `Idempotency-Key` de l'appelant | index unique `(tenant_id, idempotency_key)` |
| API → fournisseur | notre référence d'intention, stable et rejouable | l'`intent_id` voyage |
| **Fournisseur → nous** | `provider_event_id` | **index unique partiel** `WHERE provider_event_id IS NOT NULL` |

La troisième est celle que tout le monde oublie, et les webhooks arrivent en double, dans le
désordre, ou pas du tout. L'index partiel est nécessaire parce que `POLL` et `STATEMENT` n'ont pas
d'identifiant fournisseur — et en SQL, `NULL != NULL` (le piège déjà rencontré sur
`watch_group_type_policies`).

---

## 6. L'écart est un cas

> Le modèle du `Signal`, appliqué à l'argent : un propriétaire, une raison stockée, et une file
> qui doit pouvoir se vider.

| `DiscrepancyKind` | Situation |
|---|---|
| `CONTRADICTS_TERMINAL` | Webhook « réussi » sur une intention expirée |
| `AMOUNT_MISMATCH` | Le montant observé diffère |
| `ORPHAN_AT_PROVIDER` | Transaction au relevé, sans intention locale |
| `STUCK_PENDING` | `PENDING` depuis plus de N heures |
| `MISSING_AT_PROVIDER` | Intention `SUCCEEDED` absente du relevé |

Trois règles reprises telles quelles de `watch` :

- **aucune correction automatique silencieuse** — le système ne « répare » jamais un écart
  d'argent, il l'expose ;
- **fermeture par acte humain**, avec issue et motif ;
- **raison immuable** après ouverture.

**On réutilise la discipline, jamais la classe.** Importer `Signal` dans `payments` coupleraient
la trésorerie au moteur de veille, et l'invariant « aucune donnée financière n'entre dans la
veille » deviendrait une question d'attention plutôt qu'une propriété du code. Le grillage du
ledger (`FORBIDDEN_KIND_PATTERNS`, famille *financier*) refuse déjà `payment`, `amount`, `fee` à
l'enregistrement d'une source — il faut que ce refus reste sans objet.

---

## 7. L'argent — `app/_shared/domain/money.py`

**Le franc CFA n'a pas de sous-unité.** XOF est à zéro décimale.

```python
@dataclass(frozen=True)
class Money:
    amount: int          # entier, TOUJOURS. Jamais de float, jamais de Decimal implicite
    currency: str        # « XOF »
```

Deux pièges, et ils coûtent cher :

- **le « montant × 100 »** qui traîne dans toutes les bibliothèques de paiement. Une erreur de
  facteur 100 sur une convention est irrattrapable. Le type l'interdit par construction ;
- **la devise appartient au devis**, jamais à une configuration globale.

### Les frais — déclarés par l'appelant

> **Le contexte appelant déclare la politique de frais en créant l'intention. Le rail applique ce
> qu'on lui dit — il ne décide jamais.**

```python
FeePolicy: kind ∈ {NONE, PERCENT, FLAT}, value, floor_amount?, rounding = FLOOR
```

`ticketing` crée son intention avec `PERCENT 0.75`. `collections` crée la sienne avec `NONE`. **Le
rail ne sait toujours pas ce qu'est un billet.**

- Les frais sont une **ligne du journal**, écrite à la création, jamais recalculée. Il faudra
  répondre exactement à *« combien Dorea nous a prélevé l'an dernier ? »*
- **Arrondi déterministe**, toujours dans le même sens, reliquat journalisé. 0,75 % de 5 000 XOF
  fait 37,5 : ce demi-franc va quelque part **par décision**, pas par hasard.
- **Un plancher.** En dessous d'un montant, pas de frais : 0,75 % de 500 XOF ne couvre rien et
  fait passer pour mesquin.

---

## 8. Les ports

Le rail ne connaît aucun fournisseur. Il demande, un adaptateur répond.

```python
class ProviderGateway(ABC):
    async def initiate(self, intent) -> ProviderRef: ...
    async def fetch_status(self, provider_ref) -> Observation: ...

class StatementSource(ABC):
    async def lines_for(self, day) -> list[StatementLine]: ...

class OutboxWriter(ABC):
    async def enqueue(self, event) -> None: ...
```

`FakeProvider` est un adaptateur de **première classe**, pas un bouchon de test : c'est lui qui
permet de construire la réconciliation avant d'avoir un contrat signé (§11).

---

## 9. Sans broker — le patron existant

```
Transaction :  changement d'état  +  écriture dans `payments_outbox`   → atomique
```

Trois crons one-shot idempotents, exactement le patron déjà prouvé trois fois dans le repo
(`dispatch_notifications`, `relay_appointments`, `watch_concerns`) :

| Cron | Rôle |
|---|---|
| `drain_outbox` | publie les événements de domaine aux contextes appelants |
| `poll_pending` | interroge les intentions `PENDING` |
| `reconcile_daily` | rapproche le relevé, **ouvre des écarts** |

> `reconcile_daily` ne corrige jamais. Il produit des écarts.

Chacun est joignable par une route plateforme gardée par le jeton de service, comme
`POST /platform/watch/run` — deux chemins, une implémentation.

**Le garde anti-orage s'applique ici aussi.** Si un cron ne tourne pas pendant trois jours, la
file d'écarts ne doit pas sortir d'un bloc : borner, les plus anciens d'abord, et **dire ce qui
reste**. La leçon est déjà apprise sur les échéances de veille.

---

## 10. Le contrat avec les contextes appelants

Dans un sens : un contexte crée une intention avec un `purpose_ref` **opaque**, une `FeePolicy`,
une clé d'idempotence. Dans l'autre : le rail publie `PaymentSucceeded` / `PaymentFailed` par
l'outbox, et **le contexte appelant décide quoi en faire**.

```
ticketing   →  intent(purpose_ref=("ticketing", registration_id), fee=PERCENT 0.75)
collections →  intent(purpose_ref=("collections", contribution_id), fee=NONE)

PaymentSucceeded  →  ticketing émet le billet
                  →  collections enregistre la contribution
```

Le rail n'appelle jamais un contexte métier. Il écrit un événement ; qui l'écoute ne le regarde
pas.

### Ce que le rail ne fera jamais

- interpréter `purpose_ref` — pas un seul `if context == "ticketing"` ;
- mettre à jour un montant ;
- corriger un écart tout seul ;
- décider d'un tarif (c'est `pricing`) ;
- émettre quoi que ce soit vers `watch`.

---

## 11. Sécurité

> **L'actif le plus sensible n'est pas l'argent — ce sont les identifiants marchands.**

Une clé par église, chiffrée au repos avec une clé distincte de la base, **jamais journalisée,
jamais renvoyée par l'API**. Une fuite compromet toutes les églises d'un coup.

| Mesure | |
|---|---|
| Signature des callbacks | obligatoire, fenêtre temporelle + déduplication anti-rejeu |
| Données de carte | **aucune**. Le mobile money évite le PCI-DSS — ne jamais le perdre |
| Plafonds par tenant | montant, et débit de création d'intentions |
| MSISDN | donnée personnelle, mêmes règles que le reste du produit |
| Piste d'audit | non répudiable : qui a initié, qui a validé un remboursement, motif |
| Remboursements | **aucun automatisé en V1** — décision humaine, exécution hors bande |

---

## 12. L'UI n'attend jamais

**Rien n'est synchrone.** Le payeur confirme sur son téléphone, parfois plusieurs minutes plus
tard.

> Conçois l'écran autour de `PENDING`, pas du succès.

C'est une contrainte d'architecture, pas de design : une API qui bloque en attendant un webhook
produit des timeouts et des doubles paiements.

---

## 13. Séquence de construction

| Phase | Contenu | Note |
|---|---|---|
| **0** | **Enrôlement marchand** — 2 églises + bureau régional | **Chemin critique, non technique. Maintenant.** |
| **1** | **Faux fournisseur** : machine à états, journal, convergence, file d'écarts | La phase que tout le monde saute et qui décide de la robustesse |
| 2 | Un fournisseur, un cas d'usage : billetterie convention, bac à sable | |
| 3 | Production + **comptabilité fantôme** (tableur en parallèle, comparaison quotidienne) | L'équivalent du test des trois cellules |
| 4 | Second fournisseur, puis `pricing` complet | Quelques jours si la phase 1 est bien faite |

**La phase 1 teste explicitement six scénarios**, et ils sont la raison d'être du faux
fournisseur : timeout, webhook dupliqué, webhook hors ordre, succès arrivant après expiration,
montant divergent, transaction orpheline au relevé.

Aucun d'eux n'est reproductible avec un vrai fournisseur en bac à sable. C'est pour cela que le
faux vient en premier, et pas « quand on aura le temps ».

---

## 14. Invariants

1. Les fonds ne transitent **jamais** par Dorea — compte marchand par église
2. Le rail **n'interprète jamais** `purpose_ref`
3. Aucun montant n'est mis à jour ; journal append-only, statut **projeté**
4. Les états terminaux sont **absorbants** — une contradiction ouvre un écart
5. Idempotence aux trois frontières, dont `provider_event_id`
6. Les frais sont **déclarés par l'appelant** et figés à la création
7. Aucun écart n'est corrigé automatiquement
8. Un écart se ferme par **acte humain**, avec issue et motif
9. Arrondi déterministe, reliquat journalisé
10. Les identifiants marchands ne sont jamais journalisés ni renvoyés
11. Aucun remboursement automatisé
12. **Aucune donnée financière n'entre dans le moteur de veille** — aucun `FactKind` ne peut la
    porter, et le grillage du ledger le refuse déjà au démarrage
13. Montants entiers, devise portée par le devis — jamais de configuration globale

---

## 15. Ce qui reste à trancher

| Question | Impact |
|---|---|
| **Paiement scindé disponible ?** | **Décide du modèle de revenus.** Sans split, la commission n'est pas encaissable sur les petits montants — reste la prestation facturée |
| Mandat / prélèvement récurrent | Décide de la faisabilité de la cotisation automatique |
| Grilles de frais Wave et Orange | Décident de l'affichage du coût total |
| **Qui porte les frais opérateur ?** | À trancher **et afficher** avant la première transaction. *« Vous donnez 10 000, l'église reçoit X »* n'est pas de la conformité — c'est ce qui évite le soupçon |
| Noms `pricing` / `ticketing` | Confirmés ? Le reste du document en dépend |

Les trois premières se vérifient dans les documentations fournisseurs, et **avant** la phase 2.

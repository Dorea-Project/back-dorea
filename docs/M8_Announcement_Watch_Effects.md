# Annonce → Veille — comment une annonce agit sur la veille fraternelle

> **Mise à jour — le chemin a changé.** Les règles décrites ici sont inchangées, mais l'annonce
> **n'écrit plus rien elle-même** : elle est devenue une *source* du moteur de veille et émet un
> fait `LIFE_EVENT_ANNOUNCED`. La table de décision (`SubjectRole`, `ROLE_RULES`) vit désormais
> dans `watch/domain/role_rules.py`. Voir [Veille_Engine.md](Veille_Engine.md).

**Statut :** livré (lots 1 et 2). L'épisode reste à construire — voir « Ce qui n'est pas là ».
**Étend :** [M8_Announcements.md](M8_Announcements.md), [M6_Attendance_Model.md](M6_Attendance_Model.md), [M7_Pastoral_Intelligence.md](M7_Pastoral_Intelligence.md).

---

## 1. Le problème

Un membre disparaît six semaines. Le moteur de veille le remarque et demande à son responsable
de prendre de ses nouvelles. Sauf qu'une annonce de décès le concernant a été publiée trois
semaines plus tôt.

C'est le pire défaut possible pour ce produit : l'église **savait**, et le logiciel a demandé à
quelqu'un d'appeler un mort. Le même défaut, en moins brutal, se répète chaque fois qu'on
signale le silence d'une personne dont tout le monde sait qu'elle est à la maternité, à
l'hôpital ou en voyage.

L'information existe déjà — elle est dans le fil d'actualité. Elle n'était simplement branchée
sur rien.

---

## 2. Le principe : le rôle décide, pas le type

Le type d'annonce **propose** des rôles plausibles. C'est le **rôle** tenu par la personne qui
détermine l'effet. Une même annonce de décès porte deux rôles opposés :

| Rôle | Effet | Pourquoi |
|---|---|---|
| `deceased` | `EXIT` | Retrait définitif. Plus jamais de signal, quelle que soit la source |
| `bereaved` | `EPISODE` (40 j) | Le deuil **n'excuse pas** l'absence : il ouvre un soin |
| `sick` | `EPISODE` + `NEUTRALIZATION` (30 j) | Accord de l'intéressé exigé ; ne sort pas de la cellule |
| `new_parent` | `EPISODE` (21 j) + `NEUTRALIZATION` (56 j) | On l'entoure pendant qu'on ne l'attend pas |
| `newlywed` | `NEUTRALIZATION` (24 j) | On sait où ils sont |
| `traveler` | `NEUTRALIZATION` (durée déclarée) | Sans « jusqu'à quand », rien n'est posé — c'est refusé |
| `honoree` | aucun | On célèbre, on ne surveille pas |

Le choix le plus contre-intuitif est celui de l'endeuillé : **pas de neutralisation**. Excuser
l'absence d'une famille en deuil reviendrait à la rendre invisible au moment précis où elle a le
plus besoin qu'on aille vers elle. Elle reste attendue ; son silence reste un signal.

Les durées sont des **paramètres à calibrer par église** (backtest terrain), pas des constantes.
Elles vivent aujourd'hui dans [watch_rules.py](../app/contexts/announcements/domain/watch_rules.py),
`with_durations()` est le point d'entrée du paramétrage par tenant.

### La surcharge du publicateur ne peut que retrancher

L'écran pré-remplit les effets par défaut du rôle ; le publicateur peut en **décocher**. Il ne
peut pas en ajouter — sinon n'importe quel rôle permettrait de neutraliser la veille de
n'importe qui. `EXIT` absorbe : dès qu'il est retenu, c'est le seul effet évalué.

---

## 3. Trois garde-fous

### La date de l'événement, jamais celle de la publication

`occurred_at` — **quand c'est arrivé**. Distinct de `published_at` (quand on l'a dit) et de
`event_at` (quand on se réunit). Un voyage parti le 12 et annoncé le 20 a déjà consommé huit
jours ; sans cette distinction, toutes les échéances sont fausses de la durée de la saisie
tardive. Une date future est refusée : on annonce ce qui **est arrivé**.

### Un type qui parle d'une activité refuse un sujet

`service`, `meeting`, `call`, `info`, `sermon` n'acceptent aucun sujet — **contrainte à
l'écriture**, pas convention. C'est ce qui interdit structurellement qu'une collecte, un appel à
servir ou une info générale produise un effet de veille sur une personne.

### La maladie attend l'accord de l'intéressé

Un rôle intime (`sick`) retient l'annonce hors du fil (`pending_consent`). L'église n'apprend
rien ; seule la personne concernée est prévenue, et on lui **demande**. Refuser est terminal
(`declined`) : l'annonce ne paraîtra jamais et aucun effet n'est posé. Accepter la publie et
pose les effets **datés de l'événement**, pas de l'accord.

Personne ne consent à la place de quelqu'un — ni le pasteur, ni la secrétaire, ni l'auteur.
C'est la seule opération du module dont l'autorité est une identité, pas un rôle.

---

## 4. Où les effets s'écrivent

### La neutralisation → une `PlannedAbsence` d'origine `announcement`

L'absence planifiée (M6-2) est le seul objet que le roster et M7 consultent déjà. Une table
`Neutralisation` parallèle donnerait deux vérités concurrentes sur « cette personne est attendue
plus tard », et elles finiraient par diverger. Donc :

- `source = announcement`, `source_ref = l'annonce` — la clé d'idempotence `(annonce, personne)` ;
- `from_date` = la date de l'événement, `to_date` = le retour attendu ;
- `note` = la raison **en clair**, stockée, jamais recalculée à l'affichage.

**Prolongation, jamais cumul.** Une seconde annonce sur une personne déjà neutralisée repousse
`to_date` si elle va plus loin, et ne fait **rien** si la période est déjà couverte. Les durées
ne s'additionnent jamais.

Les absences que le membre a déclarées lui-même ne sont pas touchées : sa parole n'est pas
écrasée par une annonce faite sur lui.

**Retour anticipé :** clore sur `returned` **raccourcit** la période au lieu de l'effacer — les
rencontres manquées avant le retour restent excusées. Réécrire l'histoire d'un membre revenu
plus tôt en absences non justifiées serait exactement le faux positif qu'on veut éviter.

### La détection du retour (algo E)

[return_detection.py](../app/contexts/attendance/application/return_detection.py), branché sur
les **deux voix** de la présence : le pointage du responsable et l'auto-pointage du membre.

- **Ce qui compte comme retour :** une présence réellement enregistrée. Réagir à une annonce
  n'en est pas un — c'est un signe de vie, pas un retour. Le module n'est donc jamais appelé
  depuis le fil d'actualité. (Cohérent avec l'invariant anti-compteur : le clic n'absout pas.)
- **Daté de la rencontre, pas de la saisie.** Un responsable qui saisit le dimanche mercredi
  date le retour de dimanche — sinon l'histoire du membre décale à chaque saisie différée.
- Une présence **antérieure** au début de la neutralisation ne ferme rien : elle est simplement
  plus vieille que l'événement qui l'a posée.
- Les absences que le membre a **déclarées lui-même** ne sont jamais fermées : sa parole lui
  appartient, et venir une fois n'annule pas son voyage.
- Le retour ferme la neutralisation, **et elle seule** — on peut être présent et endeuillé.
  Le jour où l'épisode existera, il restera ouvert jusqu'au geste réel.
- Rien à remettre à zéro : M7 dérive la surveillance de la dernière présence.

**Manque :** la notification positive du produit (« X est revenu(e) le … ») s'adresse au
**référent** dans le document. `Referent` n'existant pas, elle n'est pas émise — l'envoyer à
l'auteur de l'annonce serait la donner à la mauvaise personne.

### La sortie → une `WatchExclusion`

Le document d'algorithme parle de `set_veille_status(person, EXCLUDED_PERMANENT)`. C'est bien un
**statut de veille**, pas un statut d'appartenance — et c'est décisif : publier une annonce ne
doit jamais pouvoir fermer l'adhésion de quelqu'un (ce geste demande `CLOSE_MEMBERSHIP`).
L'exclusion arrête la surveillance ; elle ne touche pas à l'identité. L'Admin clôturera
l'appartenance à son rythme, avec son autorité.

Poser une exclusion **clôt tout ce qui courait** sur la personne (issue `deceased`), puis
`GroupPulseComputer` la retire de tout calcul M7 : plus de pouls, plus d'état de marche, plus de
liste de soin, plus de trajectoire.

Elle est **absorbante** : aucune annonce postérieure ne rouvre quoi que ce soit, et il n'existe
pas d'opération pour la lever.

---

## 5. Surface HTTP

```http
POST /api/mobile/tenants/{tenant_id}/announcements
{
  "category": "death",
  "title": "Rappel à Dieu de Frère Yao",
  "occurred_at": "2026-04-12T00:00:00Z",
  "subjects": [
    { "account_id": "…", "role": "deceased" },
    { "account_id": "…", "role": "bereaved" }
  ]
}
```

```http
POST /api/mobile/announcements/{announcement_id}/consent
{ "accept": true }
```

Le rôle des sujets **n'est pas exposé** dans le fil : un membre voit `concerns_me`, jamais
« malade ». La pudeur est une propriété de la surface, pas seulement de la portée.

---

## 6. Ce qui n'est pas là

L'`EPISODE` n'est pas posé. Il demande le `Signal` et le `Referent`, qui n'existent pas encore
(cf. les arbitrages du moteur de veille). Concrètement :

> **Une annonce de décès ne produit aujourd'hui aucun effet pour la famille.** Le défunt sort de
> la veille ; l'endeuillé reste attendu, sans qu'un cas de soin s'ouvre sur lui.

C'est conforme à la table de décision, mais c'est un manque réel, et c'est le premier à combler.

Les effets retenus sont malgré tout **calculés et stockés** sur chaque sujet dès maintenant
(colonne `effects`) : le jour où l'épisode arrivera, il n'y aura rien à recalculer — juste à
consommer ce qui est déjà décidé.

Restent également à construire, dans l'ordre du document d'algorithme :

| # | Élément | État |
|---|---|---|
| D | Épisode + résolution du référent | bloqué par `Referent` |
| E | Détection du retour | **livré** (§4) ; la notification positive attend `Referent` |
| F | Worker nocturne (échéances, couverture aveugle) | bloqué par `Signal` |
| §10 | Rejouabilité / rétractation | bloqué par F |

L'algorithme F est celui qui donnera sa valeur pleine à la neutralisation : aujourd'hui, une
échéance atteinte sans retour ne produit **rien**. La donnée est là (`outcome` reste `NULL`,
`to_date` est dépassée), il manque l'objet qui matérialise le cas ouvert.

---

## 7. Invariants testés

[tests/contexts/announcements/test_watch_effects.py](../tests/contexts/announcements/test_watch_effects.py)

1. Une annonce sans sujet ne produit aucun effet
2. Un type qui parle d'une activité refuse le rattachement d'un sujet (contrainte, pas convention)
3. La surcharge du publicateur ne peut que retrancher ; `EXIT` absorbe
4. Une personne ne tient qu'un rôle par annonce
5. Deux neutralisations prolongent, ne cumulent pas ; une plus courte ne raccourcit rien
6. Le décès retire de la veille, clôt tout ce qui courait, et rien ne le lève
7. La consolation revient à l'endeuillé, jamais au défunt
8. Les durées courent depuis l'événement ; une date future est refusée
9. La maladie attend l'accord ; le refus est terminal ; personne ne consent pour autrui
10. Rejouer la même annonce laisse l'état identique
11. Une présence réelle ferme la neutralisation et raccourcit la fenêtre sans réécrire le passé
12. Une présence antérieure à l'événement n'est pas un retour ; une absence auto-déclarée n'est
    jamais fermée ; un second retour ne réécrit pas la date du premier

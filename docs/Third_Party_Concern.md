# Signalement par un tiers — l'intuition du responsable, le « je pense à quelqu'un » du membre

> État : **livré** (blocs 1, 2, 3, 6, 7, 8 + la route qui sert les blocs 4 et 5).
> Dépend de `Veille_Engine.md`, du module Référent et du traitement du Signal.

---

## 0. Ce que c'est — et ce que ce n'est pas

Jean sait déjà. Il le sait depuis trois semaines, et il n'a rien fait — non par négligence, mais
parce que **savoir ne crée aucune obligation**.

Le geste ne transporte donc **aucune information nouvelle** vers le système. Il convertit un
savoir privé en un cas daté, attribué, qu'il faudra fermer.

> **L'intuition n'est pas une source de données. C'est un dispositif d'engagement que le
> responsable se pose à lui-même.**

Tout le reste en découle : le contenu n'a presque aucune importance, et l'escalade change de
sujet.

---

## 1. Un seul fait pour deux usages

`LEADER_INTUITION` **a été retiré du vocabulaire.** Il ne reste que `THIRD_PARTY_CONCERN`.

Les deux gestes sont structurellement identiques — quelqu'un qui n'est pas le sujet signale une
inquiétude — et la seule différence, le rôle de l'émetteur, **se dissout dans la résolution du
propriétaire** :

| L'émetteur… | Le cas revient à… | Et se lit… |
|---|---|---|
| est le propriétaire du cas | lui-même | « Tu as pris l'engagement de prendre de ses nouvelles. » |
| ne l'est pas | au propriétaire | « Quelqu'un de l'église pense à cette personne. » |

Le cas du responsable n'est que le cas général replié sur lui-même. Deux `FactKind` auraient
divergé dans six mois.

**Deux sources, un seul kind :** `watch_ui` (écran Veille) et `companion` (membre). Les
distinguer sert à lire l'adoption de chaque canal, jamais à traiter les faits différemment.

---

## 2. La formulation retenue

« **Je m'en occupe cette semaine** », pas « je le sens loin ».

Le premier libellé déclare quelque chose *sur la personne* : il glisse vers le diagnostic, et
conservé, il fait une fiche. Le second déclare quelque chose *sur soi* — et il règle le problème
**par construction**, puisqu'il n'y a plus rien à écrire sur quelqu'un.

*Arbitrage de culture, à tester au terrain : « je le sens loin » se dit naturellement entre
responsables ; « je m'en occupe » sonne plus administratif.*

---

## 3. Le contenu — presque vide, et c'est voulu

**Aucun texte libre.** Le corps HTTP n'a que deux champs, et un test le verrouille.

```python
class Nuance(StrEnum):          # sur la RELATION, jamais sur la personne
    NO_NEWS = "no_news"                      # « je n'ai pas eu de nouvelles »
    PARTICIPATES_LESS = "participates_less"  # « il ne participe plus comme avant »
    SOMETHING_CHANGED = "something_changed"  # « quelque chose a changé, je ne sais pas quoi »
```

`FORBIDDEN_NUANCE_PATTERNS` est le même grillage que `FORBIDDEN_KIND_PATTERNS` du ledger : un
état intérieur supposé (*triste*, *déprimé*, *va mal*) fait échouer les tests, pas la revue de
code. La suite balaie l'enum entier — l'oubli est structurellement impossible.

La nuance n'existe **que** pour le suivant : si le cas est transféré ou escaladé, il reçoit
sinon un cas muet.

---

## 4. Le chemin d'un signalement

```
RaiseConcern
  ├─ refus : soi-même (→ SELF_DECLARATION), exclu·e, ou DO_NOT_CONTACT
  ├─ résout le propriétaire  ← ici, pas dans l'interpreter
  ├─ Fact(THIRD_PARTY_CONCERN, consent=SPEAK_FOR_ANOTHER par l'émetteur)
  └─ « Noté. »   — une fois, sans récapitulatif
        ↓
ThirdPartyConcernV1  (pur)
  └─ OpenCase(origin=CONCERN, owner=…, reason= une des deux phrases fixes)
```

**Pourquoi le propriétaire est résolu à l'émission.** Un interpreter est pur : ni horloge, ni
I/O. Ce n'est pas une concession, c'est plus juste — le référent d'il y a six semaines n'est pas
celui d'aujourd'hui, et rejouer le ledger doit rendre exactement ce que le direct a produit.

**Si l'église n'a aucun destinataire, le fait entre quand même.** Perdre l'inquiétude parce que
personne n'est configuré serait exactement le faux silence que le produit existe pour empêcher.
Le trou, lui, est consigné par `ResolveSignalOwner` en `NO_RECIPIENT`.

---

## 5. La non-rétention du déclarant

L'identité sert **à l'intake** — le fait exige une preuve de consentement à porter le souci
d'autrui — puis elle n'est plus jointe à rien.

- `ThirdPartyConcernV1` ne la lit qu'**une fois**, pour un test d'égalité dont il ne sort qu'un
  booléen. Un test le vérifie sur l'arbre syntaxique, pas par une lecture attentive.
- Les deux phrases sont **fixes** : l'interpreter ne sait pas écrire un nom.
- Aucune des trois lectures ajoutées au `SignalStore` ne prend le déclarant en argument ni ne le
  renvoie. « Qui a signalé qui » n'est reconstituable par aucune projection.

**La limite, dite franchement :** le ledger, lui, garde `consent.given_by` — il ne peut pas
faire autrement, c'est la preuve de consentement, et il est append-only. La promesse porte sur
les projections, qui sont tout ce que le produit restitue.

---

## 6. L'escalade change de sujet

Propre à cette source, et contre-intuitif.

Escalader vers le pasteur *à propos du membre* n'aurait aucun sens : il n'a aucune base pour
agir, il sait seulement que Jean a ressenti quelque chose.

Ce qui remonte est donc `CoverageGap.ENGAGEMENT_NOT_KEPT`, **avec le responsable pour sujet**.
L'action du pasteur est d'appeler Jean, pas Awa.

Le critère est `first_contact_at IS NULL`, jamais la clôture : un engagement tenu tard reste un
engagement tenu. Et un cas **sans propriétaire** n'escalade pas — il n'y a alors pas
d'engagement à ne pas tenir, seulement un trou de couverture déjà consigné.

Formulé comme un besoin d'aide, jamais comme un reproche : un responsable qui ne tient pas ses
engagements est le plus souvent un responsable débordé. Un test vérifie la phrase.

---

## 7. Le déversoir — un ratio, jamais un volume

Un responsable débordé peut taper sur dix personnes en trente secondes. Sa conscience est
tranquille, il n'a appelé personne.

| Comportement | Lecture |
|---|---|
| 10 intuitions, 10 contacts | **excellent responsable — ne jamais le freiner** |
| 10 intuitions, 0 contact | il se décharge |

> **Le tell est le ratio, jamais le volume.** Un seuil sur le volume punirait exactement les
> meilleurs.

Le volume n'intervient que comme **plancher de lisibilité** : en dessous de 5 signalements, le
ratio porte sur trop peu de cas pour vouloir dire quelque chose.

**Le plafond de débit s'applique à cette origine** — contrairement au déclaré du membre. Celui
qui demande de l'aide passe devant tout ; celui qui s'organise reste dans la file.

---

## 8. La calibration s'arrête au tenant

L'intuition est la seule source du produit qui **se vérifie** : l'émetteur a une croyance
préalable, et la résolution dit si elle était juste.

| | |
|---|---|
| Interdit | « Jean a raison 70 % du temps » — un score sur une personne |
| Autorisé | Taux de justesse **agrégé au tenant** |

`ConcernPrecision` n'a aucun champ qui descende à la personne, et un test le verrouille. À 80 %,
c'est la source la plus précieuse du produit ; à 20 %, c'est un déversoir et le plafond doit se
resserrer — dans les deux cas la décision porte sur un **seuil**, pas sur quelqu'un.

Un taux sur zéro cas clos renvoie `None`. Un pourcentage calculé sur rien est un mensonge qu'on
affiche avec assurance.

---

## 9. Deux décisions que le document ne prévoyait pas

**`CasePriority.CONCERN` a dû être créée.** Le §4 du document dit `origin: DECLARED` ; son §6 dit
que le plafond de débit s'applique *contrairement* au déclaré du membre. Dans le code,
`CasePriority.DECLARED` **est** précisément l'origine exemptée de plafond : les deux règles ne
pouvaient pas tenir sur la même valeur. La nouvelle origine porte la parole d'un tiers — plus
haut qu'une absence calculée, plus bas que celle de l'intéressé, et **soumise au plafond**.

**`SignalOutcome.NOTHING_TO_REPORT` a dû être ajoutée.** Sans elle, la calibration du §7 mesure
le vide : aucune issue du vocabulaire ne disait « j'ai pris contact, tout allait bien », donc
rien ne distinguait une intuition juste d'une intuition fausse.

---

## 10. Ce qui est en place

| # | Bloc | État |
|---|---|---|
| 1 | `THIRD_PARTY_CONCERN` unique + `Nuance` + grillage | ✅ |
| 2 | `ThirdPartyConcernV1` + résolution du propriétaire | ✅ |
| 3 | Non-rétention du déclarant | ✅ |
| 4 | Bouton écran Veille | route servie — reste l'écran |
| 5 | Bouton Compagnon | route servie — reste le Compagnon |
| 6 | Escalade `ENGAGEMENT_NOT_KEPT` | ✅ |
| 7 | Garde-fou de ratio + `LEADER_OVERLOADED` | ✅ |
| 8 | Calibration agrégée par tenant | ✅ |

**Aucune migration** : le schéma ne bouge pas. Les nouvelles valeurs d'énumérés vivent dans des
colonnes `String` existantes, et le propriétaire du cas s'écrit dans `watch_signals.owner_account_id`,
qui attendait depuis le début.

`EscalateStaleConcerns` et `GuardAgainstDumping` sont **construits et testés mais pas encore
cadencés** : il n'y a pas de worker. Ils s'appellent aujourd'hui à la main, comme
`RelayUnansweredRequests`.

---

## 11. Points ouverts

| Question | Position |
|---|---|
| Formulation retenue | « Je m'en occupe » — **à tester au terrain** contre « je le sens loin » |
| `CONCERN_ESCALATION_DAYS` | 10 jours par défaut — à calibrer |
| Seuils du garde-fou (5 / 30 %) | Pilote |
| La nuance est-elle utile, ou du bruit ? | À vérifier : si personne ne la renseigne, la retirer |
| **Les responsables l'utiliseront-ils ?** | **Inconnu.** La valeur dépend entièrement d'une habitude qui n'existe pas encore |

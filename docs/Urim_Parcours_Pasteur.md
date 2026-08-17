# Urim — le parcours du pasteur

*15 août 2026. Écrit après la fusion des neuf worktrees, contre le code qui tourne — pas contre
une intention.*

> **Un compagnon, pas un formulaire.** Le champ de saisie ne se ferme jamais. À n'importe quel
> moment le pasteur peut écrire ce qu'il veut — désigner, écarter, questionner, changer d'avis,
> ou parler de tout autre chose — et **quelque chose lui répond toujours**, en lui rappelant où
> il en est.

---

## 1. Entrer — l'antichambre

Urim s'ouvre **sans église et sans rôle**. Le rôle Dorea `null` est le cas normal, pas le cas
particulier : un pasteur peut préparer ses prédications sans que son assemblée soit dans le
système, et sans que personne l'y ait inscrit.

| Il fait | Ce qui se passe |
| :-- | :-- |
| S'inscrire | téléphone → OTP par SMS → il pose son code secret → connecté |
| Se connecter | téléphone + code secret + appareil |
| Depuis un appareil inconnu | un OTP de plus, puis l'appareil devient de confiance |
| **Code oublié** | téléphone → OTP → nouveau code → **connecté dans la foulée** |
| Se déconnecter | cet appareil, ou tous — le geste à faire quand on soupçonne un vol |

⚠️ **Le code oublié est arrivé le 14 août, et son absence était bloquante.** Le changement de
code existait depuis longtemps mais exigeait d'être *connecté* — or celui qui a oublié son code
ne peut pas se connecter. Trois propriétés le tiennent :

- **Aucune énumération.** La demande se comporte exactement pareil que le numéro existe ou non.
  Un refus sur un numéro inconnu ferait de cette route un **annuaire**.
- **Un motif d'OTP distinct.** Un code émis pour un porteur authentifié ne peut pas être rejoué
  dans un contexte anonyme.
- **Les autres sessions meurent.** Changer la serrure laisse rarement les anciennes clés en
  circulation. L'appareil qui vient de prouver sa possession du numéro, lui, est gardé.

---

## 2. Ouvrir — un seul champ, rien à cocher

Le pasteur écrit ou dicte **ce qui lui vient**. Il n'y a **aucun onglet** à choisir entre
« référence », « citation » et « intention » : c'est au moteur de reconnaître, en croisant la
saisie avec les 31 170 versets.

    Hb 2v29                                        une référence, dans SA notation
    « Dieu est l'auteur et le consommateur… »       une citation de mémoire
    « l'amour fraternel n'existe plus dans l'eglise » une conviction, une plainte
    « le fils prodigue rentre chez son pere »       une scène racontée

> 🔴 **L'onglet a existé, et il coûtait deux saisies sur trois.** Tant qu'un défaut `reference`
> comblait le silence, l'étage 0 posait une question de désaccord à quelqu'un qui n'avait rien
> dit. Le mode ne s'écrit plus que par une correction explicite.

---

## 3. Le tour — ce qui se répète

Une préparation n'est pas un formulaire en cinq étapes. C'est **un tour qui se répète** jusqu'à
ce que le pasteur ait son texte, ce qu'il porte, et de quoi prêcher.

Chaque tour porte quatre choses :

| | |
| :-- | :-- |
| `say` | ce qu'Urim vient de faire — **choisi sur l'écran**, pas sur le nom de l'étage |
| `why` | **le motif du moteur, tel quel** — jamais réécrit |
| `ask` | la question, et seulement quand il y a quelque chose à faire |
| `blocks` | le contenu, typé, à rendre de haut en bas |

**`why` n'est jamais nul, et c'est une règle du produit.** *Chaque réponse porte son filet doré.
C'est ce qui sépare un atelier d'un oracle.*

Et chaque réponse du pasteur **rejoue tout le raisonnement depuis le début**, à corpus constant.
C'est ce qui permet d'écarter une option sans perdre le fil, et de revenir en arrière sans rien
casser.

---

## 4. L'arbre — ce qui se passe quand il écrit

**Six sorties avant le premier appel de modèle.** L'ordre n'est pas négociable.

```
ce que le pasteur écrit
│
├─ vide, illisible ──────────────► « rien qui concerne la préparation »      0 appel
│
├─ une référence que le corpus rejette ──► « Hébreux 2 compte 18 versets »   0 appel
│
├─ LA LIAISON — exacte, déterministe
│   ├─ « ok », « d'accord » ─────► le tour se repose tel quel                0 appel
│   ├─ « non, pas le deuxième » ─► ÉCARTE      ◄── un geste exécuté          0 appel
│   └─ « Romains 12 », « le 3ᵉ » ─► DÉCIDE     ◄── un geste exécuté          0 appel
│
├─ pas de clé, quota épuisé ─────► le corpus répond seul, et le dit          0 appel
│
└─ L'AIGUILLEUR ─────────────────► 7 intentions → 7 répondeurs               1 appel
                                    ils PROPOSENT, aucun n'exécute
```

⚠️ **La référence introuvable passe avant la liaison**, et c'est le seul ordre défendable.
`Hb 2v29` tomberait sinon dans une option « Hébreux 2 » affichée en chapitre entier : décider
silencieusement cacherait au pasteur la seule chose utile du tour — *il n'y a pas de verset 29*.
Et ce que le corpus sait, il le sait sans le modèle.

⚠️ **Les deux seuls gestes qui changent la préparation viennent de la liaison**, qui ne devine
jamais. Sans appariement exact, elle rend la main.

> *Une intention mal aiguillée donne une réponse hors sujet. Une désignation manquée fait agir
> sur le mauvais objet.* La seconde est bien plus grave.

---

## 5. Les sept intentions

| Il dit | Intention | Ce qu'Urim répond |
| :-- | :-- | :-- |
| « en fait c'est plutôt sur le pardon » | `preciser` | reprend le fil, sans rien perdre |
| « que veut dire *upodema* ? » | `interroger_texte` | le grec, l'hébreu, la coutume — ou l'aveu que le corpus n'en dit rien |
| « quel plan je peux tenir ? » | `interroger_travail` | l'état de sa préparation — et sans texte ouvert, il le dit |
| « mets-moi ça en PowerPoint » | `demander_production` | le livrable, ou **pourquoi** il est encore fermé |
| « finalement je prêche autre chose » | `changer_de_sujet` | propose d'en ouvrir une neuve — **ne ferme jamais celle-ci** |
| « comment annoncer un décès ? » | `hors_champ` | dit ce qu'il ne sait pas faire, et tend une passerelle |
| « ma voiture a besoin de réparation » | `indechiffrable` | situe la préparation, sans reprocher le micro ouvert |

> **Aucune intention n'exécute quoi que ce soit.** Elles proposent. C'est ce qui autorise un
> aiguilleur **probabiliste** devant des répondeurs **déterministes** : un faux positif donne
> une réponse hors sujet, *jamais* un acte irréversible — et un travail de samedi soir ne se
> perd pas sur une phrase mal lue.

---

## 6. Les sept écrans

| Écran | Ce que le pasteur voit |
| :-- | :-- |
| `chips` | les dix loci, dans **sa** langue — « La prière sans réponse », pas « théologie propre » |
| `units` | les textes relus, groupés : **en fait son sujet** · **le soutient** · **lui résiste** |
| `bounds` | ses bornes contre l'unité relue, **avec la conséquence** |
| `bearings` | ce que le texte porte, les mises en garde, les mots d'origine, les textes qui résistent ailleurs |
| `feasibility` | les plans que le texte peut tenir — **et ceux qu'il refuse** |
| `theme` | une proposition, jamais un titre |
| `actions` | écrire ses points, emporter un document |

**Quatre règles que ces écrans tiennent :**

1. **Les pastilles sont des raccourcis, jamais des barreaux.** Il peut taper le libellé à la
   main ; `expects: choice` *autorise* le texte libre, il ne l'exclut jamais.
2. **`résiste` a son groupe**, au même rang que ce qui porte. C'est la seule mécanique
   anti-proof-texting du produit ; le noyer dans « le soutient » inverserait son sens.
3. **Les refusés voyagent avec les faisables.** Les cacher laisserait croire qu'on n'y a pas
   pensé.
4. **Un bouton grisé porte toujours son motif.** Un bouton muet est un mensonge poli.

⚠️ **Et un libellé habillé par le modèle porte sa signature.** Sur l'écran des dix loci, sept
titres viennent du corpus et trois sont écrits par le modèle en écho à la saisie du pasteur —
ils étaient indiscernables. On ne change pas la formulation, cet écran doit parler sa langue ;
on dit **lequel est habillé**.

---

## 7. La voix — deux usages qui ne partagent qu'un microphone

Le pasteur ivoirien dicte plus volontiers qu'il ne tape. Mais **parler à Urim et lui donner un
culte à écouter sont deux produits différents.**

| | La dictée, en préparation | La capture du culte |
| :-- | :-- | :-- |
| Ce qu'il fait | il dit sa conviction au lieu de la taper | il dépose sa prédication entière |
| Durée | quelques secondes | 45 minutes à une heure |
| Coût | négligeable | **0,05 à 0,33 € par heure d'audio** |
| Dans le flux | à l'ouverture, et à chaque tour | après le culte — un autre moment |
| État | le moteur la distingue **déjà** | spécifiée, construction non autorisée |

**Une dictée se fait confirmer là où une saisie tapée ne le fait pas.** Cette règle est vivante :
le système *sait* d'où vient la chaîne — le module de capture connaît son `provider` — au lieu de
le déduire des mots.

Le cas qui l'a imposée traîne dans tout ce dépôt :

> *« Ma voiture 406, a besoin de reparation , jefgf Paradis »*

Le détecteur peut s'acharner sur ce texte : **il n'y a rien à comprendre**, et il ne faut pas le
reprocher à celui qui parlait.

⚠️ **Le dioula n'est plus le mur qu'on croyait.** La première version de la note disait *« Dorea
transcrit le français ; on ne promet pas le dioula »*. Ce n'est plus vrai — la langue locale est
redevenue une question ouverte, et ça change ce qu'on peut promettre à une assemblée qui ne
prêche pas qu'en français.

---

## 8. Les impasses, et ce qu'Urim y répond

**Aucun tour ne se termine par un mur.** Après chaque tour, le pasteur a quelque chose à faire :
des options à toucher, une barre de saisie ouverte, ou une passerelle nommée.

**Il a écarté les dix axes**
> Ces dix axes sont ce que la dogmatique de ce corpus sait nommer — un sujet peut n'entrer dans
> aucun. Donnez-moi un texte, même un seul verset : je l'ouvre entier, avec ce qui en a été relu.

**Il demande un conseil sur quelqu'un**
> Je ne sais pas conseiller sur les personnes ni sur la conduite d'une assemblée. Ce que je sais
> faire, c'est ouvrir un texte avec vous : si un passage vous vient pour cette situation,
> donnez-le-moi.

**Le micro est resté ouvert**
> Je n'ai rien reçu qui concerne la préparation. Nous en sommes à Romains 12:9-16. Reprenez
> quand vous voulez.

**Le modèle ne répond pas**
> La préparation continue sans lui, avec ce que le corpus sait dire — et la dégradation est
> dite, jamais masquée.

> ⚠️ **Aucune ne reproche quoi que ce soit au pasteur.** On nomme ce qu'Urim *est*, jamais ce que
> l'autre a mal fait. La phrase *« je n'ai pas compris »* est **bannie par un test** : une parole
> captée par un micro resté ouvert a été parfaitement comprise, elle ne nous était pas destinée.

---

## 9. Ce qui fait le compagnon

**Rien de ce qu'il dit n'est irréversible.** Une option écartée reste dans la liste, reléguée —
il peut y revenir. La retirer lui ferait perdre ce qu'on lui avait proposé, et rendrait son geste
irréversible par accident.

**Il n'est jamais perdu.** Chaque réponse — même celle qui n'a rien à donner — rappelle où en est
la préparation : *« Nous en sommes à Romains 12:9-16. »* C'est le seul service qu'un tour perdu
puisse rendre, et il le rend toujours.

**Rien ne lui est reproché.** Voir §8.

**Il se souvient.** Ce qu'il a écarté reste écarté, ce que le modèle a répondu est gardé, et le
raisonnement se rejoue à l'identique tant que le corpus n'a pas bougé. Reprendre une préparation
trois jours plus tard donne le même fil, pas un autre.

**Et rien de généré ne se confond avec une relecture.** La signature `ia-mistral` voyage jusqu'à
l'écran. Sur les 45 557 pesées du corpus, **aucune n'a encore été relue par un théologien** — et
c'est écrit, pas masqué.

---

## 10. Ce qui n'est pas encore dans le flux

| Manque | Ce que le pasteur ne peut pas faire |
| :-- | :-- |
| Ses appareils | voir où il est connecté, et en révoquer un |
| Effacer son compte | partir — **et c'est une décision de produit, pas de code** |
| Le paiement | rien n'est encaissable : aucun cycle de facturation |
| Le transport audio | parler au lieu d'écrire — le moteur sait traiter une dictée, rien ne porte le son |

⚠️ **`delete-account` n'est pas un chantier technique.** Ses préparations sont à lui et partent
avec lui, sans hésitation. Mais sa présence aux cultes, ses groupes, son historique dans
l'assemblée : **l'église les détient aussi**. Effacer un membre, est-ce effacer ce que l'église a
observé de lui ? La piste qui tient d'habitude — *le compte disparaît, les faits deviennent
anonymes* — reste à trancher.

---

## 11. Les règles qui tiennent tout le parcours

1. **Le serveur rend le tour, le client rend des blocs.** Le client n'écrit jamais une phrase de
   sa propre autorité — sans quoi elle échapperait à la relecture et aux tests.
2. **Le modèle n'a aucun canal de sortie en prose.** Il rend des codes et des références
   vérifiées contre les 31 170 versets. La voix du produit est écrite en français, une fois, et
   relue.
3. **Le modèle nomme des références ; la Bible donne le texte.** Toujours.
4. **Aucun mur un vendredi soir.** Pas de clé, quota épuisé, panne, corpus muet : la préparation
   continue, dégradée et **dite**.
5. **Une décision ne vaut que sur l'objet qu'elle a regardé.** Le corpus change, la trace le dit ;
   la curation change, le verdict se périme.

# DOREA — Le projet, son état, son cœur

> **But de ce document :** expliquer Dorea simplement — ce qu'est le projet, ce qui est
> réellement construit, ce qui reste, ses angles morts, et surtout sa philosophie.
> Écrit pour être lu autant par un développeur que par un pasteur.
>
> **Base :** état des lieux du code au 25 juillet 2026 (dépôt `back-dorea`). Les affirmations
> techniques sont ancrées dans le code réel ; ce qui est promesse-non-encore-construite est dit
> comme tel, sans maquillage.

---

## 1. Le projet en clair

### Ce que c'est

Dorea est une **plateforme de vie communautaire pour les églises africaines**. Mais son cœur
n'est pas la gestion d'église : c'est un **système de veille fraternelle** — *détecter les
personnes qui s'éloignent, et déclencher un contact humain.*

La promesse tient en une phrase : **ne plus perdre personne dans la foule.**

Tout le reste (annonces, événements, rendez-vous, sermons…) existe pour **capter la matière**
qui nourrit cette veille, ou pour donner à l'église une raison d'ouvrir l'application. Le
véritable produit, c'est la boucle : *quelqu'un décroche → quelqu'un s'en aperçoit → quelqu'un
l'appelle → on note ce qui s'est passé.*

### L'architecture, en une image

Un seul serveur (FastAPI, Python) propriétaire de sa base de données PostgreSQL, découpé en
**13 « contextes »** (modules métier). Deux applications le consomment :
- une **application mobile Flutter** pour les membres (téléphone + code PIN) ;
- un **back-office web (PWA)** pour les responsables et le pasteur.

Pas de messagerie interne, pas de fil d'actualité addictif, **pas de broker temps réel** :
des choix délibérés (voir §5).

### Ce qui est fait / ce qui reste — vue macro

**Largement construit :** l'ossature d'une plateforme d'église complète — identité et rôles,
onboarding d'église, groupes/cellules, présence, intelligence pastorale (lecture seule),
annonces, événements, mission/évangélisation, rendez-vous, sermons, notifications.

**Le cœur — la chaîne de veille — n'est PAS encore bouclé.** La chaîne se lit ainsi :

```
captation → qualification → détection → attribution → contact → résolution
   FAIT        PARTIEL        FAIT        À FAIRE      À FAIRE    À FAIRE
                                        (+ mémoire relationnelle : À FAIRE)
                                        (+ couverture : calculée, non branchée)
```

Autrement dit : **on sait capter la présence et détecter qui s'éloigne, mais on ne sait pas
encore transformer cette détection en un cas qu'on attribue à un humain, qu'on suit jusqu'au
contact, et qu'on referme.** C'est le chantier central qui reste.

---

## 2. Les modules, un par un

Légende : **Livré** (construit, branché à l'API, testé) · **Partiel** · **Amorcé** (écrit mais
pas branché / incomplet) · **Note de design** (décidé, pas codé).

### Le socle

**IAM — Identité, rôles, permissions** · *Livré (le plus testé).*
Qui est qui, dans quelle église, avec quel rôle (pasteur, admin, secrétaire, responsable de
groupe, « Timothée » en formation, équipe d'accueil…). Gère aussi le transfert d'un membre
entre églises. *Reste :* invariant « un seul Owner par église » à durcir ; rôle `church_leader`
prévu, pas encore ajouté.

**Auth — Connexion** · *Livré.*
Deux profils : le pasteur/responsable (email + OTP), le membre (téléphone + PIN, l'appareil
devient la clé). JWT, anti-force-brute. *Reste :* rien de bloquant.

**Tenant — L'église et son Owner** · *Livré.*
Création d'une église (onboarding public → « genèse » → premier compte pasteur), profil,
propriété. *Reste :* la notion d'annexe = église-fille avec son propre Owner est décidée mais
son échafaudage n'est pas terminé.

**Groups — Groupes et cellules** · *Livré.*
Arbre typé (cellule / ministère / classe), double filiation (structure + lignée de
multiplication), chemin matérialisé pour l'autorisation par sous-arbre. Le leadership est un
rôle *rattaché à un groupe*. *Reste :* détails d'ouverture (visibilité de la liste des membres).

### Le cœur pastoral

**M6 — Présence** · *Livré.*
On n'enregistre que des **signaux positifs** : les présents et les excusés. **L'absence est
déduite**, jamais saisie ni stockée. Saisie leader ou auto-pointage par un « code de séance »
(type Kahoot). Le membre peut **pré-déclarer** son absence (« absent 3 semaines »). *Reste :*
la présence au culte église-entière et la géolocalisation sont laissées ouvertes.

**M7 — Intelligence pastorale** · *Livré, et strictement en lecture seule.*
À partir des présences, le système déduit un **état de marche** par personne — au rythme *propre
à cette personne*, pas à un seuil absolu. Il produit une **liste de soin** (« à interpeller »),
une trajectoire, la santé d'une cellule, l'arbre de multiplication. **Il ne persiste rien, ne
change aucun statut, ne classe personne.** Le système éclaire ; l'humain décide.

**Couverture / Cadence** · *Amorcé — construit mais non branché.*
Le « Programme » : le rythme *attendu* d'un groupe (cette cellule aurait dû se réunir tel jour).
Permet de dire « aucune rencontre saisie depuis 5 semaines = veille aveugle sur 18 personnes ».
Une occurrence a **trois états** : saisie / acquittée (non tenue, motif connu) / silencieuse
(trou). *État réel :* le calcul, les tables et les tests existent, **mais rien n'est exposé via
l'API** — la fonctionnalité est aujourd'hui *injoignable*. C'est le premier étage de la veille
par couverture.

### Les modules « satellites » (captation & vie d'église)

**M8 — Annonces** · *Livré.* Fil d'actualité où le *type* pilote la couleur/l'intention ;
réactions emoji **sans compteur public** (anti-vitrine) ; le « 32 personnes vous portent » est
remis *au sujet* d'une consolation, jamais affiché comme score.

**Event — Événements** · *Livré.* Le happening publié (date, lieu, géo) ; réactions **sans
compteur public** (retiré, correctif récent) ; participants confirmés ; tableau de rayonnement
réservé à l'organisateur (compte Business).

**Mission — La main tendue** · *Livré (partiel).* Lien d'invitation → carte-versículo générée
par IA → chercheur (Seeker) → accompagnement → intégration. *Reste :* M9-2 « Dialoguer » (IA
conversationnelle).

**RDV — Rendez-vous** · *Livré.* L'agenda du pasteur gardé par la secrétaire ; le membre demande,
la secrétaire confirme/décline avec un mot.

**Sermon & Compagnon** · *Livré côté mobile.* Le pasteur dépose, l'IA résume en capsules, un
compagnon privé demande « as-tu vécu le culte ? ». *Reste :* dépôt côté back-office ; S-6 audio
(transcription).

**Notifications — Push** · *Livré (best-effort).* Appareils + envoi push non bloquant, avec repli
en journalisation. *Reste :* l'envoi réel (FCM) et le cron de production.

**Billing — Compte Business** · *Partiel.* Le compte Business d'une *personne*, activé par carte
prépayée Visa. *Reste :* la **facturation réelle** (rien n'est débité aujourd'hui).

**Media** · *Livré (technique).* Upload d'images, stockage local en dev / S3-MinIO en prod.

### Décidé mais pas codé

- **Abonnement d'église** (offres Standard/Pro/Premium selon taille + annexes) — *note de design.*
- **Console admin Dorea** (3ᵉ plan d'autorisation, `/api/admin/*`) — *note de design.*

---

## 3. Présenter Dorea à un pasteur

*(Ici, je prends parti. Je défends le projet tel qu'il veut être.)*

Pasteur, laissez-moi vous poser une seule question : **combien de personnes ont quitté votre
église sans que personne ne s'en rende compte à temps ?**

Pas par manque d'amour. Par manque d'**yeux**. Une église qui grandit devient une foule, et dans
une foule, on se perd. La personne qui souffre en silence est souvent la plus discrète — elle ne
fait pas de bruit en partant. Trois dimanches d'absence, puis quatre, puis on l'oublie. Ce n'est
la faute de personne, et c'est exactement le problème : **quand c'est la responsabilité de tout
le monde, ce n'est celle de personne.**

Dorea existe pour une chose : **que plus jamais quelqu'un ne s'éloigne sans qu'un frère ou une
sœur ne soit averti et n'aille le chercher.**

Ce n'est pas un logiciel de plus. Ce n'est pas un réseau social « chrétien ». Dorea est
volontairement **l'inverse d'une application qui cherche à vous retenir**. Son unique juge de
paix, pour chaque fonctionnalité, c'est cette question : *est-ce que ça fait regarder un écran
plus longtemps, ou est-ce que ça fait aimer une personne réelle ?* Si c'est le premier, c'est
refusé.

Concrètement, ce que Dorea vous rend :
- **Des yeux.** Chaque responsable de cellule voit qui commence à s'éloigner — non pas « qui a
  raté trois cases », mais qui a **rompu son propre rythme**. Celui qui venait chaque semaine et
  disparaît compte plus que celui qui vient une fois par mois et saute un mois.
- **Une main.** Quand quelqu'un décroche, Dorea ne vous envoie pas un badge à liker. Il vous dit :
  *appelle-le.* Et vous sortez de l'application — vers votre téléphone, WhatsApp. Dorea
  **enregistre que le contact a eu lieu**, il ne le remplace pas.
- **Une mémoire.** Quand un responsable de cellule change, tout ce qu'il savait des gens
  disparaît d'habitude avec lui. Chez Dorea, **cela reste.** L'histoire relationnelle survit.
  C'est peut-être ce qu'un simple groupe WhatsApp ne saura jamais faire.
- **La vérité, pas la vanité.** Dorea ne compte pas les « j'aime ». Il vous dit des choses utiles :
  « 40 personnes ont réagi à cette annonce de deuil, 2 ont rendu visite. » L'écart entre les
  deux, c'est exactement ce qu'un pasteur a besoin de voir.

Et — parce que l'honnêteté fait partie du soin — voici ce que Dorea **refuse** d'être : un
fichier. On peut **sortir** de la veille. « Ne souhaite plus être contacté » est une sortie
respectée, définitive. Une veille dont on ne peut pas sortir n'est pas de la fraternité, c'est
de la surveillance. Dorea a choisi la fraternité.

**Où en est-on, franchement ?** L'église numérique — présence, groupes, annonces, événements,
rendez-vous, sermons — est **là et fonctionne**. Le cœur — détecter qui s'éloigne — **voit déjà**.
Ce qui se construit maintenant, c'est le **dernier maillon** : transformer ce que le système voit
en un appel confié à une personne précise, suivi jusqu'au bout. C'est le chantier en cours, et
c'est là que Dorea deviendra pleinement ce qu'il promet.

---

## 4. Les angles morts

*Les zones où le projet est fragile, incomplet, ou aveugle sur lui-même. Sans complaisance.*

1. **La chaîne de veille est coupée après la détection.** Le produit *voit* qui s'éloigne
   (M7), mais il n'existe encore **aucun objet « cas de veille »** : pas d'attribution à un
   référent, pas de journal de contact, pas de cycle ouvert→fermé, pas de mémoire relationnelle.
   Tant que ce maillon manque, **la promesse centrale n'est pas opérationnelle de bout en bout.**

2. **Le silence est ambigu — et l'indicateur qui le lèverait n'est pas branché.** La couverture
   (« cette cellule est-elle aveugle ? ») est *calculée* mais **injoignable via l'API**. Résultat :
   aujourd'hui, « zéro alerte » peut vouloir dire *tout va bien* **ou** *personne ne saisit rien*,
   sans moyen de trancher. La promesse est structurellement **invérifiable** en l'état.

3. **Personne ne peut « qualifier » une absence.** La distinction reine de Dorea — *absence sans
   nouvelles* vs *absence expliquée* — repose sur un champ qui existe dans le code mais **qu'aucune
   action n'écrit**. L'état « sans nouvelles » (le seul qui alerte) ne peut donc pas être posé
   aujourd'hui.

4. **De la fonctionnalité invisible.** La brique cadence/couverture est écrite, testée, migrée…
   mais non exposée. Du travail réel, mais **inatteignable** — donc, pour l'utilisateur, inexistant.

5. **Pas d'historique de version (git absent).** Le dépôt n'est pas versionné. Impossible de
   retracer *qui a fait quoi, quand, pourquoi.* C'est un risque de mémoire projet, et cela rend
   certaines décisions **invérifiables**.

6. **L'intention de veille vit hors du dépôt.** Les documents fondateurs (« chaîne de veille »,
   « moteur ») ne sont **pas** dans le repo. Un nouveau venu lisant seulement le code ne peut pas
   deviner que M7 + cadence visent une chaîne bien plus large.

7. **Le sympathisant reste indétectable.** Celui qui vient régulièrement mais n'appartient à
   aucune cellule : par choix (pas de pointage au culte), **aucune donnée ne remonte son
   décrochage.** C'est reconnu, mais non résolu.

8. **Deux promesses commerciales pas encore réelles :** la **facturation** Business (activable,
   mais rien n'est débité) et le **push réel** (repli en simple journalisation, pas d'envoi FCM
   en production).

9. **Des specs qui se contredisent, sans arbitre déclaré.** La spec V1 d'origine est en partie
   dépassée par l'état livré, mais **aucun document ne dit lequel fait foi** (ex. mécanisme de
   présence, portées d'annonces, pasteur « lecture seule »). Risque de confusion pour qui reprend.

10. **Modules seulement esquissés :** abonnement d'église et console admin Dorea ne sont que des
    notes de design.

---

## 5. Le cœur et la philosophie

Si on ne devait retenir qu'une chose, ce serait ceci : **Dorea est conçu pour être ouvert
rarement.** Sa réussite ne se mesure pas au temps passé dedans, mais aux **personnes rejointes**.
Un pilote où 2 000 personnes ouvrent peu l'appli mais où 90 % des signaux sont traités sous 72 h
est un **succès total** ; 10 000 utilisateurs quotidiens seraient, selon le filtre du produit
lui-même, un **échec**.

De ce parti pris découle tout le reste :

- **Le filtre fondateur.** Chaque fonctionnalité passe une porte unique : *fait-elle regarder un
  écran plus longtemps, ou aimer une personne réelle ?* C'est un droit de veto, pas un slogan.

- **La présence est un soin, pas un pointage.** On n'enregistre que les présents et les excusés ;
  **l'absence est déduite, jamais stockée comme une liste de fautes.** On ne veut pas 20 « absent »
  en base ; on veut savoir *qui il faut rappeler.*

- **Le système révèle, l'humain décide.** M7 ne change aucun statut, ne retire personne, ne juge
  pas. Il **suggère**. La décision pastorale reste humaine, toujours.

- **Aucun score, aucun classement, aucun comparatif entre personnes.** Le jour où l'on peut trier
  les membres par popularité, on a construit un réseau social. Interdit — et interdit
  *structurellement*, dans le modèle de données, pas comme un réglage.

- **Pas de boucle d'engagement.** Le test n'est pas « y a-t-il un chiffre ? » mais « y a-t-il une
  **boucle** ? » (je produis → je reviens voir si ça monte → je republie). Un décompte remis à la
  personne concernée, une fois, comme un fait — « 32 personnes vous portent » — est du **soin**.
  Un compteur public rattaché à ce que j'ai produit est une **vanité**. Le premier est gardé, le
  second est banni.

- **Le contact sort de l'application.** Dorea rend l'appel facile (téléphone, WhatsApp) et
  **enregistre qu'il a eu lieu.** Il ne le remplace jamais par un message interne. Le refus de la
  messagerie n'est pas une limite : c'est le cœur du parti pris.

- **La mémoire relationnelle est la vraie défense du produit.** Ce qu'un groupe WhatsApp perd
  quand un responsable change, Dorea le garde. C'est ce qui fait qu'une église *capitalise* son
  attention fraternelle au lieu de la recommencer à zéro à chaque relève.

- **On peut sortir de la veille.** « Ne souhaite plus être contacté », « sympathisant connu et
  suivi » : ce ne sont pas des concessions, ce sont les **garde-fous qui séparent la veille
  fraternelle de la surveillance.** Une file de veille doit pouvoir atteindre **zéro**.

- **Une personne = un référent.** L'invariant visé : *toute personne dans la base a exactement un
  humain nommé qui la connaît.* Le groupe n'est qu'une façon habituelle d'attribuer ce référent,
  pas la seule. Une personne sans référent est un **trou de veille** — quel que soit son statut.
  *(Cet invariant est décidé ; il n'est pas encore construit.)*

---

### En une phrase

> **Dorea est un système de veille fraternelle déguisé en plateforme d'église : la plateforme est
> largement construite et fonctionne ; l'œil qui détecte est ouvert ; il reste à lui donner la
> main qui rejoint — le maillon qui transforme « je vois que tu t'éloignes » en « quelqu'un est
> allé te chercher, et on s'en souvient ».**

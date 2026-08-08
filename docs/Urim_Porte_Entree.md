# Urim — la porte d'entrée du moteur

> **Nature :** décision produit, **implémentée**. Elle remplace la spec L2 (« l'entrée sans
> mode »), qui rendait `entry_mode` facultatif. Il ne l'est pas : **il n'existe plus**.
>
> État vérifié au 7 août 2026, après le chargement de la LSG 1910 entière.

---

## 1. La porte ne pose qu'une question

**Y a-t-il un texte derrière cette phrase ?**

```
                        la saisie
                            │
              ┌─────────────┴─────────────┐
              │  CROISEMENT sur 31 170 versets  │
              │  les mots se suivent-ils ?      │
              └─────────────┬─────────────┘
        ┌─────────────┬─────┴─────┬─────────────┐
     nommé          cité       aucun         rien
  « Rom 8:1 »  « car Dieu    une            de lisible
                 a tant… »   intention
        └──── un passage ────┘      │             │
                                 l'émotion      refus
                                  oriente
```

**Nommé ou cité, c'est le même verdict** — il y a un texte. La façon dont le pasteur l'a
désigné n'est qu'une mécanique de résolution : analyser des chiffres, ou chercher une suite de
mots. Ce n'est pas un choix à lui faire faire.

## 2. Ce qui décide : l'ordre des mots, jamais le vocabulaire

Mesuré sur la Bible entière :

| saisie | plus longue suite commune | verdict |
| :-- | --: | :-- |
| « car dieu a tant aimé le monde » | 7/7 | citation → **1.00** |
| « que l'amour fraternel continue » | 2/4 | citation → **0.50** |
| « et jésus pleura » | 2/3 | citation → **0.67** |
| « l'amour fraternel n'existe plus dans l'église » | 2/6 | intention → **0.33** |
| « ma voiture a besoin de réparation » | 2/9 | rien → **0.22** |

Le seuil est à **0.45**. Onze saisies sur onze correctement orientées.

> **La contre-épreuve qui vaut la démonstration.** *« L'amour fraternel n'existe plus dans
> l'église »* et *« Que l'amour fraternel continue »* partagent leurs mots les plus rares. La
> seconde est Hébreux 13:1 ; la première est une plainte. **Seul le croisement sur l'ordre
> pouvait les séparer** — le vocabulaire des deux est entièrement biblique.

`scripture_affinity` mesure donc la **contiguïté**, et non plus le rappel. Trois mesures
existent, pour trois questions différentes, et les confondre a déjà coûté :

| mesure | question | consommateur |
| :-- | :-- | :-- |
| contiguïté | *est-ce une citation ?* | `scripture_affinity` |
| F1 (rappel × précision) | *quel verset est-ce ?* | `resolve_citation` |
| rappel seul | — | **plus utilisé** |

## 3. `entry_mode` disparaît du corps HTTP

`OpenStudyBody` ne porte plus que `raw_input`, `entry_origin` et `service_date`.

**Pourquoi pas « facultatif » comme le proposait L2.** Un champ facultatif reste un champ : un
client le remplirait « par prudence », et le défaut fantôme reviendrait par la porte du client
au lieu de celle du schéma. Absent, il ne peut plus être rempli d'office.

**Et son absence règle un bug**, sans la colonne que j'avais d'abord proposée. Puisque plus
rien ne le remplit automatiquement, `entry_mode` non nul ne peut plus vouloir dire qu'une
chose : **le pasteur a tranché**. L'étage 0 ne le reconteste donc jamais.

> 🔴 **Le bug qu'il fallait fermer.** `route_entry.applies()` se protégeait de la reprise en
> lisant `state.trace`. Mais **le service ne persiste pas la trace** — c'est le principe du
> rejeu : *on stocke les décisions, pas le raisonnement*. La trace repart vide à chaque
> affichage, l'étage se ré-exécute toujours, et un pasteur qui maintenait sa lecture contre le
> détecteur recevait **la même question indéfiniment**. Vérifié avant correction.
>
> C'était la troisième occurrence de la même famille : une décision humaine enregistrée,
> invisible pour l'étage qui la relit. Les deux précédentes étaient le bornage et le re-clage
> S9.

## 4. L'émotion n'entre qu'après la porte

Elle ne classe rien. Elle ne dit jamais *« c'est une intention »* — c'est le croisement qui l'a
dit, en ne trouvant pas de texte. Elle sert **après**, dans le chemin conviction, à orienter :
une formulation chargée élargit les textes qui **résistent** et relève le risque de
proof-texting.

Si elle entrait dans le classement, elle déciderait de la lecture. Or **une lecture
émotionnelle juste produit quand même un sermon qui blesse** — ce qui protège l'affligé, ce
n'est pas qu'on ait bien lu la détresse du pasteur, c'est que les textes qui résistent
s'affichent quand même (S10, S20, S37).

⚠️ **Reste à faire :** le service calcule aujourd'hui le risque sur **toute** saisie, y compris
une référence. C'est inoffensif tant qu'aucun modèle n'est branché — `NullConvictionReader`
rend toujours `()` — mais c'est faux dans l'ordre. Le risque doit se lever après que le
croisement a dit « pas un verset ».

## 5. Ce qui rend encore la main, et pourquoi

**Une dictée lue comme une intention** se fait confirmer. Le doute ne porte pas sur la lecture :
il porte sur le fait que le pasteur ait voulu saisir quoi que ce soit. C'est le garde-fou du
micro resté ouvert, et il est **plus** nécessaire sans onglet, pas moins — il n'y a plus aucune
autre barrière entre une poche et une préparation.

**Une seule lecture est proposée**, plus deux. La seconde disait *« ce que vous aviez
indiqué »* ; le pasteur n'indique plus rien, et proposer un choix entre le détecté et un défaut
fantôme fabriquerait une alternative qui n'existe pas.

**`reformuler` fonctionne enfin.** L'étage 0 proposait ce bouton et l'API le refusait en 422 —
une porte offerte, puis claquée. Elle abandonne la préparation : *rouvrir la saisie sans rien
conserver*, ce que S36 demandait.

## 6. Ce qui reste ouvert

| # | Question | État |
| :-- | :-- | :-- |
| 1 | Charger **Darby** et **Martin** | Le pasteur cite la traduction qu'il lit. Avec la seule LSG, un vrai verset cité d'une autre version passe à 0.50 au lieu de 1.00. **C'est ce qui améliorerait le plus la porte, avant tout modèle.** |
| 2 | Le port LLM de classification | Pour le milieu incertain — « l'histoire de Jézabel », une paraphrase. Il **ajoute, ne retire jamais**, et son verdict s'enregistre comme une décision pour que le rejeu reste identique. Le détecteur déterministe reste le sol : sinon la porte d'entrée disparaît au plafond et hors ligne (S33). |
| 3 | Le risque levé après le verdict | §4 ci-dessus. |
| 4 | « Ce n'est pas ça » après un `CONTINUE` | La route de décision l'accepte déjà (elle pose `entry_mode`, qui n'est plus recontesté). Reste à décider ce que l'écran en fait. |

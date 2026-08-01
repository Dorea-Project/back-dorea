"""La **boucle froide** — elle observe et calibre ; elle ne décide jamais d'un cas.

> La boucle chaude décide — cinq étages, déterministes, inchangés.
> La boucle froide observe et calibre — elle ne produit que des propositions de `WatchParam`.

Ce qu'elle fait : mesurer les seuils du produit **contre ce que les humains ont constaté**. Un cas
fermé sur « j'ai pris contact, tout allait bien » dit que la détection s'est trompée ; une
inquiétude signalée par un tiers et confirmée dit qu'un humain a vu avant le moteur. C'est ça,
« comprendre le jeu de veille » — jamais prédire des personnes.

**Les quatre interdits, structurels — pas des consignes :**

1. **Aucun objet de calibration ne porte l'identifiant d'une personne observée.** Les agrégats
   sont par `(église, origine)` au plus fin. La frontière est entre l'**auteur** et le **sujet** :
   une personne peut avoir *décidé* d'un réglage — une décision se signe, et
   `decided_by_account_id` est le seul identifiant de tout le paquet — mais aucune ne peut être
   *mesurée*. Un test balaie les dataclasses de ce sous-module et n'y autorise que trois champs
   d'identifiant ; tout le reste échoue.
2. **La boucle froide ne peut pas écrire un effet.** Ce paquet n'importe ni le `Materializer`, ni
   un chemin d'écriture du moteur — un test d'imports l'atteste.
3. **Aucun fait inféré n'entre au ledger.** La calibration ne passe jamais par l'intake. Ses
   sorties vivent dans ses propres tables.
4. **Pas de score par personne**, visible ou non. La sensibilité au contexte s'exprimera par le
   rythme du groupe et par des annotations factuelles — jamais par un nombre attaché à quelqu'un.

**Et sa propre clause d'arrêt.** La précision des cas ouverts, église par église, doit monter d'un
mois sur l'autre. Si elle ne monte pas, la boucle froide n'apprend rien et on la coupe — même
exigence que pour tout le reste du produit.
"""

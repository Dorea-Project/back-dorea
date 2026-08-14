"""Le livrable de prédication — `.docx` (la note) et `.pptx` (ce que l'assemblée voit).

Conception : `docs/Urim_Livrable.md`. La règle qui gouverne tout le module y tient en une ligne,
et elle est **structurelle plutôt que déclarative** :

> Le livrable ne se génère jamais sans que quelque chose du pasteur y soit — sinon il n'a aucun
> effet.

Trois verrous la portent, et aucun n'est un `if` de politesse :

1. la colonne vertébrale du document est **son plan** (`documents.POINT_CENTRAL`) ;
2. le texte biblique projeté est **jugé avant qu'un octet de fichier existe** (`citation`) ;
3. **`Deck` n'a nulle part où mettre** une mise en garde, un motif ou un risque de
   proof-texting — la frontière tient dans la forme du type.

⚠️ Le modèle n'a **aucun canal de sortie en prose** : `axes` rend des codes, `passages` rend des
références vérifiées. Un générateur de document est exactement l'endroit où ce canal se
rouvrirait — il suffit qu'une case du gabarit s'appelle « introduction proposée ». Il n'en
existe aucune, et il ne doit jamais en exister.
"""

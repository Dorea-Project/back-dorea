"""Les franchissements **nommés** de la frontière d'Urim.

Un fichier ici est un endroit où Urim touche le reste du système, et le fait exprès. Le
test d'architecture les autorise ; il interdit tout le reste. La règle n'est pas « Urim
est isolé » — c'est « les endroits où Urim ne l'est plus se comptent, et se lisent ».

⚠️ Deux exceptions ne s'ouvrent **jamais** ici, même sous forme d'adaptateur : la finance
n'entre pas (S27), et rien n'écrit vers la veille (S28). Deux tests les tiennent, et ils
n'ont aucune exemption.
"""

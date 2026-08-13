"""Les deux écrivains — **les seuls fichiers du dépôt qui importent `pptx` et `docx`**.

Même posture que `adapters/mistral.py` : la bibliothèque tierce reste à la bordure, et l'import
est **paresseux** (patron de l'extracteur de sermon) — un dépôt sans `python-docx` installé
continue de démarrer, de résoudre des passages et de valider des citations. Seul le rendu échoue,
et il échoue en le disant.

## Ce que ces fichiers ne font pas

**Ils ne décident rien.** La frontière écran/note est déjà tenue par les types (`Deck` n'a nulle
part où mettre une mise en garde) ; ces modules mettent en page ce qu'on leur donne. Si un jour
une mise en garde apparaît sur une diapositive, ce ne sera pas ici qu'il faudra chercher —
ce sera que quelqu'un aura ajouté un champ au type.

**Ils ne produisent rien qui n'ait été validé.** C'est le service qui refuse de rendre un
livrable non `conforme` ; ici on suppose le contrôle déjà passé.

## Deux détails qui se voient depuis le fond de la salle

**Le 16:9 se pose explicitement.** `python-pptx` ouvre en 4:3 : un cadre noir de chaque côté est
la première chose que l'assemblée voit du travail de la semaine.

**La mention de destination est en pied de CHAQUE page de la note**, jamais une page de garde —
elle ne survivrait ni à une capture d'écran, ni à un partage partiel, ni à une impression recto.
"""

from __future__ import annotations

from io import BytesIO

from app.contexts.urim.deliverable.domain.documents import Deck, Note

#: 16:9 en EMU (914 400 par pouce) — 13,333 x 7,5 pouces.
_LARGEUR_16_9 = 12192000
_HAUTEUR_16_9 = 6858000

#: Les codes de section, rendus lisibles. Le dictionnaire ne **ferme** rien : un code inconnu
#: s'imprime tel quel, parce que la colonne est libre et qu'un pasteur peut nommer ses sections.
_SECTIONS = {
    "titre": "Titre",
    "introduction": "Introduction",
    "proposition": "Proposition",
    "phrase_interrogative": "Question",
    "phrase_de_transition": "Transition",
    "divisions": "Point",
    "subdivisions": "Sous-point",
    "illustrations": "Illustration",
    "application": "Application",
    "conclusion": "Conclusion",
    "objectif": "Objectif",
    "contexte": "Contexte",
    "definitions": "Définition",
    "nb": "NB",
    "temoignage": "Témoignage",
}

#: Ce qu'un pied de page de note doit dire, et à qui elle est destinée. Voir l'en-tête.
MENTION = (
    "Note de préparation — les mises en garde s'adressent au prédicateur, "
    "non à l'assemblée."
)


class RenduIndisponibleError(RuntimeError):
    """La bibliothèque de rendu n'est pas installée.

    Une erreur nommée plutôt qu'un `ImportError` nu : sur un déploiement incomplet, la phrase
    doit dire **quoi faire**, comme `CorpusNonSemeError` le fait pour le corpus."""


def rendre_deck(deck: Deck) -> bytes:
    """Le `.pptx` — un titre, puis une diapositive par texte projeté."""
    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        raise RenduIndisponibleError(
            "`python-pptx` n'est pas installé : le rendu des diapositives est indisponible."
        ) from exc

    presentation = Presentation()
    presentation.slide_width = _LARGEUR_16_9
    presentation.slide_height = _HAUTEUR_16_9

    couverture = presentation.slides.add_slide(presentation.slide_layouts[0])
    couverture.shapes.title.text = deck.titre
    # Le sous-titre reste **vide** : y mettre le thème proposé par le moteur ferait monter à
    # l'écran une phrase que personne n'a écrite.
    for diapositive in deck.diapositives:
        page = presentation.slides.add_slide(presentation.slide_layouts[1])
        page.shapes.title.text = diapositive.titre or diapositive.reference
        corps = page.placeholders[1].text_frame
        corps.text = diapositive.texte_projete
        corps.word_wrap = True
        for paragraphe in corps.paragraphs:
            for morceau in paragraphe.runs:
                morceau.font.size = Pt(28)
        # La référence sous le texte — une projection sans référence est une citation
        # invérifiable pour qui la lit depuis le banc. ⚠️ **Sauf quand elle est déjà le
        # titre** : sans ce garde, une diapositive sans titre affiche deux fois la même
        # référence, ce qui se voit du fond de la salle et fait amateur.
        if diapositive.titre:
            rappel = corps.add_paragraph()
            rappel.text = diapositive.reference
            for morceau in rappel.runs:
                morceau.font.size = Pt(18)

    flux = BytesIO()
    presentation.save(flux)
    return flux.getvalue()


def rendre_note(note: Note) -> bytes:
    """Le `.docx` — tout ce que le moteur a rassemblé, et rien qui monte à l'écran."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        raise RenduIndisponibleError(
            "`python-docx` n'est pas installé : le rendu de la note est indisponible."
        ) from exc

    document = Document()
    _pied_de_page(document)

    document.add_heading(note.titre or note.reference, level=0)
    document.add_paragraph(note.reference)

    if note.unite:
        document.add_heading("L'unité littéraire", level=1)
        document.add_paragraph(note.unite)
        # ⚠️ **Le motif du découpage voyage avec les bornes.** C'est la phrase que le pasteur
        # lit pour vous contredire ; l'imprimer sans elle donnerait des bornes venues de nulle
        # part.
        _sous_texte(document, note.motif_unite)

    if note.plan:
        document.add_heading("Votre plan", level=1)
        for code, corps in note.plan:
            paragraphe = document.add_paragraph(style="List Bullet")
            # ⚠️ **Le code de section est une étiquette, pas une ligne.** Imprimé sous chaque
            # point, `divisions` répété trois fois transformait son plan en sortie de
            # débogage — vu sur le premier rendu réel.
            etiquette = paragraphe.add_run(f"{_SECTIONS.get(code, code)} · ")
            etiquette.italic = True
            etiquette.font.size = Pt(9)
            paragraphe.add_run(corps)

    if note.versets:
        document.add_heading("Le texte", level=1)
        for reference, corps in note.versets:
            document.add_paragraph(f"{reference} — {corps}")

    if note.pesees:
        document.add_heading("Ce que le texte porte", level=1)
        for axe, force, motif in note.pesees:
            document.add_paragraph(f"{axe} · {force}", style="List Bullet")
            _sous_texte(document, motif)

    if note.mises_en_garde:
        document.add_heading("Ce que le texte ne dit pas", level=1)
        for garde in note.mises_en_garde:
            document.add_paragraph(garde, style="List Bullet")

    if note.resistances:
        document.add_heading("Ce qui résiste, ailleurs", level=1)
        for reference, motif in note.resistances:
            document.add_paragraph(reference, style="List Bullet")
            _sous_texte(document, motif)

    if note.faisabilites:
        document.add_heading("Plan et matière", level=1)
        for couple, faisable, refus, risque in note.faisabilites:
            verdict = "faisable" if faisable else f"refusé — {refus}"
            document.add_paragraph(f"{couple} : {verdict}", style="List Bullet")
            if risque:
                _sous_texte(document, f"risque de proof-texting : {risque}")

    if note.appuis:
        document.add_heading("Vos textes d'appui", level=1)
        for reference, corps, verdict in note.appuis:
            # ⚠️ **Une saisie illisible s'imprime avec son motif**, jamais en silence : la
            # perdre obligerait le pasteur à se souvenir de ce qu'il voulait citer.
            document.add_paragraph(f"{reference or verdict} — {corps}", style="List Bullet")

    if note.original:
        document.add_heading("Les mots de l'original", level=1)
        for surface, lemme, morphologie in note.original:
            document.add_paragraph(f"{surface} ({lemme}) — {morphologie}", style="List Bullet")

    if note.ecartees:
        document.add_heading("Ce que vous avez écarté", level=1)
        for option, motif in note.ecartees:
            document.add_paragraph(option, style="List Bullet")
            _sous_texte(document, motif)

    provenance = document.add_paragraph()
    trace = provenance.add_run(
        f"Curation signée : {note.signature or 'non relue'} · "
        f"corpus {note.corpus_snapshot or 'inconnu'}"
    )
    trace.font.size = Pt(8)

    flux = BytesIO()
    document.save(flux)
    return flux.getvalue()


def _sous_texte(document, texte: str) -> None:
    if not texte:
        return
    from docx.shared import Pt

    paragraphe = document.add_paragraph()
    morceau = paragraphe.add_run(texte)
    morceau.italic = True
    morceau.font.size = Pt(9)


def _pied_de_page(document) -> None:
    """La mention de destination, **dans le pied de page de chaque page**.

    Une page de garde ne survit ni à une capture d'écran, ni à un partage partiel, ni à une
    impression recto — et le PDF, lui, circule pour de bon."""
    from docx.shared import Pt

    for section in document.sections:
        paragraphe = section.footer.paragraphs[0]
        morceau = paragraphe.add_run(MENTION)
        morceau.italic = True
        morceau.font.size = Pt(8)

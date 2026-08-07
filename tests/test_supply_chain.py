"""La chaîne d'approvisionnement — DOREA-017.

`pyproject.toml` déclare ce dont l'application a besoin ; `uv.lock` fige **ce qui sera
réellement installé**. Quand les deux divergent, l'installation résout au moment où elle
tourne — c'est-à-dire vers ce qui est disponible ce jour-là, y compris une version
compromise. Une dépendance non verrouillée n'est pas une dépendance à jour : c'est une
dépendance dont personne ne sait ce qu'elle vaut.

La dérive s'était produite en silence : `pypdf` et `python-pptx` ont été ajoutés au
`pyproject` puis installés avec `pip`, sans que le lock soit régénéré. Rien n'a protesté.

Ce test proteste. Il ne répare pas — **régénérer le lock demande `uv`** (`uv lock`), qui
n'est pas sur ce poste. Il rend la dérive visible au premier `pytest`, au lieu de la laisser
dormir jusqu'au prochain déploiement.
"""

import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _ROOT / "pyproject.toml"
_LOCK = _ROOT / "uv.lock"

# `fastapi>=0.115.0`, `uvicorn[standard]>=0.32.0`, `sqlalchemy[asyncio]>=2.0.36`…
_NAME = re.compile(r"^([A-Za-z0-9._-]+)")


def _declared() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    names = set()
    for spec in data["project"]["dependencies"]:
        match = _NAME.match(spec.strip())
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def _locked() -> set[str]:
    # Le lock est du TOML, mais on n'a besoin que des noms de paquets.
    return {
        name.lower().replace("_", "-")
        for name in re.findall(r'^name = "([^"]+)"', _LOCK.read_text(encoding="utf-8"), re.M)
    }


def test_le_lock_existe():
    assert _LOCK.is_file(), "uv.lock manquant : plus rien n'est verrouillé"


@pytest.mark.xfail(
    reason="DOREA-017 — dérive connue : pypdf/python-pptx installés via pip, lock non "
    "régénéré. Se répare par `uv lock` (uv absent de ce poste). Le jour où le lock est "
    "régénéré, ce test passe au vert et le xfail doit être retiré.",
    strict=False,
)
def test_chaque_dependance_declaree_est_verrouillee():
    manquantes = sorted(_declared() - _locked())
    assert manquantes == [], (
        f"{len(manquantes)} dépendance(s) déclarée(s) hors du lock : {manquantes}. "
        "Elles se résoudront à l'installation, vers une version que personne n'a choisie."
    )


def test_aucune_dependance_n_est_sans_plancher():
    """DOREA-021 — une dépendance sans version minimale accepte n'importe quel passé,
    y compris les versions portant des CVE connues."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    sans_plancher = [
        spec
        for spec in data["project"]["dependencies"]
        if not any(marker in spec for marker in (">=", "==", "~="))
    ]
    assert sans_plancher == [], f"dépendances sans plancher de version : {sans_plancher}"

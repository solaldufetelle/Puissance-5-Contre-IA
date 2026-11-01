"""
Puissance 5 : jouez contre une IA.

Plateau de 7 lignes x 9 colonnes, il faut aligner 5 jetons de la même couleur
(en ligne, en colonne ou en diagonale).

Lancer en local :   streamlit run app.py
"""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ia import HAUTEUR, LARGEUR, ALIGNER, Plateau, choisir_coup

# Temps de réflexion de l'IA par coup, en secondes.
# Plus c'est grand, plus l'IA voit loin (et plus elle est forte).
TEMPS_REFLEXION = 8.0

JAUNE, ROUGE = 1, 2
NOMS_COULEURS = {JAUNE: "Jaune", ROUGE: "Rouge"}
EMOJIS = {JAUNE: "🟡", ROUGE: "🔴"}

st.set_page_config(page_title="Puissance 5", page_icon="🟡", layout="centered")

# Composant personnalisé : plateau SVG sur lequel on clique directement dans les colonnes
plateau_ui = components.declare_component(
    "puissance5_plateau",
    path=str(Path(__file__).parent / "composant"),
)


# --------------------------------------------------------------------------- #
#  Logique de partie (tout est déduit de la liste des coups joués)
# --------------------------------------------------------------------------- #
def joueur_du_coup(i, humain_commence):
    """Qui a joué le coup numéro i ('humain' ou 'ia') ?"""
    premier, second = ("humain", "ia") if humain_commence else ("ia", "humain")
    return premier if i % 2 == 0 else second


def code_couleur(joueur, couleur_humain):
    return couleur_humain if joueur == "humain" else (ROUGE if couleur_humain == JAUNE else JAUNE)


def analyser(coups, humain_commence):
    """Rejoue la partie. Renvoie (plateau, gagnant, nul)."""
    plateau = Plateau()
    gagnant = None
    for i, col in enumerate(coups):
        if plateau.jouer(col):
            gagnant = joueur_du_coup(i, humain_commence)
    nul = gagnant is None and plateau.est_plein()
    return plateau, gagnant, nul


def construire_grille(coups, humain_commence, couleur_humain):
    """
    Grille pour l'affichage : liste de 7 lignes (de haut en bas) de 9 cases
    (0 = vide, 1 = jaune, 2 = rouge). Renvoie aussi la position du dernier jeton.
    """
    grille = [[0] * LARGEUR for _ in range(HAUTEUR)]
    hauteurs = [0] * LARGEUR
    derniere = None
    for i, col in enumerate(coups):
        ligne = HAUTEUR - 1 - hauteurs[col]
        grille[ligne][col] = code_couleur(joueur_du_coup(i, humain_commence), couleur_humain)
        hauteurs[col] += 1
        derniere = [ligne, col]
    return grille, derniere


def trouver_ligne(grille):
    """Toutes les cases appartenant à un alignement de 5 jetons ou plus."""
    gagnantes = set()
    for l in range(HAUTEUR):
        for c in range(LARGEUR):
            v = grille[l][c]
            if not v:
                continue
            for dl, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                fin_l, fin_c = l + dl * (ALIGNER - 1), c + dc * (ALIGNER - 1)
                if not (0 <= fin_l < HAUTEUR and 0 <= fin_c < LARGEUR):
                    continue
                cases = [(l + dl * k, c + dc * k) for k in range(ALIGNER)]
                if all(grille[a][b] == v for a, b in cases):
                    gagnantes.update(cases)
    return [list(x) for x in sorted(gagnantes)]


# --------------------------------------------------------------------------- #
#  État de l'application
# --------------------------------------------------------------------------- #
def demarrer_partie(couleur_humain, humain_commence):
    ss = st.session_state
    ss.ecran = "jeu"
    ss.couleur_humain = couleur_humain
    ss.humain_commence = humain_commence
    ss.coups = []
    ss.dernier_clic = None
    ss.id_partie = ss.get("id_partie", 0) + 1     # nouvelle clé => nouveau composant


def retour_menu():
    st.session_state.ecran = "menu"


# --------------------------------------------------------------------------- #
#  Écrans
# --------------------------------------------------------------------------- #
def ecran_menu():
    st.title("Puissance 5")
    st.write(
        "Alignez **5 jetons** de votre couleur, en ligne, en colonne ou en diagonale, "
        "sur un plateau de 7 lignes × 9 colonnes. L'IA joue du mieux qu'elle peut : "
        "à vous de la battre."
    )

    choix_couleur = st.radio(
        "Couleur de votre jeton",
        [f"{EMOJIS[JAUNE]} Jaune", f"{EMOJIS[ROUGE]} Rouge"],
        horizontal=True,
        key="menu_couleur",
    )
    choix_qui = st.radio(
        "Qui commence ?",
        ["Moi", "L'IA"],
        horizontal=True,
        key="menu_qui",
    )
    st.caption("Celui qui commence a un net avantage dans ce jeu.")

    if st.button("Commencer la partie", type="primary"):
        couleur = JAUNE if "Jaune" in choix_couleur else ROUGE
        demarrer_partie(couleur, humain_commence=(choix_qui == "Moi"))
        st.rerun()


def ecran_jeu():
    ss = st.session_state
    couleur_humain = ss.couleur_humain
    humain_commence = ss.humain_commence
    couleur_ia = ROUGE if couleur_humain == JAUNE else JAUNE

    plateau, gagnant, nul = analyser(ss.coups, humain_commence)
    grille, derniere = construire_grille(ss.coups, humain_commence, couleur_humain)
    trait = joueur_du_coup(len(ss.coups), humain_commence)
    partie_en_cours = gagnant is None and not nul
    tour_humain = partie_en_cours and trait == "humain"
    tour_ia = partie_en_cours and trait == "ia"

    # --- Bandeau d'état ---
    st.markdown(
        f"**Vous** : {EMOJIS[couleur_humain]} {NOMS_COULEURS[couleur_humain]} &nbsp;·&nbsp; "
        f"**IA** : {EMOJIS[couleur_ia]} {NOMS_COULEURS[couleur_ia]}"
    )
    if gagnant == "humain":
        st.success("Bravo, vous avez battu l'IA !")
    elif gagnant == "ia":
        st.error("L'IA remporte la partie. Une revanche ?")
    elif nul:
        st.info("Match nul : le plateau est plein.")
    elif tour_humain:
        st.info("À vous de jouer : cliquez sur une colonne.")
    else:
        st.warning("L'IA réfléchit…")

    # --- Plateau cliquable ---
    clic = plateau_ui(
        grille=grille,
        derniere=derniere,
        gagnantes=trouver_ligne(grille) if gagnant else [],
        couleur_humain=couleur_humain,
        actif=tour_humain,
        n_coups=len(ss.coups),
        key=f"plateau_{ss.id_partie}",
        default=None,
    )
    if clic and clic.get("t") != ss.dernier_clic:
        ss.dernier_clic = clic.get("t")
        col = clic.get("col")
        if tour_humain and isinstance(col, int) and 0 <= col < LARGEUR and plateau.colonne_jouable(col):
            ss.coups = ss.coups + [col]
            st.rerun()

    # --- Boutons ---
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Rejouer (mêmes réglages)", use_container_width=True):
            demarrer_partie(couleur_humain, humain_commence)
            st.rerun()
    with c2:
        if st.button("Changer les réglages", use_container_width=True):
            retour_menu()
            st.rerun()

    # --- Tour de l'IA (en dernier, pour que le plateau soit déjà affiché pendant qu'elle réfléchit) ---
    if tour_ia:
        col = choisir_coup(plateau, TEMPS_REFLEXION)
        ss.coups = ss.coups + [col]
        st.rerun()


def main():
    if "ecran" not in st.session_state:
        st.session_state.ecran = "menu"
    if st.session_state.ecran == "jeu":
        ecran_jeu()
    else:
        ecran_menu()


main()

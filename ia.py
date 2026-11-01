"""
Moteur de Puissance 5 (plateau de 7 lignes x 9 colonnes) et intelligence artificielle.

Techniques utilisées :
- plateau codé en "bitboards" (un grand entier Python par joueur) -> détection
  des alignements et des cases gagnantes ultra rapide ;
- recherche négamax avec élagage alpha-bêta ;
- approfondissement itératif limité par le temps ;
- table de transposition ;
- détection tactique exacte : victoire immédiate, blocage obligatoire,
  double menace, coups qui offrent une victoire à l'adversaire ;
- évaluation heuristique de toutes les "fenêtres" de 5 cases.
"""

import time

# --------------------------------------------------------------------------- #
#  Constantes du plateau
# --------------------------------------------------------------------------- #
HAUTEUR = 7                  # lignes
LARGEUR = 9                  # colonnes
ALIGNER = 5                  # nombre de jetons à aligner
PAS = HAUTEUR + 1            # 8 bits par colonne : 7 cases + 1 bit "plafond"

# Bit 0 de chaque colonne (sert à trouver la première case libre)
BAS = [1 << (PAS * c) for c in range(LARGEUR)]
BAS_TOUS = sum(BAS)
# Les 7 cases réelles de chaque colonne
CASES_COL = [((1 << HAUTEUR) - 1) << (PAS * c) for c in range(LARGEUR)]
PLATEAU = sum(CASES_COL)

# On essaie d'abord les colonnes du centre
ORDRE = sorted(range(LARGEUR), key=lambda c: abs(c - LARGEUR // 2))

DIRECTIONS = (1, PAS - 1, PAS, PAS + 1)   # vertical, diag. descendante, horizontal, diag. montante

GAIN = 1_000_000             # score d'une victoire
SEUIL_MAT = GAIN - 200       # au-dessus : score de victoire/défaite forcée
INFINI = 10 ** 9

try:                          # Python >= 3.10
    _popcount = int.bit_count
except AttributeError:        # pragma: no cover
    def _popcount(x):
        return bin(x).count("1")


def _indice(ligne, colonne):
    return colonne * PAS + ligne


def _construire_fenetres():
    """Toutes les suites de 5 cases alignées du plateau (sous forme de masques)."""
    fenetres = []
    for l in range(HAUTEUR):
        for c in range(LARGEUR):
            for dl, dc in ((0, 1), (1, 0), (1, 1), (-1, 1)):
                fin_l = l + dl * (ALIGNER - 1)
                fin_c = c + dc * (ALIGNER - 1)
                if 0 <= fin_l < HAUTEUR and 0 <= fin_c < LARGEUR:
                    m = 0
                    for k in range(ALIGNER):
                        m |= 1 << _indice(l + dl * k, c + dc * k)
                    fenetres.append(m)
    return fenetres


FENETRES = _construire_fenetres()
# Poids d'une fenêtre ne contenant que 1, 2, 3 ou 4 jetons d'un seul joueur
POIDS = (0, 1, 3, 10, 300, 0)


# --------------------------------------------------------------------------- #
#  Fonctions sur les bitboards
# --------------------------------------------------------------------------- #
def est_gagnant(b):
    """Vrai si le bitboard b contient 5 jetons alignés."""
    for d in DIRECTIONS:
        m = b & (b >> d)
        m &= m >> (2 * d)          # 4 jetons alignés
        if m & (b >> (4 * d)):     # + un 5e
            return True
    return False


def cases_gagnantes(b):
    """
    Cases (vides ou non) où poser un jeton compléterait un alignement de 5
    pour le joueur dont les jetons sont dans b.
    """
    r = 0
    for d in DIRECTIONS:
        s1 = b >> d
        s2 = b >> (2 * d)
        s3 = b >> (3 * d)
        s4 = b >> (4 * d)
        l1 = b << d
        l2 = b << (2 * d)
        l3 = b << (3 * d)
        l4 = b << (4 * d)
        r |= ((s1 & s2 & s3 & s4)
              | (l1 & s1 & s2 & s3)
              | (l2 & l1 & s1 & s2)
              | (l3 & l2 & l1 & s1)
              | (l4 & l3 & l2 & l1))
    return r & PLATEAU


def evaluer(pos, adv):
    """Évaluation statique du point de vue du joueur 'pos' (celui qui doit jouer)."""
    score = 0
    for w in FENETRES:
        a = pos & w
        o = adv & w
        if a:
            if not o:
                score += POIDS[_popcount(a)]
        elif o:
            score -= POIDS[_popcount(o)]
    return score


# --------------------------------------------------------------------------- #
#  Plateau de jeu
# --------------------------------------------------------------------------- #
class Plateau:
    """
    Position de jeu. 'pos' = jetons du joueur qui doit jouer,
    'mask' = tous les jetons posés.
    """

    __slots__ = ("pos", "mask", "nb_coups")

    def __init__(self):
        self.pos = 0
        self.mask = 0
        self.nb_coups = 0

    def copie(self):
        p = Plateau()
        p.pos, p.mask, p.nb_coups = self.pos, self.mask, self.nb_coups
        return p

    def colonne_jouable(self, col):
        return (self.mask + BAS[col]) & CASES_COL[col] != 0

    def colonnes_jouables(self):
        return [c for c in range(LARGEUR) if self.colonne_jouable(c)]

    def est_plein(self):
        return self.nb_coups >= HAUTEUR * LARGEUR

    def jouer(self, col):
        """Pose un jeton dans la colonne `col`. Renvoie True si ce coup gagne."""
        bit = (self.mask + BAS[col]) & CASES_COL[col]
        if not bit:
            raise ValueError(f"La colonne {col} est pleine.")
        gagne = est_gagnant(self.pos | bit)
        self.pos ^= self.mask      # le joueur suivant devient "pos"
        self.mask |= bit
        self.nb_coups += 1
        return gagne


# --------------------------------------------------------------------------- #
#  Recherche
# --------------------------------------------------------------------------- #
class _TempsEcoule(Exception):
    pass


_EXACT, _BORNE_BASSE, _BORNE_HAUTE = 0, 1, 2


class _Recherche:
    def __init__(self, temps_max):
        self.fin = time.perf_counter() + temps_max
        self.noeuds = 0
        self.table = {}
        self.courant = None          # meilleur coup de l'itération en cours
        self.profondeur_atteinte = 0

    def negamax(self, pos, mask, prof, alpha, beta, ply, mes_gagn):
        """
        pos      : jetons du joueur qui joue
        mask     : tous les jetons
        mes_gagn : cases_gagnantes(pos), déjà calculé par le parent
        Valeur renvoyée : du point de vue du joueur qui joue.
        """
        self.noeuds += 1
        if not (self.noeuds & 127) and time.perf_counter() > self.fin:
            raise _TempsEcoule

        possibles = (mask + BAS_TOUS) & PLATEAU
        if not possibles:
            return 0                                   # match nul

        # 1) Victoire immédiate
        if mes_gagn & possibles:
            return GAIN - ply - 1

        # 2) Table de transposition
        cle = pos + mask
        entree = self.table.get(cle)
        meilleur_tt = -1
        alpha_initial = alpha
        if entree is not None:
            e_prof, e_val, e_drapeau, meilleur_tt = entree
            if e_prof >= prof:
                if e_val > SEUIL_MAT:
                    e_val -= ply
                elif e_val < -SEUIL_MAT:
                    e_val += ply
                if e_drapeau == _EXACT:
                    return e_val
                if e_drapeau == _BORNE_BASSE:
                    if e_val > alpha:
                        alpha = e_val
                elif e_val < beta:
                    beta = e_val
                if alpha >= beta:
                    return e_val
                alpha_initial = alpha

        adv = pos ^ mask
        menaces = cases_gagnantes(adv) & ~mask         # cases où l'adversaire gagnerait
        urgentes = menaces & possibles
        perte = -(GAIN - ply - 2)

        # 3) Tactique : blocages obligatoires et coups suicidaires
        if urgentes:
            if urgentes & (urgentes - 1):              # deux menaces : perdu
                return perte
            surs = urgentes & ~(menaces >> 1)
            if not surs:
                return perte
            prof_enfant = prof                         # coup forcé : pas de perte de profondeur
        else:
            if prof <= 0:
                return evaluer(pos, adv)
            surs = possibles & ~(menaces >> 1)         # on évite d'offrir la case du dessus
            if not surs:
                return perte
            prof_enfant = prof - 1

        # 4) Ordre des coups : table de transposition d'abord, puis le centre
        coups = []
        for c in ORDRE:
            b = surs & CASES_COL[c]
            if b:
                if c == meilleur_tt:
                    coups.insert(0, (c, b))
                else:
                    coups.append((c, b))

        meilleur = -INFINI
        meilleur_col = -1
        for c, b in coups:
            v = -self.negamax(adv, mask | b, prof_enfant, -beta, -alpha, ply + 1, menaces)
            if v > meilleur:
                meilleur = v
                meilleur_col = c
                if v > alpha:
                    alpha = v
                    if alpha >= beta:
                        break

        # 5) Mémorisation
        if meilleur <= alpha_initial:
            drapeau = _BORNE_HAUTE
        elif meilleur >= beta:
            drapeau = _BORNE_BASSE
        else:
            drapeau = _EXACT
        v_stockee = meilleur
        if v_stockee > SEUIL_MAT:
            v_stockee += ply
        elif v_stockee < -SEUIL_MAT:
            v_stockee -= ply
        self.table[cle] = (prof, v_stockee, drapeau, meilleur_col)
        return meilleur

    def racine(self, pos, mask, prof, coups):
        """Cherche à la profondeur `prof`. Renvoie la liste (valeur, col, bit) pour chaque coup."""
        adv = pos ^ mask
        menaces_adv = cases_gagnantes(adv)
        alpha, beta = -INFINI, INFINI
        resultats = []
        self.courant = None
        for col, bit in coups:
            v = -self.negamax(adv, mask | bit, prof - 1, -beta, -alpha, 1, menaces_adv)
            resultats.append((v, col, bit))
            if v > alpha:
                alpha = v
                self.courant = (col, v)
        return resultats


def choisir_coup(plateau, temps_max=3.0, profondeur_max=40):
    """
    Renvoie la colonne (0..8) que l'IA doit jouer.
    `temps_max` : durée maximale de réflexion en secondes.
    """
    pos, mask = plateau.pos, plateau.mask
    possibles = (mask + BAS_TOUS) & PLATEAU
    colonnes = [c for c in ORDRE if possibles & CASES_COL[c]]
    if not colonnes:
        raise ValueError("Le plateau est plein.")
    if len(colonnes) == 1:
        return colonnes[0]
    if mask == 0:
        return LARGEUR // 2                              # on ouvre au centre

    # Victoire immédiate
    for c in colonnes:
        if est_gagnant(pos | (possibles & CASES_COL[c])):
            return c

    # Blocage obligatoire (si l'adversaire menace de gagner au prochain coup)
    adv = pos ^ mask
    menaces = cases_gagnantes(adv) & ~mask
    urgentes = menaces & possibles
    if urgentes:
        for c in colonnes:
            if urgentes & CASES_COL[c]:
                return c

    # Coups "sûrs" : ceux qui n'offrent pas la victoire à l'adversaire
    surs = possibles & ~(menaces >> 1)
    coups = []
    for c in ORDRE:
        b = (surs or possibles) & CASES_COL[c]
        if b:
            coups.append((c, b))
    if len(coups) == 1:
        return coups[0][0]

    recherche = _Recherche(temps_max)
    meilleur = coups[0][0]
    for prof in range(1, profondeur_max + 1):
        try:
            resultats = recherche.racine(pos, mask, prof, coups)
        except _TempsEcoule:
            # Itération interrompue : on garde son meilleur coup s'il est déjà connu
            if recherche.courant is not None:
                meilleur = recherche.courant[0]
            break
        resultats.sort(key=lambda r: -r[0])              # tri stable : le meilleur d'abord
        coups = [(col, bit) for _, col, bit in resultats]
        meilleur = coups[0][0]
        recherche.profondeur_atteinte = prof
        if resultats[0][0] >= SEUIL_MAT:                 # victoire forcée trouvée
            break
        if resultats[0][0] <= -SEUIL_MAT and prof >= 6:  # tout est perdu : inutile d'insister
            break
        if len(coups) == 1:
            break
        if prof >= HAUTEUR * LARGEUR - plateau.nb_coups:
            break
    choisir_coup.derniere_profondeur = recherche.profondeur_atteinte
    choisir_coup.derniers_noeuds = recherche.noeuds
    return meilleur


choisir_coup.derniere_profondeur = 0
choisir_coup.derniers_noeuds = 0

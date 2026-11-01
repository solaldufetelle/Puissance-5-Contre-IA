# Puissance 5

Jouez contre une IA à **Puissance 5** : il faut aligner **5 jetons** de la même couleur
(en ligne, en colonne ou en diagonale) sur un plateau de **7 lignes × 9 colonnes**.

- Menu pour choisir la couleur de son jeton (jaune ou rouge) et qui commence (vous ou l'IA)
- On clique directement dans les colonnes du plateau (ou touches `1` à `9` du clavier)
- Le dernier jeton posé est entouré de blanc
- Un jeton « fantôme » montre où tombera votre jeton quand vous survolez une colonne
- Les 5 jetons gagnants clignotent à la fin de la partie

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publier sur Streamlit Community Cloud

1. Mettez ces fichiers dans un dépôt GitHub (à la racine du dépôt) :

   ```
   app.py
   ia.py
   requirements.txt
   composant/index.html
   ```

2. Allez sur <https://share.streamlit.io>, connectez-vous avec GitHub, puis **Create app**.
3. Choisissez votre dépôt, la branche `main` et le fichier principal `app.py`, puis **Deploy**.

## Comment fonctionne l'IA

`ia.py` contient tout le moteur : plateau en *bitboards*, recherche négamax avec élagage
alpha-bêta, approfondissement itératif limité par le temps, table de transposition,
détection exacte des victoires / blocages / doubles menaces, et évaluation de toutes les
suites de 5 cases.

Pour changer la force de l'IA, modifiez `TEMPS_REFLEXION` en haut de `app.py`
(en secondes, 3.0 par défaut). Plus il est élevé, plus l'IA voit de coups à l'avance.

## Structure

| Fichier | Rôle |
|---|---|
| `app.py` | Interface Streamlit : menu, déroulement de la partie |
| `ia.py` | Règles du jeu et intelligence artificielle |
| `composant/index.html` | Plateau cliquable (SVG + JavaScript) branché sur Streamlit |

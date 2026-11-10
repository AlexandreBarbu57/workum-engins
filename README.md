# Bibliothèque Workum · engins et matériel de chantier

Modèles 3D libres (CC0 ou CC BY) pour les relevés 3D de [Workum](https://github.com/AlexandreBarbu57/htvrd-etudes-tirage) : engins, véhicules, levage, ouvrages électriques, balisage, installations de chantier.

- `catalogue.json` : liste des modèles avec nom, catégorie, dimension réelle de référence (longueur `L` ou hauteur `h`, en mètres), fichier, vignette, poids, auteur, licence et source. Servi par jsDelivr : `https://cdn.jsdelivr.net/gh/AlexandreBarbu57/workum-engins@main/catalogue.json`.
- `modeles/*.glb` : fichiers glTF binaires, sans extension de compression, prêts pour three.js.
- `vignettes/*.jpg` : aperçus.
- `LICENCES.md` : attributions, à conserver avec les modèles.
- `src/` : sources du catalogue et scripts de construction (`build_catalogue.py`, `glbinfo.py`).

Workum met chaque modèle à l'échelle en conservant ses proportions à partir de la dimension de référence ; les dimensions restent modifiables objet par objet. Les modèles stylisés ne remplacent pas les gabarits constructeur : pour le contrôle des distances électriques, ce sont les dimensions saisies qui font foi.

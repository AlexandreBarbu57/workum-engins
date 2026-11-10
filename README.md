# Bibliothèque Workum · engins et matériel de chantier

Modèles 3D libres (CC0 ou CC BY) pour les relevés 3D de [Workum](https://github.com/AlexandreBarbu57/htvrd-etudes-tirage) : engins, véhicules, levage, ouvrages électriques, balisage, installations de chantier, câbles et fourreaux. 72 modèles : 23 modèles stylisés issus de Poly Pizza et 49 modèles ou objets issus de Sketchfab (CC BY 4.0), dont huit engins réalistes (mini-pelle, chariot télescopique, nacelle à ciseaux, camion-grue, camions benne, compacteur, touret) et des objets extraits de packs (balisage, clôtures, feu de chantier, bungalow, groupe électrogène, transformateur, coffret, fourreaux…).

- `catalogue.json` : liste des modèles avec nom, catégorie, dimension réelle de référence (longueur `L` ou hauteur `h`, en mètres), fichier, vignette, poids, auteur, licence et source. Servi par jsDelivr : `https://cdn.jsdelivr.net/gh/AlexandreBarbu57/workum-engins@main/catalogue.json`.
- `modeles/*.glb` : fichiers glTF binaires, sans extension de compression, prêts pour three.js.
- `vignettes/*.jpg` : aperçus.
- `LICENCES.md` : attributions, à conserver avec les modèles.
- `src/` : sources du catalogue et outils, sans dépendance autre que Python 3 et `sips` (macOS) : `build_catalogue.py` (catalogue, licences, copie des modèles), `glbinfo.py` (lecture d'un GLB), `glb_light.py` (allègement : textures ré-échantillonnées, matériaux specular-glossiness convertis, nettoyage), `split_glb.py` (découpe d'un pack en un objet par fichier, remis à l'origine), `vignettes.html` (rendu des vignettes avec three.js, à ouvrir depuis un petit serveur local).

Ajouter un modèle : déposer le GLB dans `dl/` (hors dépôt), l'alléger ou le découper si besoin, compléter `src/catalogue_src.json` (nom, catégorie, `L` ou `h` en mètres, titre original, auteur, licence, source), générer la vignette, lancer `python3 src/build_catalogue.py`, pousser, puis purger le cache jsDelivr du catalogue (`https://purge.jsdelivr.net/gh/AlexandreBarbu57/workum-engins@main/catalogue.json`).

Workum met chaque modèle à l'échelle en conservant ses proportions à partir de la dimension de référence ; les dimensions restent modifiables objet par objet. Les modèles stylisés ne remplacent pas les gabarits constructeur : pour le contrôle des distances électriques, ce sont les dimensions saisies qui font foi.

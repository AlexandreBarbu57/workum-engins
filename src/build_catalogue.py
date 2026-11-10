#!/usr/bin/env python3
"""Construit catalogue.json, LICENCES.md et copie les modèles retenus dans modeles/ à partir de src/catalogue_src.json et dl/."""
import json, os, shutil, struct, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from glbinfo import info
src = json.load(open(os.path.join(ROOT, "src", "catalogue_src.json"), encoding="utf-8"))
os.makedirs(os.path.join(ROOT, "modeles"), exist_ok=True); os.makedirs(os.path.join(ROOT, "vignettes"), exist_ok=True)
out = {"v": src["v"], "nom": src["nom"], "date": datetime.date.today().isoformat(), "base": src["base"], "note": src["note"], "modeles": []}
lic = ["# Licences et attributions\n", f"Bibliothèque Workum · engins et matériel de chantier · {out['date']}\n", "Chaque modèle est l'œuvre de son auteur, publiée sous la licence indiquée (CC0 : domaine public ; CC BY : réutilisation libre, y compris commerciale, avec attribution). Les modèles Poly Pizza sont redistribués tels quels ou simplement renommés. Les modèles Sketchfab ont été modifiés pour l'usage dans Workum : textures ré-échantillonnées et recompressées, matériaux specular-glossiness convertis en métal-rugosité, packs découpés en un objet par fichier (`src/glb_light.py`, `src/split_glb.py`). Workum affiche ces attributions dans « À propos et licences » et dans les documents où les modèles apparaissent.\n", "| Modèle Workum | Titre original | Auteur | Licence | Source |", "|---|---|---|---|---|"]
for m in src["modeles"]:
    f = os.path.join(ROOT, "dl", m["src"] + ".glb")
    if not os.path.exists(f): print("absent :", f); continue
    dest = os.path.join(ROOT, "modeles", m["src"] + ".glb"); shutil.copyfile(f, dest)
    vig = os.path.join(ROOT, "vignettes", m["src"] + ".jpg")
    i = info(dest)
    e = {k: m[k] for k in ["id", "nom", "cat"]}
    if "L" in m: e["L"] = m["L"]
    if "h" in m: e["h"] = m["h"]
    e.update({"fichier": "modeles/" + m["src"] + ".glb", "vignette": "vignettes/" + m["src"] + ".jpg" if os.path.exists(vig) else None, "octets": i["octets"], "triangles": i["triangles"], "up": m.get("up", "y"),
              "titre": m["titre"], "auteur": m["auteur"], "licence": m["licence"], "via": m["via"], "source": m["source"]})
    out["modeles"].append(e)
    lic.append(f"| {m['nom']} | {m['titre']} | {m['auteur']} | {m['licence']} | [{m['via']}]({m['source']}) |")
json.dump(out, open(os.path.join(ROOT, "catalogue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(ROOT, "LICENCES.md"), "w", encoding="utf-8").write("\n".join(lic) + "\n")
print(len(out["modeles"]), "modèles,", sum(e["octets"] for e in out["modeles"]) // 1024, "Ko")

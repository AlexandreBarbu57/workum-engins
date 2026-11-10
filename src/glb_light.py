#!/usr/bin/env python3
"""Allège un fichier GLB sans outil externe (sips de macOS) : textures ré-échantillonnées au côté maximal demandé et
ré-encodées en JPEG (ou PNG si le matériau utilise la transparence), matériaux KHR_materials_pbrSpecularGlossiness
convertis en métal-rugosité standard (--metalrough), textures et vues de buffer inutilisées supprimées, BIN réaligné.
Usage : glb_light.py entree.glb sortie.glb [--max 1024] [--q 75] [--metalrough]"""
import struct, json, sys, os, subprocess, tempfile

MAGIC, JSON_T, BIN_T = 0x46546C67, 0x4E4F534A, 0x004E4942
SG = "KHR_materials_pbrSpecularGlossiness"

def read_glb(path):
    b = open(path, "rb").read()
    magic, ver, ln = struct.unpack_from("<III", b, 0)
    if magic != MAGIC: raise SystemExit("pas un GLB : " + path)
    off, j, bin_ = 12, None, b""
    while off < ln:
        cl, ct = struct.unpack_from("<II", b, off); off += 8
        chunk = b[off:off + cl]; off += cl
        if ct == JSON_T: j = json.loads(chunk)
        elif ct == BIN_T: bin_ = chunk
    return j, bin_

def write_glb(path, j, bin_):
    js = json.dumps(j, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    bin_ += b"\0" * ((4 - len(bin_) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", MAGIC, 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<II", len(js), JSON_T)); f.write(js)
        f.write(struct.pack("<II", len(bin_), BIN_T)); f.write(bin_)

def sips_props(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", "-g", "hasAlpha", path], capture_output=True, text=True).stdout
    d = dict(l.strip().partition(": ")[::2] for l in out.splitlines() if ": " in l)
    return int(d.get("pixelWidth", 0) or 0), int(d.get("pixelHeight", 0) or 0), d.get("hasAlpha", "no") == "yes"

def shrink(data, mime, maxpx, quality, keep_alpha):
    """Retourne (octets, mime, dims avant, dims après)."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in" + (".png" if mime == "image/png" else ".jpg")); open(src, "wb").write(data)
        w, h, alpha = sips_props(src)
        if not w: return data, mime, (0, 0), (0, 0)
        png = keep_alpha and alpha
        dst = os.path.join(td, "out." + ("png" if png else "jpg"))
        cmd = ["sips", "-s", "format", "png" if png else "jpeg"] + ([] if png else ["-s", "formatOptions", str(quality)])
        if max(w, h) > maxpx: cmd += ["-Z", str(maxpx)]
        subprocess.run(cmd + [src, "--out", dst], capture_output=True)
        if not os.path.exists(dst): return data, mime, (w, h), (w, h)
        out = open(dst, "rb").read(); w2, h2, _ = sips_props(dst)
        if len(out) >= len(data): return data, mime, (w, h), (w, h)
        return out, ("image/png" if png else "image/jpeg"), (w, h), (w2, h2)

def tex_infos(o, acc):
    """Collecte (dict textureInfo) de tous les champs *Texture d'un sous-arbre JSON."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k.endswith("Texture") and isinstance(v, dict) and "index" in v: acc.append(v)
            tex_infos(v, acc)
    elif isinstance(o, list):
        for v in o: tex_infos(v, acc)
    return acc

def alpha_images(j):
    """Index des images utilisées comme couleur de base par un matériau transparent (BLEND / MASK)."""
    tex = j.get("textures", []); res = set()
    for m in j.get("materials", []):
        if m.get("alphaMode", "OPAQUE") == "OPAQUE": continue
        bt = (m.get("pbrMetallicRoughness") or {}).get("baseColorTexture") or ((m.get("extensions") or {}).get(SG) or {}).get("diffuseTexture")
        if bt and bt.get("index") is not None and bt["index"] < len(tex) and "source" in tex[bt["index"]]: res.add(tex[bt["index"]]["source"])
    return res

def specgloss_to_metalrough(j):
    n = 0
    for m in j.get("materials", []):
        ext = (m.get("extensions") or {}).pop(SG, None)
        if ext is None: continue
        pbr = m.setdefault("pbrMetallicRoughness", {})
        if "diffuseFactor" in ext: pbr["baseColorFactor"] = ext["diffuseFactor"]
        if "diffuseTexture" in ext: pbr["baseColorTexture"] = ext["diffuseTexture"]
        pbr["metallicFactor"] = 0.0
        g = ext.get("glossinessFactor", 1.0)
        pbr["roughnessFactor"] = 0.6 if "specularGlossinessTexture" in ext else max(0.25, min(0.9, 1.0 - g))
        if not m.get("extensions"): m.pop("extensions", None)
        n += 1
    for k in ("extensionsUsed", "extensionsRequired"):
        if k in j:
            j[k] = [e for e in j[k] if e != SG]
            if not j[k]: del j[k]
    return n

def prune(j):
    """Supprime textures, images, samplers et vues de buffer non référencés (renumérotation comprise)."""
    infos = tex_infos(j.get("materials", []), [])
    used_t = sorted({ti["index"] for ti in infos})
    tmap = {t: k for k, t in enumerate(used_t)}
    for ti in infos: ti["index"] = tmap[ti["index"]]
    texs = [j["textures"][t] for t in used_t] if used_t else []
    used_i = sorted({t["source"] for t in texs if "source" in t}); imap = {i: k for k, i in enumerate(used_i)}
    used_s = sorted({t["sampler"] for t in texs if "sampler" in t}); smap = {s: k for k, s in enumerate(used_s)}
    for t in texs:
        if "source" in t: t["source"] = imap[t["source"]]
        if "sampler" in t: t["sampler"] = smap[t["sampler"]]
    imgs = [j["images"][i] for i in used_i] if used_i else []
    for k, arr in (("textures", texs), ("images", imgs), ("samplers", [j["samplers"][s] for s in used_s] if used_s else [])):
        if arr: j[k] = arr
        else: j.pop(k, None)
    if any("sparse" in a for a in j.get("accessors", [])): return  # cas rare : on ne touche pas aux vues
    used_v = sorted({a["bufferView"] for a in j.get("accessors", []) if "bufferView" in a} | {im["bufferView"] for im in j.get("images", []) if "bufferView" in im})
    vmap = {v: k for k, v in enumerate(used_v)}
    for a in j.get("accessors", []):
        if "bufferView" in a: a["bufferView"] = vmap[a["bufferView"]]
    for im in j.get("images", []):
        if "bufferView" in im: im["bufferView"] = vmap[im["bufferView"]]
    j["bufferViews"] = [j["bufferViews"][v] for v in used_v]

def light(src, dst, maxpx=1024, quality=75, metalrough=False, log=print):
    j, bin_ = read_glb(src)
    if len(j.get("buffers", [])) > 1: raise SystemExit("plusieurs buffers : non géré")
    if metalrough:
        n = specgloss_to_metalrough(j)
        if n: log(f"  {n} matériau(x) specular-glossiness convertis")
    # données des vues AVANT renumérotation
    old_views = [(bv, bin_[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]) for bv in j.get("bufferViews", [])]
    for k, bv in enumerate(j.get("bufferViews", [])): bv["_old"] = k
    prune(j)
    bvs = j.get("bufferViews", []); alpha = alpha_images(j); repl = {}
    for i, im in enumerate(j.get("images", [])):
        if "bufferView" not in im: log(f"  image {i} : uri externe, inchangée"); continue
        data = old_views[bvs[im["bufferView"]]["_old"]][1]
        out, mime, d0, d1 = shrink(data, im.get("mimeType", "image/png"), maxpx, quality, i in alpha)
        log(f"  image {i:2} {im.get('mimeType','?'):10} {d0[0]}×{d0[1]} {len(data)/1e6:5.2f} Mo → {mime:10} {d1[0]}×{d1[1]} {len(out)/1e6:5.2f} Mo" + ("  (alpha conservé)" if i in alpha else ""))
        if out is not data: repl[im["bufferView"]] = out; im["mimeType"] = mime
    nb = bytearray()
    for k, bv in enumerate(bvs):
        data = repl.get(k, old_views[bv["_old"]][1]); del bv["_old"]
        nb += b"\0" * ((4 - len(nb) % 4) % 4); bv["byteOffset"] = len(nb); bv["byteLength"] = len(data); nb += data
    j["buffers"] = [{"byteLength": len(nb)}]
    write_glb(dst, j, bytes(nb))
    log(f"  {os.path.basename(src)} : {os.path.getsize(src)/1e6:.2f} Mo → {os.path.basename(dst)} {os.path.getsize(dst)/1e6:.2f} Mo")

if __name__ == "__main__":
    a = sys.argv[1:]; maxpx = 1024; q = 75; mr = False
    if "--max" in a: maxpx = int(a[a.index("--max") + 1]); del a[a.index("--max"):a.index("--max") + 2]
    if "--q" in a: q = int(a[a.index("--q") + 1]); del a[a.index("--q"):a.index("--q") + 2]
    if "--metalrough" in a: mr = True; a.remove("--metalrough")
    if len(a) != 2: raise SystemExit(__doc__)
    light(a[0], a[1], maxpx, q, mr)

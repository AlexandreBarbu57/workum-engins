#!/usr/bin/env python3
"""Découpe un GLB multi-objets en un GLB par nœud d'une profondeur donnée (chaque objet remis à l'origine, posé sur le sol,
textures partagées ré-échantillonnées). Usage :
  split_glb.py pack.glb --depth 4 --list                       liste les objets avec leur boîte englobante
  split_glb.py pack.glb --depth 4 --out dossier [--max 512] [--q 75] [--only regex] [--prefix xx_]"""
import struct, json, sys, os, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glb_light import read_glb, write_glb, shrink, alpha_images

def quat_mat(q):
    x, y, z, w = q
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 0], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 0], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), 0], [0, 0, 0, 1]]
def mul(a, b): return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
def node_mat(n):
    if "matrix" in n: m = n["matrix"]; return [[m[c*4+r] for c in range(4)] for r in range(4)]
    t = n.get("translation", [0, 0, 0]); r = n.get("rotation", [0, 0, 0, 1]); s = n.get("scale", [1, 1, 1])
    return mul([[1,0,0,t[0]],[0,1,0,t[1]],[0,0,1,t[2]],[0,0,0,1]], mul(quat_mat(r), [[s[0],0,0,0],[0,s[1],0,0],[0,0,s[2],0],[0,0,0,1]]))
def tp(m, p): return [m[i][0]*p[0]+m[i][1]*p[1]+m[i][2]*p[2]+m[i][3] for i in range(3)]
I4 = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]

def nodes_at_depth(j, depth):
    res = []
    def walk(i, d, m):
        n = j["nodes"][i]; w = mul(m, node_mat(n))
        if d == depth: res.append((i, w)); return
        for c in n.get("children", []): walk(c, d + 1, w)
    for r in j["scenes"][j.get("scene", 0)]["nodes"]: walk(r, 0, I4)
    return res

def bbox(j, root, W):
    lo = [math.inf]*3; hi = [-math.inf]*3; tris = 0
    def walk(i, pm):
        nonlocal tris
        n = j["nodes"][i]; m = mul(pm, node_mat(n))
        if "mesh" in n:
            for p in j["meshes"][n["mesh"]]["primitives"]:
                a = j["accessors"][p["attributes"]["POSITION"]]
                tris += (j["accessors"][p["indices"]]["count"] if "indices" in p else a["count"]) // 3
                for cx in (a["min"][0], a["max"][0]):
                    for cy in (a["min"][1], a["max"][1]):
                        for cz in (a["min"][2], a["max"][2]):
                            q = tp(m, [cx, cy, cz])
                            for k in range(3): lo[k] = min(lo[k], q[k]); hi[k] = max(hi[k], q[k])
        for c in n.get("children", []): walk(c, m)
    # W est la matrice monde du parent du nœud racine ; on inclut la transformation du nœud lui-même via walk
    walk(root, W)
    return lo, hi, tris

def ext_names(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "extensions" and isinstance(v, dict): acc.update(v.keys())
            ext_names(v, acc)
    elif isinstance(o, list):
        for v in o: ext_names(v, acc)

def extract(j, bin_, root, Wparent, maxpx, q, cache):
    nodes, meshes, accs, mats = [], set(), [], set()
    def walk(i):
        nodes.append(i); n = j["nodes"][i]
        if "mesh" in n: meshes.add(n["mesh"])
        for c in n.get("children", []): walk(c)
    walk(root)
    meshes = sorted(meshes)
    for mi in meshes:
        for p in j["meshes"][mi]["primitives"]:
            for a in p["attributes"].values(): accs.append(a)
            if "indices" in p: accs.append(p["indices"])
            if "material" in p: mats.add(p["material"])
    accs = sorted(set(accs)); mats = sorted(mats)
    texs = set()
    def find_tex(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.endswith("Texture") and isinstance(v, dict) and "index" in v: texs.add(v["index"])
                find_tex(v)
        elif isinstance(o, list):
            for v in o: find_tex(v)
    for mi in mats: find_tex(j["materials"][mi])
    texs = sorted(texs)
    imgs = sorted({j["textures"][t]["source"] for t in texs if "source" in j["textures"][t]})
    samps = sorted({j["textures"][t]["sampler"] for t in texs if "sampler" in j["textures"][t]})
    alpha = alpha_images(j)
    CT = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}; NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
    # nouveau BIN : une plage par accesseur (regroupées quand la vue est entrelacée), une vue par image
    nb = bytearray(); newviews = []; abv = {}; groups = {}
    for a in accs:
        src = j["accessors"][a]
        if "bufferView" not in src: continue
        bv = j["bufferViews"][src["bufferView"]]; elem = CT[src["componentType"]] * NC[src["type"]]; stride = bv.get("byteStride") or elem
        start = bv.get("byteOffset", 0) + src.get("byteOffset", 0)
        key = (src["bufferView"], start // stride) if stride > elem else (src["bufferView"], a)
        groups.setdefault(key, []).append((a, start, stride * (src["count"] - 1) + elem, elem, stride))
    for key, members in groups.items():
        bv = j["bufferViews"][key[0]]
        rs = min(m[1] for m in members); re_ = max(m[1] + m[2] for m in members)
        data = bin_[rs:re_]; nb += b"\0" * ((4 - len(nb) % 4) % 4)
        nbv = {"buffer": 0, "byteOffset": len(nb), "byteLength": len(data)}
        if any(m[4] > m[3] for m in members): nbv["byteStride"] = members[0][4]
        if "target" in bv: nbv["target"] = bv["target"]
        nb += data
        for m in members: abv[m[0]] = (len(newviews), m[1] - rs)
        newviews.append((nbv, None))
    ibv = {}
    for i in imgs:
        im = j["images"][i]
        if "bufferView" not in im: continue
        bv = j["bufferViews"][im["bufferView"]]; data = bin_[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]]
        if i not in cache: cache[i] = shrink(data, im.get("mimeType", "image/png"), maxpx, q, i in alpha)[:2]
        data, mime = cache[i]
        nb += b"\0" * ((4 - len(nb) % 4) % 4); ibv[i] = (len(newviews), mime); newviews.append(({"buffer": 0, "byteOffset": len(nb), "byteLength": len(data)}, mime)); nb += data
    amap = {a: k for k, a in enumerate(accs)}; mmap = {m: k for k, m in enumerate(mats)}; tmap = {t: k for k, t in enumerate(texs)}
    imap = {i: k for k, i in enumerate(imgs)}; smap = {s: k for k, s in enumerate(samps)}; nmap = {n: k for k, n in enumerate(nodes)}; memap = {m: k for k, m in enumerate(meshes)}
    out = {"asset": {"version": "2.0", "generator": "Workum split_glb"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [], "meshes": [], "accessors": [], "bufferViews": [bv for bv, _ in newviews], "buffers": [{"byteLength": len(nb)}]}
    for a in accs:
        na = dict(j["accessors"][a]); na.pop("sparse", None)
        if a in abv: na["bufferView"], na["byteOffset"] = abv[a]
        else: na.pop("bufferView", None); na.pop("byteOffset", None)
        out["accessors"].append(na)
    for mi in meshes:
        nm = {"primitives": []}
        for p in j["meshes"][mi]["primitives"]:
            np_ = {"attributes": {k: amap[v] for k, v in p["attributes"].items()}}
            if "indices" in p: np_["indices"] = amap[p["indices"]]
            if "material" in p: np_["material"] = mmap[p["material"]]
            if "mode" in p: np_["mode"] = p["mode"]
            nm["primitives"].append(np_)
        out["meshes"].append(nm)
    # remise à l'origine : boîte englobante dans le repère monde du pack
    lo, hi, tris = bbox(j, root, Wparent)
    cx, cz, my = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2, lo[1]
    Wroot = mul(mul([[1,0,0,-cx],[0,1,0,-my],[0,0,1,-cz],[0,0,0,1]], Wparent), node_mat(j["nodes"][root]))
    for n in nodes:
        src = j["nodes"][n]; nn = {}
        if src.get("name"): nn["name"] = src["name"]
        if "mesh" in src: nn["mesh"] = memap[src["mesh"]]
        if src.get("children"): nn["children"] = [nmap[c] for c in src["children"]]
        if n == root: nn["matrix"] = [Wroot[r][c] for c in range(4) for r in range(4)]
        else:
            for k in ("matrix", "translation", "rotation", "scale"):
                if k in src: nn[k] = src[k]
        out["nodes"].append(nn)
    if mats:
        out["materials"] = []
        def remap_tex(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k.endswith("Texture") and isinstance(v, dict) and "index" in v: v["index"] = tmap[v["index"]]
                    remap_tex(v)
            elif isinstance(o, list):
                for v in o: remap_tex(v)
        for mi in mats:
            m = json.loads(json.dumps(j["materials"][mi])); remap_tex(m); out["materials"].append(m)
    if texs:
        out["textures"] = []
        for t in texs:
            nt = {}
            if "source" in j["textures"][t]: nt["source"] = imap[j["textures"][t]["source"]]
            if "sampler" in j["textures"][t]: nt["sampler"] = smap[j["textures"][t]["sampler"]]
            out["textures"].append(nt)
        out["images"] = []
        for i in imgs:
            im = dict(j["images"][i])
            if i in ibv:
                im["bufferView"], mime = ibv[i]
                if mime: im["mimeType"] = mime
            out["images"].append(im)
        if samps: out["samplers"] = [j["samplers"][s] for s in samps]
    used = set(); ext_names(out, used)
    if used: out["extensionsUsed"] = sorted(used)
    req = [e for e in j.get("extensionsRequired", []) if e in used]
    if req: out["extensionsRequired"] = req
    size = [round(hi[k] - lo[k], 4) for k in range(3)]
    return out, bytes(nb), size, tris

def slug(s): s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_"); return s.lower()

if __name__ == "__main__":
    a = sys.argv[1:]
    def opt(name, default=None, flag=False):
        if name in a:
            i = a.index(name)
            if flag: del a[i]; return True
            v = a[i + 1]; del a[i:i + 2]; return v
        return default
    depth = int(opt("--depth", 1)); lst = opt("--list", flag=True); outdir = opt("--out"); maxpx = int(opt("--max", 512)); q = int(opt("--q", 75)); only = opt("--only"); prefix = opt("--prefix", "")
    src = a[0]; j, bin_ = read_glb(src)
    cache = {}; n = 0; total = 0
    for i, W in nodes_at_depth(j, depth):
        name = j["nodes"][i].get("name", "n%d" % i)
        if only and not re.search(only, name, re.I): continue
        Wparent = W  # matrice monde du nœud lui-même ; on retire sa propre transformation pour obtenir celle du parent
        # (bbox et extract réappliquent node_mat(root)) : inverse non nécessaire, on passe la matrice du parent calculée séparément
        if lst:
            lo, hi, tris = bbox(j, i, I4_parent[i]) if False else (None, None, None)
        n += 1
    # seconde passe propre : calcul des matrices parent
    parents = {}
    def walk(i, d, m):
        nd = j["nodes"][i]
        if d == depth: parents[i] = m; return
        for c in nd.get("children", []): walk(c, d + 1, mul(m, node_mat(nd)))
    for r in j["scenes"][j.get("scene", 0)]["nodes"]: walk(r, 0, I4)
    if outdir: os.makedirs(outdir, exist_ok=True)
    for i, Wp in parents.items():
        name = j["nodes"][i].get("name", "n%d" % i)
        if only and not re.search(only, name, re.I): continue
        if lst:
            lo, hi, tris = bbox(j, i, Wp)
            print(f"{i:4} {name[:44]:44} tris={tris:6}  L×h×l = {hi[0]-lo[0]:7.3f} × {hi[1]-lo[1]:7.3f} × {hi[2]-lo[2]:7.3f}")
            continue
        out, nb, size, tris = extract(j, bin_, i, Wp, maxpx, q, cache)
        f = os.path.join(outdir, prefix + slug(name) + ".glb"); write_glb(f, out, nb); total += os.path.getsize(f)
        print(f"{slug(name):40} {os.path.getsize(f)/1e3:8.1f} Ko tris={tris:6} taille={size}")
    if outdir: print(f"total {total/1e6:.2f} Mo")

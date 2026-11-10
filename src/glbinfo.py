import json, struct, sys, os
def info(path):
    with open(path, "rb") as f: data = f.read()
    magic, ver, length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF": return {"err": "pas un GLB"}
    off = 12; j = None; binlen = 0
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off); chunk = data[off+8:off+8+clen]
        if ctype == 0x4E4F534A: j = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942: binlen = clen
        off += 8 + clen
    tris = 0
    for m in j.get("meshes", []):
        for p in m.get("primitives", []):
            if "indices" in p: tris += j["accessors"][p["indices"]]["count"] // 3
            else: tris += j["accessors"][p["attributes"]["POSITION"]]["count"] // 3
    imgs = [(i.get("mimeType"), j["bufferViews"][i["bufferView"]]["byteLength"] if "bufferView" in i else i.get("uri", "")[:30]) for i in j.get("images", [])]
    return {"octets": len(data), "bin": binlen, "nodes": len(j.get("nodes", [])), "meshes": len(j.get("meshes", [])), "triangles": tris, "images": imgs, "materials": len(j.get("materials", [])), "ext": j.get("extensionsUsed", []), "anim": len(j.get("animations", []))}
for p in sys.argv[1:]: print(os.path.basename(p), json.dumps(info(p), ensure_ascii=False))

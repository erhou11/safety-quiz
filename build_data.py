"""合并五套题数据 -> questions_full.json（含 sets 元数据）。"""
import json, os, shutil, hashlib

BASE = "/home/hatch/workspace/quizapp"
www = os.path.join(BASE, "www")

# --- set 1：已有数据（兼容旧 list 格式与新 dict 格式，可重复构建） ---
raw = json.load(open(os.path.join(BASE, "questions_full.json"), encoding="utf-8"))
old = raw["questions"] if isinstance(raw, dict) else raw
set1 = []
for q in old:
    if q.get("set", "s1") != "s1":
        continue
    nq = dict(q)
    nq["set"] = "s1"
    set1.append(nq)

def build_set(sid, json_path, img_subdir, existing):
    """由 parse_setN.py 的原始 json 构建；源图片不在时复用已构建好的条目。"""
    imgdir = os.path.join(www, img_subdir)
    os.makedirs(imgdir, exist_ok=True)
    out = []
    for q in json.load(open(os.path.join(BASE, json_path), encoding="utf-8")):
        nq = {
            "set": sid, "n": q["n"], "cat": q["cat"], "type": q["type"],
            "stem": q["stem"], "answer": q["answer"], "explanation": q["explanation"],
            "images": [], "exp_images": [],
            "options": [{"text": o["text"]} for o in q["options"]],
        }
        def add_img(u, field):
            if os.path.exists(u):
                raw = open(u, "rb").read()
                name = hashlib.sha256(raw).hexdigest()[:12] + ".png"
                dst = os.path.join(imgdir, name)
                if not os.path.exists(dst):
                    shutil.copyfile(u, dst)
                nq[field].append(img_subdir + "/" + name)
            elif q["n"] in existing:
                nq[field] = existing[q["n"]][field]
            else:
                raise FileNotFoundError(f"{sid} Q{q['n']} 图片源丢失: {u}")
        for u in q["images"]:
            add_img(u, "images")
        for u in q.get("exp_images", []):
            add_img(u, "exp_images")
        out.append(nq)
    return out

existing_by_set_n = {}
for q in old:
    existing_by_set_n.setdefault((q.get("set", "s1"), q["n"]), q)

# --- set 2 / set 3 ---
set2 = build_set("s2", "questions_set2.json", "img2",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s2"})
set3 = build_set("s3", "questions_set3.json", "img3",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s3"})
set4 = build_set("s4", "questions_set4.json", "img4",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s4"})
set5 = build_set("s5", "questions_set5.json", "img5",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s5"})

sets = [
    {"id": "s1", "title": "2026 点题锁分班 · 第4套", "kicker": "2026 点题锁分班",
     "desc": "覆盖机械安全、电气安全、危险化学品与防火防爆等重点。选择答案后立即核对，并结合解析巩固考点。"},
    {"id": "s2", "title": "安全技术基础阶段评测一", "kicker": "2026 阶段评测",
     "desc": "按 2025 真题难度呈现，知识点覆盖全面，陷阱题型典型，适合考前重复练习。"},
    {"id": "s3", "title": "安全技术基础阶段评测二", "kicker": "2026 阶段评测",
     "desc": "李天宇 8 套卷之二，难度对标真题，覆盖机械、电气、危化品等高频考点，适合刷题巩固。"},
    {"id": "s4", "title": "2026 点题锁分班 · 第1套", "kicker": "2026 点题锁分班",
     "desc": "点题锁分第 1 讲，机械安全与电气安全重点突出，题型紧扣考点，适合系统复习。"},
    {"id": "s5", "title": "李天宇 8 套卷 · 第 5 套", "kicker": "2026 点题锁分班",
     "desc": "点题锁分班（三），李天宇 8 套卷之五，题型紧贴考点，适合考前冲刺刷题。"},
]
out = {"sets": sets, "questions": set1 + set2 + set3 + set4 + set5}
with open(os.path.join(BASE, "questions_full.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
for s in sets:
    qs = [q for q in out["questions"] if q["set"] == s["id"]]
    print(s["id"], s["title"], len(qs), "题，单选",
          sum(1 for q in qs if q["type"] == "single"), "多选",
          sum(1 for q in qs if q["type"] == "multi"))
print("img2 文件数:", len(os.listdir(os.path.join(www, "img2"))))
print("img3 文件数:", len(os.listdir(os.path.join(www, "img3"))))
print("img4 文件数:", len(os.listdir(os.path.join(www, "img4"))))
print("img5 文件数:", len(os.listdir(os.path.join(www, "img5"))))

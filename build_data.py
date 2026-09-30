"""合并两套题数据 -> questions_full.json（含 sets 元数据）。"""
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

# --- set 2：新解析 ---
s2 = json.load(open(os.path.join(BASE, "questions_set2.json"), encoding="utf-8"))
img2dir = os.path.join(www, "img2")
os.makedirs(img2dir, exist_ok=True)
set2 = []
for q in s2:
    nq = {
        "set": "s2", "n": q["n"], "cat": q["cat"], "type": q["type"],
        "stem": q["stem"], "answer": q["answer"], "explanation": q["explanation"],
        "images": [], "exp_images": [],
        "options": [{"text": o["text"]} for o in q["options"]],
    }
    for u in q["images"]:
        raw = open(u, "rb").read()
        name = hashlib.sha256(raw).hexdigest()[:12] + ".png"
        dst = os.path.join(img2dir, name)
        if not os.path.exists(dst):
            shutil.copyfile(u, dst)
        nq["images"].append("img2/" + name)
    set2.append(nq)

sets = [
    {"id": "s1", "title": "2026 点题锁分班 · 第4套", "kicker": "2026 点题锁分班",
     "desc": "覆盖机械安全、电气安全、危险化学品与防火防爆等重点。选择答案后立即核对，并结合解析巩固考点。"},
    {"id": "s2", "title": "安全技术基础阶段评测一", "kicker": "2026 阶段评测",
     "desc": "按 2025 真题难度呈现，知识点覆盖全面，陷阱题型典型，适合考前重复练习。"},
]
out = {"sets": sets, "questions": set1 + set2}
with open(os.path.join(BASE, "questions_full.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
for s in sets:
    qs = [q for q in out["questions"] if q["set"] == s["id"]]
    print(s["id"], s["title"], len(qs), "题，单选",
          sum(1 for q in qs if q["type"] == "single"), "多选",
          sum(1 for q in qs if q["type"] == "multi"))
print("img2 文件数:", len(os.listdir(img2dir)))

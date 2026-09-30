"""合并十套题数据 -> questions_full.json（含 sets 元数据）。"""
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
set6 = build_set("s6", "questions_set6.json", "img6",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s6"})
set7 = build_set("s7", "questions_set7.json", "img7",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s7"})
set8 = build_set("s8", "ocr_work/questions_set8.json", "img8",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s8"})
set9 = build_set("s9", "ocr_work/questions_set9.json", "img9",
                 {n: q for (s, n), q in existing_by_set_n.items() if s == "s9"})
set10 = build_set("s10", "ocr_work/questions_fagui1.json", "img10",
                  {n: q for (s, n), q in existing_by_set_n.items() if s == "s10"})
set11 = build_set("s11", "ocr_work/questions_fagui2.json", "img11",
                  {n: q for (s, n), q in existing_by_set_n.items() if s == "s11"})

subjects = [
    {"id": "fagui", "title": "法规", "desc": "安全生产法律法规"},
    {"id": "guanli", "title": "管理", "desc": "安全生产管理"},
    {"id": "jishu", "title": "技术", "desc": "安全生产技术基础"},
    {"id": "meikuang", "title": "煤矿", "desc": "安全生产专业实务·煤矿安全"},
    {"id": "kuangshan", "title": "矿山", "desc": "安全生产专业实务·金属非金属矿山安全"},
    {"id": "huagong", "title": "化工", "desc": "安全生产专业实务·化工安全"},
    {"id": "yelian", "title": "冶炼", "desc": "安全生产专业实务·金属冶炼安全"},
    {"id": "jianzhu", "title": "建筑", "desc": "安全生产专业实务·建筑施工安全"},
    {"id": "daolu", "title": "道路", "desc": "安全生产专业实务·道路运输安全"},
    {"id": "qita", "title": "其他", "desc": "安全生产专业实务·其他安全"},
]
sets = [
    # 按"技术李第N套"统一编号，按课程进度排序
    {"id": "s2", "subject": "jishu", "title": "技术李第1套", "kicker": "阶段测评",
     "desc": "第01讲 阶段测评一（一），基础阶段自测。"},
    {"id": "s3", "subject": "jishu", "title": "技术李第2套", "kicker": "阶段测评",
     "desc": "李天宇8套卷·第2套，阶段测评班（二）。"},
    {"id": "s4", "subject": "jishu", "title": "技术李第3套", "kicker": "点题锁分",
     "desc": "第01讲 点题锁分一（一）。"},
    {"id": "s1", "subject": "jishu", "title": "技术李第4套", "kicker": "点题锁分",
     "desc": "第01讲 点题锁分一（四）。"},
    {"id": "s5", "subject": "jishu", "title": "技术李第5套", "kicker": "点题锁分",
     "desc": "李天宇8套卷·第5套，点题锁分班（三）。"},
    {"id": "s6", "subject": "jishu", "title": "技术李第6套", "kicker": "模考大赛",
     "desc": "李天宇8套卷·第6套，模考大赛班。"},
    {"id": "s7", "subject": "jishu", "title": "技术李第7套", "kicker": "模考金题",
     "desc": "第01讲 模考金题一（一）。"},
    {"id": "s8", "subject": "jishu", "title": "技术顺利1套", "kicker": "顺利押题",
     "desc": "注安技术顺利押题1。"},
    {"id": "s9", "subject": "jishu", "title": "技术顺利2套", "kicker": "顺利押题",
     "desc": "注安技术顺利押题2。"},
    {"id": "s10", "subject": "fagui", "title": "法规唐第1套", "kicker": "阶段测评",
     "desc": "唐忍-2026安全生产法律法规-阶段测评（一）。"},
    {"id": "s11", "subject": "fagui", "title": "法规安第1套", "kicker": "阶段测评",
     "desc": "安勇-2026安全生产法律法规-阶段测评（二）。"},
]
out = {"subjects": subjects, "sets": sets, "questions": set2 + set3 + set4 + set1 + set5 + set6 + set7 + set8 + set9 + set10 + set11}
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
print("img6 文件数:", len(os.listdir(os.path.join(www, "img6"))))
print("img7 文件数:", len(os.listdir(os.path.join(www, "img7"))))
print("img8 文件数:", len(os.listdir(os.path.join(www, "img8"))))
print("img9 文件数:", len(os.listdir(os.path.join(www, "img9"))))
print("img10 文件数:", len(os.listdir(os.path.join(www, "img10"))))
print("img11 文件数:", len(os.listdir(os.path.join(www, "img11"))))

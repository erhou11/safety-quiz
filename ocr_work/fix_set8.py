"""从 raw8 (qs+ans) 合并并手工修复 set8"""
import json

W = "/home/hatch/workspace/quizapp/ocr_work"
raw = json.load(open(f"{W}/raw8.json"))
qs, ans = raw["qs"], {int(k): v for k, v in raw["ans"].items()}

merged = {}
for q in qs:
    a = ans.get(q["n"])
    merged[q["n"]] = {
        "n": q["n"], "type": "multi" if (a and len(a["answer"]) > 1) else "single",
        "cat": "", "stem": q["stem"],
        "options": [{"key": o["k"], "text": o["t"]} for o in q["options"]],
        "answer": a["answer"] if a else [],
        "explanation": a["explanation"] if a else "",
        "images": [], "exp_images": [],
    }

def set_opts(n, opts):
    merged[n]["options"] = [{"key": k, "text": t} for k, t in opts]

def set_ans(n, answer, typ=None, exp=None):
    merged[n]["answer"] = answer
    if typ: merged[n]["type"] = typ
    if exp is not None: merged[n]["explanation"] = exp

# Q2: 补 A；答案 B；解释去乱码
set_opts(2, [("A", "0.2s"), ("B", "0.4s"), ("C", "0.5s"), ("D", "5s")])
set_ans(2, ["B"], exp="对于供给手持式电动工具、移动式电气设备的线路或插座回路，电压220V者故障持续时间不应超过0.4s，故B正确")
# Q10: C
set_opts(10, [("A", "刀轴采用装配式的方形刀轴"),
              ("B", "刀体上的装刀梯形槽应下底靠圆心，上底在外"),
              ("C", "刀轴组装后必须经强度试验或离心试验"),
              ("D", "组装后刨刃轴应为全开式结构")])
# Q19: 补 C/D；答案 B
set_opts(19, [("A", "1~2"), ("B", "2~3"), ("C", "3~5"), ("D", "5~10")])
set_ans(19, ["B"])
# Q20: 补 D
set_opts(20, [(o["key"], o["text"]) for o in merged[20]["options"] if o["key"] in "ABC"] +
              [("D", "放电击穿是固体绝缘在强电场作用下，内部气泡首先发生碰撞电离而放电")])
# Q27: 上标
set_opts(27, [("A", "1×10⁷Ω·m"), ("B", "1×10⁸Ω·m"), ("C", "1×10⁹Ω·m"), ("D", "1×10¹⁰Ω·m")])
set_ans(27, ["D"], exp="对于液体，电阻率1×10⁷Ω·m以下的液体，由于泄漏较强而不容易积累静电；电阻率1×10¹⁰Ω·m左右的液体最容易产生静电，故D正确")
# Q28: 整题插入
merged[28] = {"n": 28, "type": "single", "cat": "",
    "stem": "锅炉蒸发表面汽水共同升起，产生大量泡沫上下波动翻腾的现象，下面关于汽水共腾的处理，正确的是（）",
    "options": [{"key": "A", "text": "减弱燃烧力度，降低负荷，开大主汽阀"},
                {"key": "B", "text": "加强蒸汽管道和过热器的疏水"},
                {"key": "C", "text": "关闭连续排污阀"},
                {"key": "D", "text": "同时不应上水"}],
    "answer": ["B"],
    "explanation": "①减弱燃烧力度，降低负荷，关小主汽阀。故A不正确②加强蒸汽管道和过热器的疏水。故B正确③全开连续排污阀，并打开定期排污阀放水。故C不正确④同时上水，以改善锅水的品质。故D不正确",
    "images": [], "exp_images": []}
# Q13: 解析被水印吞了，手工补
set_ans(13, ["C"], exp="型砂制备和砂再生设备输送长度大于3m的带式输送机应设置双侧拉绳开关，故C正确")
# Q30/Q47/Q82 答案
set_ans(30, ["A"], exp="A属于年度检查项目。使用单位每月对所使用的压力容器至少进行一次月度检查，并应当记录检查情况。月度检查内容主要为压力容器本体及其安全附件、装卸附件、安全保护装置、测量调控装置、附属仪器仪表是否完好，各密封面有无泄漏，以及其他异常情况等。使用单位每年对所使用的压力容器至少进行一次年度检查。年度检查项目至少包括压力容器安全管理情况、压力容器本体及其运行状况和压力容器安全附件检查等。")
set_ans(47, ["D"], exp="一般说来爆炸现象具有以下四种特征：(1)爆炸过程高速进行。故A正确(2)爆炸点附近压力急剧升高，多数爆炸伴有温度升高。故B正确(3)发出或大或小的响声。故C正确(4)周围介质发生震动或邻近的物质遭到破坏。爆炸最主要的特征是爆炸点及其周围压力急剧升高。故D不正确")
set_ans(82, ["A", "C", "D"], typ="multi",
        exp="根据工作原理的不同，定温火灾探测器又可分为双金属片定温探测器、热敏电阻定温探测器、低熔点合金探测器等。故ACD正确")
# Q36: 补 C/D
set_opts(36, [("A", "0"), ("B", "Ⅰ"), ("C", "Ⅱ"), ("D", "Ⅲ")])
# Q45: D（注意 C 的文本尾部混入了 D 的乱码行，先截掉）
c45 = merged[45]["options"][2]["text"].split("超神于")[0]
set_opts(45, [("A", merged[45]["options"][0]["text"]),
              ("B", merged[45]["options"][1]["text"]),
              ("C", c45),
              ("D", "对于复杂的可燃固体化合物，受热后不能分解")])
# Q54: 补 D；答案 D（注意 raw 里混入了 Q55 的选项，只取前 3 个）
set_opts(54, [(o["key"], o["text"]) for o in merged[54]["options"][:3]] +
              [("D", "2.5")])
set_ans(54, ["D"], exp="成箱成品堆垛的高度不应超过2.5m，故D正确")
# Q55: 整题插入
merged[55] = {"n": 55, "type": "single", "cat": "",
    "stem": "下列不属于工业雷管的是（）",
    "options": [{"key": "A", "text": "继爆管"},
                {"key": "B", "text": "导爆管雷管"},
                {"key": "C", "text": "电子雷管"},
                {"key": "D", "text": "塑料导爆管"}],
    "answer": ["D"],
    "explanation": "工业雷管如工业电雷管、磁电雷管、电子雷管、导爆管雷管、继爆管等，ABC属于工业雷管；D属于工业索类火工品。工业索类火工品如工业导火索、工业导爆索、切割索、塑料导爆管、引火线。",
    "images": [], "exp_images": []}
# Q63: B/C 去乱码
set_opts(63, [("A", "温度较高地区装运液化气体和易燃液体等危险物品，要有防晒设施"),
              ("B", "放射性物品应用专用运输搬运车和抬架搬运，装卸机械应按规定负荷降低20%的装卸量"),
              ("C", "遇水燃烧物品及有毒物品，禁止用小型机帆船、小木船和水泥船承运"),
              ("D", "运输易燃易爆危险货物车辆的排气管，应安装隔热和熄灭火星装置，并配装导静电橡胶拖地带装置")])
# Q71: 选项被水印破坏，按原图+解析重建（D 据解析"检查、维修由人承担"还原为标准表述）
set_opts(71, [("A", "精度高的"),
              ("B", "图形辨认"),
              ("C", "高阶运算的"),
              ("D", "检查和维修的"),
              ("E", "操作复杂的")])
set_ans(71, ["A", "C", "E"], typ="multi")

out = [merged[n] for n in sorted(merged)]
assert sorted(merged) == list(range(1, 86)), f"题号不连续: {sorted(set(range(1,86))-set(merged))}"
for q in out:
    assert len(q["options"]) in (4, 5), f"Q{q['n']} 选项数 {len(q['options'])}"
    for L in q["answer"]:
        assert L in [o["key"] for o in q["options"]], f"Q{q['n']} 答案{L}非法"
    assert q["answer"] and q["explanation"], f"Q{q['n']} 缺答案/解析"
s = sum(1 for q in out if q["type"] == "single")
m = sum(1 for q in out if q["type"] == "multi")
print(f"set8 OK: 共{len(out)}题 单选{s} 多选{m}")
json.dump(out, open(f"{W}/questions_set8.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

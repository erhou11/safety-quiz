"""调试：打印指定题号在 OCR 行中的上下文"""
import json, re, sys

W = "/home/hatch/workspace/quizapp/ocr_work"
ocr = json.load(open(f"{W}/ocr_lines.json"))

def show(tag_prefix, qn, context=6):
    tags = sorted([t for t in ocr if t.startswith(tag_prefix)],
                  key=lambda t: int(t.rsplit("_p", 1)[1]))
    all_lines = []
    for t in tags:
        for l in ocr[t]:
            all_lines.append((t, l))
    for i, (t, l) in enumerate(all_lines):
        if re.match(rf"^{qn}[、.．]", l["t"]):
            print(f"=== {tag_prefix} Q{qn} @ {t} ===")
            for j in range(max(0, i-context), min(len(all_lines), i+context+10)):
                mark = ">>>" if j == i else "   "
                print(f"{mark} {all_lines[j][0]} {all_lines[j][1]['c']} {all_lines[j][1]['t'][:80]!r}")
            print()
            return
    print(f"{tag_prefix} Q{qn}: 未找到题号行")

if __name__ == "__main__":
    show(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)

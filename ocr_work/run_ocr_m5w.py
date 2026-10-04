"""OCR worker: 处理 sp 页面区间 [p1, p2] -> ocr_m5_part_{tag}.json"""
import json, glob, os, sys
from rapidocr_onnxruntime import RapidOCR

W = os.path.expanduser("~/workspace/quizapp/ocr_work")
p1, p2, tag = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
ocr = RapidOCR()
out = {}
files = sorted(glob.glob(os.path.join(W, "m5", "sp*.png")))
files = [f for f in files if p1 <= int(os.path.basename(f)[2:4]) <= p2]
print("pages:", len(files), flush=True)
for i, fp in enumerate(files):
    name = os.path.basename(fp)[:-4]
    try:
        result = ocr(fp)
        lines = []
        for box, text, conf in (result[0] or []):
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append({"x": (min(xs) + max(xs)) / 2, "y": (min(ys) + max(ys)) / 2,
                          "w": max(xs) - min(xs),
                          "t": text, "c": round(float(conf), 3)})
        out[name] = lines
        print("[%d/%d] %s: %d lines" % (i + 1, len(files), name, len(lines)), flush=True)
    except Exception as e:
        print("[%d/%d] %s ERROR %s" % (i + 1, len(files), name, e), flush=True)
        out[name] = []
    json.dump(out, open(os.path.join(W, "ocr_m5_part_%s.json" % tag), "w", encoding="utf-8"),
                   ensure_ascii=False)
print("DONE", tag)

"""OCR 顺利法规模拟卷5套合集: m5/spNN.png -> ocr_m5.json"""
import json, glob, os
from rapidocr_onnxruntime import RapidOCR

W = os.path.expanduser("~/workspace/quizapp/ocr_work")
ocr = RapidOCR()
out = {}
files = sorted(glob.glob(os.path.join(W, "m5", "sp*.png")))
print("pages:", len(files), flush=True)
for i, fp in enumerate(files):
    tag = os.path.basename(fp)[:-4]
    try:
        result = ocr(fp)
        lines = []
        for box, text, conf in (result[0] or []):
            xs = [p[0] for p in box]; ys = [p[1] for p in box]
            lines.append({"x": (min(xs)+max(xs))/2, "y": (min(ys)+max(ys))/2,
                          "w": max(xs)-min(xs),
                          "t": text, "c": round(float(conf), 3)})
        out[tag] = lines
        print(f"[{i+1}/{len(files)}] {tag}: {len(lines)} lines", flush=True)
    except Exception as e:
        print(f"[{i+1}/{len(files)}] {tag} ERROR {e}", flush=True)
        out[tag] = []
    if (i+1) % 10 == 0:
        json.dump(out, open(os.path.join(W, "ocr_m5.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(out, open(os.path.join(W, "ocr_m5.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("DONE")

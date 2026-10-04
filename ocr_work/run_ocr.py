"""OCR all scanned pages, save line results to ocr_lines.json"""
import json, glob, os
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
out = {}
files = sorted(glob.glob(os.path.expanduser("~/workspace/quizapp/ocr_work/sl*_p*.png")))
print("pages:", len(files), flush=True)
for i, fp in enumerate(files):
    tag = os.path.basename(fp)[:-4]
    try:
        result = ocr(fp)
        lines = []
        for box, text, conf in (result[0] or []):
            xs = [p[0] for p in box]; ys = [p[1] for p in box]
            lines.append({"x": (min(xs)+max(xs))/2, "y": (min(ys)+max(ys))/2,
                          "t": text, "c": round(float(conf), 3)})
        lines.sort(key=lambda l: (l["y"] // 20, l["x"]))
        out[tag] = lines
        print(f"[{i+1}/{len(files)}] {tag}: {len(lines)} lines", flush=True)
    except Exception as e:
        print(f"[{i+1}/{len(files)}] {tag} ERROR {e}", flush=True)
        out[tag] = []
json.dump(out, open(os.path.expanduser("~/workspace/quizapp/ocr_work/ocr_lines.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("DONE")

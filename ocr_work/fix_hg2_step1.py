import json
q = json.load(open('hg2_q1_20.json', encoding='utf-8'))
# Q1: 补A选项（原图：超押加微A.燃烧热大于300J/g属于爆炸物）
q['1']['opts'].insert(0, ['A', '燃烧热大于300J/g属于爆炸物'])
# Q7: 从Q6中分离（题号被OCR吞掉）
q6 = q['6']
# Q6的D选项尾部混入了Q7题干
d_text = q6['opts'][3][1]
split_mark = '精细化工歪业的运行管理'
idx = d_text.find(split_mark)
assert idx > 0, d_text
q6['opts'][3][1] = d_text[:idx]
q7_stem = d_text[idx:] + '\n' + '\n'.join(x for _, x in q6['opts'][4:])
q['7'] = {'stem': q7_stem, 'opts': q6['opts'][4:]}
q6['opts'] = q6['opts'][:4]
# Q13: 修复A选项（B力储存→A.压力储存）
q['13']['opts'].insert(0, ['A', '压力储存剧毒、高毒危害的可燃液体储罐'])
json.dump(q, open('hg2_q1_20.json', 'w', encoding='utf-8'), ensure_ascii=False)
for n in ['1','6','7','13']:
    print(f"Q{n}: opts={[l for l,_ in q[n]['opts']]}")
    if n == '7': print('  stem:', q[n]['stem'][:60])

# 刷题 App 免费版改版 · 施工清单

> 依据：product-rules.md 现行口径（2026-10-25 拍板）——全站免费 + 上传时提示打赏。
> 积分/收款相关一律不做（规则留存备查）。执行顺序即本文顺序，每阶段完成按部署铁律验证后才进下一阶段。

## 阶段 0 · 三 AI 流水线基建（先行）

- [x] VPS（hk-node-02）建 3 个小工账号：worker-jia / worker-yi / worker-bing，各配独立 ed25519 密钥（2026-10-25 已实测三人可登录）
- [x] 建 /opt/quizapp-pipeline/：blackboard.json（空池）+ inbox/ + workers/{jia,yi,bing}/ + review/ + archive/
- [x] 权限隔离：小工对 pipeline 可读写、对线上 /opt/quizapp 无写权限（实测写入被拒）
- [x] 登录信息打包成 .txt 交用户，由用户分发给三个小工（小工登录信息.txt，私钥逐字节核对过）
- [x] three-ai-collab-plan.md 同步更新为 3 个小工

## 阶段 1 · 数据层改造（本地完成、测试通过再上线）

- [x] questions_full.json 顶层加 categories（6 大类）；subjects 每项加 category 字段（现有 10 科目全归 zhongji）
- [x] sets 每项加字段：category / owner / created_at / visibility（private|public）
- [x] 存量 29 套迁移：category=zhongji、owner=站长账号、created_at=上线日、visibility=private（1 年私有期从上线日起算）——迁移脚本 migrate_v2.py 已就绪，上线时以站长真实邮箱+上线日期正式跑
- [x] app.py：/api/meta 返回 categories；套题可见性过滤（登录用户看自己的私有套 + 全部 public 套；未登录只看 public）
- [x] 硬约束：set id 不变，现有作答进度/错题本/收藏零影响；迁移脚本先在本地副本跑通并核对题量 2104 不变（本地测试 18/18 通过）

## 阶段 2 · 前端类别导航

- [x] 首页顶部加考试类别切换（6 类），类别下沿用现有科目 tab；空类别/空科目显示「题库整理中」（本地完成，待随阶段 1 一起部署）
- [ ] 改 app.js/style.css 必须同步 bump index.html 的 ?v=N；部署后 curl 验 200 + 查 CF 缓存、必要时清缓存（已 bump app.js v30 / style.css v26；部署待站长邮箱）

## 阶段 3 · 上传解析 + 打赏

- [x] 需登录。上传页：选类别 + 科目 + PDF 文件
- [x] 后端 uploads 表（uid/category/subject/文件名/状态/时间）；状态：parsing → ready（待确认）/ need_review（转人工）→ done
- [x] 解析：文字层 PDF 走现有解析逻辑；扫描版走 RapidOCR；解析失败 → need_review，用户端显示「等待人工审核」，任务同步登记流水线黑板 inbox（v1 落地：文字层走 upload_lib 泛化解析；无文字层/质量不达标直接转人工，OCR 由流水线小工处理）
- [x] 确认页：展示解析出的题量与题型分布 → 用户确认 → 生成其私有套题（免费，无扣费环节）
- [x] 上传成功/等待页放打赏模块：支付宝 + 微信双码并排 + 自愿文案，不拦截流程（素材已备：assets/reward-alipay.jpg、assets/reward-wechat.png；部署时拷入 www 并统一命名 reward-wechat.jpg）
- [x] 每日上传上限：暂定 5 套/天防滥用（代码常量 DAILY_UPLOAD_LIMIT），待用户正式定

## 阶段 4 · 私有期满公开

- [x] 满 1 年自动转公开脚本 promote_public.py（本地完成并测试：到期转公开、剔重后重编号、全重复套跳过、幂等；定时任务接线随部署一起做）
- [ ] 定时任务：created_at 满 1 年的 private 套 → 转 public；转公开前跑 dedup_check 与公共库查重，重复题不重复显示
- [ ] 公共题库暂时全部免费（后续可调整，改规则先改 product-rules.md）

## 待用户确认（不阻塞阶段 0–2）

1. 站长账号邮箱（存量 2104 题归属到哪个注册账号）
2. 每日上传上限
3. 其余 5 个考试类别的科目划分（我按各考试大纲先拟稿，用户确认）

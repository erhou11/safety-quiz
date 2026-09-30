# safety-quiz 安全生产技术刷题

手机刷题 Web App：85 道安全生产技术试题（70 单选 / 15 多选），答完即时判分并显示答案解析。进度与错题本保存在服务端，关掉重开可续做。

线上地址：https://st.952121.xyz

## 功能

- 顺序练习 / 随机练习 / 错题本 三种模式
- 每题作答后即时显示对错、正确答案与解析
- 进度自动保存：下次打开从上次做到的一题继续
- 错题自动收录，答对后自动移出错题本
- 题目接口不返回答案与解析（作答后才经 API 返回）

## 技术栈

- 后端：Flask + SQLite（WAL 模式）+ gunicorn
- 前端：原生 HTML/CSS/JS，无构建步骤
- 部署：systemd 服务 + nginx 反向代理（`/api/`），静态文件由 nginx 直服

## 目录结构

```
app.py               # Flask 后端（API + 会话进度/错题存储）
questions_full.json  # 85 道题全部数据（题干/选项/答案/解析）
www/                 # 前端静态文件（index.html / style.css / app.js / img/）
quizapp.service      # systemd 服务单元
nginx-st.conf        # nginx 站点配置（参考）
prep_data.py         # 数据准备脚本（图片提取 + JSON 瘦身，构建用）
```

## 部署（Ubuntu + nginx）

```bash
# 1. 建目录并装依赖
sudo mkdir -p /opt/quizapp/data
python3 -m venv /opt/quizapp/venv
/opt/quizapp/venv/bin/pip install flask gunicorn

# 2. 放代码：app.py、questions_full.json、www/ 进 /opt/quizapp
# 3. systemd 服务
sudo cp quizapp.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now quizapp   # 监听 127.0.0.1:8001

# 4. nginx：参考 nginx-st.conf，静态直服 www/，/api/ 反代到 127.0.0.1:8001
```

运行时数据（SQLite 与 Flask session 密钥）保存在 `/opt/quizapp/data/`，不在版本库中。

## 说明

- 进度按浏览器会话（cookie）区分设备，不跨设备同步。
- `questions_full.json` 由试卷 PDF 解析生成，构建脚本见 `prep_data.py`。

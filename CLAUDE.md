# CLAUDE.md — quote0-worker-weekly

打工人周历：每天 7:05 北京时间向 MindReset Dot Quote/0（296×152 黑白墨水屏）推送当日卡片。

## 架构

```
slogans.py (文案表) ─┬─> layout.py (Canvas DSL payload) ──> dot_push.push_canvas ─┐
                     │                                                           ├─> Dot API
image_utils.py ──────┼─> render_card.py (整卡 PNG) ───────> dot_push.push_image ─┘
(GIF→黑白二值PNG)      └─> tools/render_preview.py (预览图)
```

- **双 API**：Image（默认，本地 Pillow 渲染整卡 PNG）与 Canvas（DSL 树文字设备端渲染 chillksans）。切换：`.env` `PUSH_MODE` 或 CLI `--api`。
- **渲染一致**：`render_card.py` 的几何常量与 `layout.py` 的 tailwind 类严格对应（左栏 w-[112px]、右栏 x=122、两行 text-32、px-[4px] py-[8px]；上下边距 8px 由顶行 -mb-[2px] / 底行 -mt-[2px] 把文字少量叠进表情包上下空白，对应 render_card 的 TOP_PULL/BOTTOM_PULL=2），改动必须两处同步。
- **图层顺序**：顶部"2026年进度"文字行要画在表情包**上层**（canvas 顶行 style zIndex:1；Pillow 侧先 paste 表情包、后画顶部行），底部 footer 天然后画即在上层。
- **图片管线**：`image_utils.process_meme` — GIF(RGBA) → 白底合成 → autocontrast → resize 112×112 LANCZOS → 二值化（默认 `bw` 硬阈值，可选 `fs` Floyd-Steinberg / `4level`）→ 严格 0/255 PNG。素材是透明背景黑白贴纸（240×240 单帧）。取图两模式（`.env` `MEME_MODE` 或 CLI `--meme-mode`）：`random`（默认）按周几从 `pic/周一周二|周三|周四|周五周六周日/` 分组文件夹按当天日期+周几为种子随机抽一张，文件夹缺失/为空回退 fixed；`fixed` 用顶层单日文件 `pic/周一.GIF`。
- **文案**：`slogans.slogan_for` — 前半句"周X周X"固定，后半句从当天文案池 `slogans.DAY_PHRASES`（按周几分池，原 A/B 两版合并）随机抽（种子 `日期-slogan-周几` 同日稳定）。
- **推送**：`dot_push._post` 统一错误处理（400 Validation / 401/403 Auth / 404 DeviceNotFound / 5xx）。设备离线时内容排队，API 仍返回成功。

## 环境

- **uv 管理**（Python 3.12 + Pillow），命令统一 `uv run python ...`。
- 系统 python 3.8.10 太老；cron 的 PATH 里 `~/.local/bin` 已有 uv。
- 系统无中文字体，一切本地中文渲染必须用 `fonts/ChillKSans.otf`。
- cron：用户 crontab 里 `5 23 * * *`（UTC）= 北京 7:05，wrapper `export TZ='Asia/Shanghai'` 生效后 `date.today().weekday()` 取北京周几。与参考项目 23:55/1:55/3:55/5:55/8:25/15:55 UTC 不冲突。

## 常见操作

```bash
uv run python -m laborer_reminder.main --dry-run --day 周一   # 看 payload
uv run python -m laborer_reminder.main --api image --dry-run  # 看 Image 模式
uv run python -m laborer_reminder.main --meme-mode fixed --dry-run  # 固定单日表情包
uv run python tools/render_preview.py --scale 4               # 放大预览
./run_laborer_reminder.sh                                     # 手动跑一次（写日志）
```

## 注意事项

- `.env` 有真实密钥（DOT_API_KEY/DOT_DEVICE_ID），勿提交/勿外传；PUSH_MODE / TREATMENT 也在里面。
- `taskAlias` 为"打工人周历"，与参考项目的 "DeepSeek Balance" 区分。
- 改布局时同时改 `render_card.py`（Pillow 坐标）和 `layout.py`（tailwind 类），再 `--dry-run` 验证。
- 真推一次看设备实物为准：预览加粗为 stroke 模拟，设备端 `font-bold` 是真渲染。

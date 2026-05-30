<p align="right">
  <strong>简体中文</strong> |
  <a href="README.en.md">English</a>
</p>

<p align="center">
  <img src="assets/logo.gif" alt="百度贴吧" width="200">
</p>

<h1 align="center">贴吧时光机</h1>
<p align="center"><code>Tieba-Time-Machine</code></p>

<p align="center">
  <strong>帖子会沉，记忆不会</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/无服务器-本地运行-8B5CF6?style=flat-square" alt="Local">
</p>

<p align="center">
  打捞互联网的集体记忆。<br>
  百度贴吧全量归档与本地阅读工具。
</p>

---

## 功能特性

- **全量抓取** — 按吧/按用户批量下载，断点续传，自动限流
- **智能合并** — 分散数据整合为统一 SQLite 数据库（含 FTS5 全文索引）
- **媒体打包** — 图片/视频打包为 tar，支持随机访问，无需解包
- **数据校验** — PAR2 奇偶校验保护归档完整性，支持损坏修复
- **本地阅读** — FastAPI + React 阅读器，浏览器即开即用
- **零服务器** — 全程本地运行，不上传任何数据到外部服务器
- **开源透明** — 所有代码公开可审计，不含遥测或追踪

**处理流程：** 抓取 → 合并为 master.db → 打包媒体 → PAR2 校验 → 本地阅读

> 合并完成后，零散的原始抓取文件默认自动删除（`--keep-raw` 可保留）。  
> archive 是唯一的持久数据源，增量更新和 schema 迁移均直接操作 archive。

---

## 快速开始

```bash
git clone https://github.com/nixliuxin/Tieba-Time-Machine.git
cd Tieba-Time-Machine

# Python 依赖
pip install -e .

# 前端（可选，仅阅读器需要）
cd frontend && pnpm install && cd ..
```

**环境要求：** Python 3.11+ / Node.js 18+（可选）/ par2cmdline-turbo（可选）

### 1. 抓取贴吧

```bash
tieba scrape 魔兽世界 -o ./data/魔兽世界
```

首次运行会提示输入 BDUSS（百度登录凭证）。支持断点续传，随时中断，下次自动继续。

### 2. 一键整合

```bash
tieba pipeline -s ./data -o ./archives
```

自动执行：合并数据库 → 打包媒体 → 生成 PAR2。

### 3. 启动阅读器

```bash
tieba serve ./archives
# 打开 http://localhost:8900
```

---

## 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `tieba scrape` | 抓取整个贴吧 | `tieba scrape 魔兽世界 -o ./data/魔兽世界` |
| `tieba scrape-user` | 抓取某用户全部帖子 | `tieba scrape-user 12345 -o ./data/user` |
| `tieba merge` | 合并为 master.db | `tieba merge -s ./data -o ./archives` |
| `tieba pack` | 打包媒体为 tar | `tieba pack -s ./data -o ./archives` |
| `tieba par2` | 生成 PAR2 校验文件 | `tieba par2 -d ./archives/forum_name` |
| `tieba pipeline` | 一键全流程 | `tieba pipeline -s ./data -o ./archives` |
| `tieba serve` | 启动本地阅读器 | `tieba serve ./archives --port 8900` |

所有命令支持 `--help` 查看详细参数。

---

## 数据结构

每个贴吧归档后产出独立目录：

```
archives/<forum_name>/
├── master.db          SQLite 数据库（帖子/用户/FTS5 全文索引）
├── media.tar          媒体打包（不压缩，支持随机访问）
├── media_index.json   tar 内文件偏移索引
└── media.tar.par2     PAR2 奇偶校验文件
```

- 每个贴吧完全独立，可单独拷贝、分发
- master.db 包含完整的帖子文本和用户信息
- media.tar 通过 index 支持按需读取，无需解包

---

## 项目结构

```
Tieba-Time-Machine/
├── tieba_time_machine/cli.py   统一 CLI 入口
├── scraper/                    抓取引擎
│   ├── backup_forum.py         批量吧备份
│   ├── backup_user.py          批量用户备份
│   └── src/                    核心模块
├── tools/                      离线 ETL
│   ├── merge_archive.py        合并 -> master.db
│   ├── pack_media.py           打包 -> media.tar
│   └── par2_protect.py         校验 -> *.par2
├── server/                     FastAPI 阅读器后端
├── frontend/                   React 阅读器前端
└── docs/                       技术文档
```

---

## 致谢

本项目整合并改进了以下开源项目：

| 项目 | 作者 | 贡献 |
|------|------|------|
| [Sorceresssis/TiebaScraper](https://github.com/Sorceresssis/TiebaScraper) | Sorceresssis | 原始贴吧归档引擎，单帖抓取与 content.db 存储架构 |
| [Sorceresssis/TiebaReader](https://github.com/Sorceresssis/TiebaReader) | Sorceresssis | 离线阅读器 schema 设计与前端概念 |
| [TiebaMeow/TiebaScraper](https://github.com/TiebaMeow/TiebaScraper) | TiebaMeow | 高性能服务端抓取架构参考 |
| [aiotieba](https://github.com/Starry-OvO/aiotieba) | Starry-OvO | 贴吧异步 API 核心库 |
| [atom63/cipher-boilerplate](https://github.com/atom63/cipher-boilerplate) | atom63 | 前端 UI 框架与组件体系 |

---

## 声明

### 安全

- 本工具在本地运行，**不会将任何数据上传到外部服务器**
- BDUSS 凭证仅保存在本地 `tieba_auth.json` 中，不会被收集或传输
- 建议用户定期更换 BDUSS，使用完毕后删除本地凭证文件
- 本工具不包含任何遥测、分析或数据回传功能

### 隐私

- 归档的帖子内容可能包含用户个人信息（用户名、头像、发言内容等）
- 使用者有责任妥善保管归档数据，不得用于骚扰、人肉搜索或侵犯他人隐私
- 建议仅归档公开可见的内容，不要试图绕过平台的访问控制
- 如有当事人要求删除其个人信息，使用者应当配合处理

### 版权

- "百度贴吧" 名称和标志为百度公司的注册商标
- 本项目与百度公司无任何关联、背书或赞助关系
- 贴吧用户发布的内容，其版权归原作者所有
- 本工具仅提供技术手段，不对归档内容的版权状态做任何声明
- Logo 来源：[百度贴吧标志](https://zh.wikipedia.org/wiki/File:%E7%99%BE%E5%BA%A6%E8%B4%B4%E5%90%A7%E6%A0%87%E5%BF%97.gif)（维基百科，合理使用）

### 合规使用

- 本项目仅供**学习研究和个人非商业用途**
- 使用者应遵守所在地区法律法规及百度贴吧使用协议
- 禁止将本工具用于：商业数据采集、大规模数据贩卖、侵权传播、或其他违法活动
- 因使用本工具产生的一切法律责任由使用者自行承担
- 本工具按 "AS IS" 提供，作者不对因使用本工具造成的任何损失承担责任

### 速率限制

- 本工具内置自动限流机制，遵守百度贴吧的访问频率限制
- 请勿修改并发参数以绕过限流，这可能导致账号封禁或 IP 封锁
- 建议在非高峰时段进行大规模归档操作

---

## License

MIT (c) 2026 Nix Liu Xin

---

<p align="center">
  <sub>Made for preserving internet history.</sub>
</p>

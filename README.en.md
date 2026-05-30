<p align="right">
  <a href="README.md">简体中文</a> ·
  <strong>English</strong>
</p>

<p align="center">
  <img src="assets/logo.gif" alt="Baidu Tieba" width="200">
</p>

<h1 align="center">Tieba Time Machine</h1>
<p align="center"><code>Tieba-Time-Machine</code></p>

<p align="center">
  <strong>Posts sink. Memories don't.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/serverless-runs%20locally-8B5CF6?style=flat-square" alt="Local">
</p>

<p align="center">
  Salvaging the collective memory of the internet.<br>
  Archive entire Baidu Tieba forums and read them offline.
</p>

---

## Features

- **Full archive** — Bulk download by forum or user, with resume support and auto rate-limiting
- **Smart merge** — Consolidate scattered data into a unified SQLite database (with FTS5 full-text index)
- **Media packing** — Bundle images/videos into tar with random-access index, no extraction needed
- **Integrity check** — PAR2 parity protection for archive durability and corruption recovery
- **Local reader** — FastAPI + React reader, opens instantly in your browser
- **Zero server** — Runs entirely on your machine, never uploads data anywhere
- **Open source** — Fully auditable code, no telemetry or tracking

---

## Quick Start

```bash
git clone https://github.com/NixLiu/Tieba-Time-Machine.git
cd Tieba-Time-Machine

# Python dependencies
pip install -e .

# Frontend (optional, for the reader only)
cd frontend && pnpm install && cd ..
```

**Requirements:** Python 3.11+ / Node.js 18+ (optional) / par2cmdline-turbo (optional)

### 1. Scrape a forum

```bash
tieba scrape 魔兽世界 -o ./data/魔兽世界
```

First run prompts for BDUSS (Baidu login credential). Supports resume — interrupt anytime, continue next run.

### 2. Process archives

```bash
tieba pipeline -s ./data -o ./archives
```

Automatically: merge database → pack media → generate PAR2.

### 3. Start the reader

```bash
tieba serve ./archives
# Open http://localhost:8900
```

---

## Data Structure

Each archived forum produces a self-contained directory:

```
archives/<forum_name>/
├── master.db          SQLite database (posts/users/FTS5 full-text index)
├── media.tar          Media bundle (uncompressed, random-access via index)
├── media_index.json   Offset index for files inside tar
└── media.tar.par2     PAR2 parity files
```

---

## Acknowledgments

| Project | Author | Contribution |
|---------|--------|--------------|
| [Sorceresssis/TiebaScraper](https://github.com/Sorceresssis/TiebaScraper) | Sorceresssis | Original archive engine, per-thread scraping and content.db schema |
| [Sorceresssis/TiebaReader](https://github.com/Sorceresssis/TiebaReader) | Sorceresssis | Offline reader schema design and frontend concept |
| [TiebaMeow/TiebaScraper](https://github.com/TiebaMeow/TiebaScraper) | TiebaMeow | High-performance server-side scraping architecture |
| [aiotieba](https://github.com/Starry-OvO/aiotieba) | Starry-OvO | Async Tieba API core library |
| [atom63/cipher-boilerplate](https://github.com/atom63/cipher-boilerplate) | atom63 | Frontend UI framework and component system |

---

## Disclaimer

- This tool runs locally and **never uploads any data to external servers**
- "Baidu Tieba" is a registered trademark of Baidu, Inc. This project is not affiliated with Baidu
- User-generated content copyright belongs to the original authors
- For **personal, non-commercial use only**. Users assume all legal responsibility
- Provided "AS IS" without warranty of any kind

---

## License

MIT (c) 2026 Nix Liu Xin

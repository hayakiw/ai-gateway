# AI Gateway

LLM（Gemini）へのプロンプト送信時に、Microsoft Presidio で個人情報（PII）を検出・マスキングするゲートウェイサーバー（FastAPI）。

詳細は [README.md](README.md) を参照。

## 開発環境は Docker で起動する

ローカルに Python をインストールせず、必ず Docker Compose で起動する。

### 前提

- Docker Desktop（Windows / Mac）または Docker Engine + Compose v2
- [.env](.env) に `GEMINI_API_KEY` を設定済みであること（未作成なら `cp .env.example .env`）

### 起動

```bash
cd docker
docker compose up -d --build
```

| 用途 | URL |
|------|-----|
| AI Gateway | http://localhost:8080 |
| Swagger UI | http://localhost:8080/docs |
| テスト画面 | http://localhost:8080/tests/ |
| Redis | localhost:6379 |

`../app` と `../tests` はバインドマウントされており、ホスト側の編集が `uvicorn --reload` で自動反映される。

### よく使うコマンド

```bash
# ログ追従
docker compose logs -f ai-gateway

# 停止
docker compose down

# Redis データも削除
docker compose down -v

# コンテナ内に入る
docker compose exec ai-gateway bash

# テスト実行
docker compose exec ai-gateway pytest tests/ -v
```

詳細は [docker/README.md](docker/README.md) を参照。

## 主要パス

- [app/main.py](app/main.py) — FastAPI エントリーポイント。`/tests` に静的マウント。
- [app/services/pii_detector.py](app/services/pii_detector.py) — PII 検出・マスキング（Presidio + spaCy）。検出対象は `TARGET_ENTITIES` を編集。
- [app/services/llm_client.py](app/services/llm_client.py) — Gemini API クライアント。
- [app/stores/mapping_store.py](app/stores/mapping_store.py) — マッピングテーブル（Redis）。
- [app/routers/](app/routers/) — エンドポイント定義（`health`, `gateway`）。
- [tests/](tests/) — pytest テスト + ブラウザ用テスト画面（静的ファイル）。

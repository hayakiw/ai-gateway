# AI Gateway - Docker 開発環境

開発環境用の Docker 構成。FastAPI アプリと Redis をまとめて起動する。

## 構成

- `Dockerfile` — AI Gateway (FastAPI) のイメージ定義。spaCy モデルも同梱。
- `docker-compose.yml` — AI Gateway + Redis の 2 コンテナ構成。
- `.dockerignore` — ビルドコンテキストの除外設定。

## 前提

- Docker Desktop (Windows / Mac) または Docker Engine + Compose v2
- `ai-gateway/.env` を作成し `GEMINI_API_KEY` を設定しておくこと

```bash
cd ai-gateway
cp .env.example .env
# .env を編集して GEMINI_API_KEY を設定
```

## 起動

```bash
cd ai-gateway/docker
docker compose up --build
```

- AI Gateway: http://localhost:8080
- Swagger UI: http://localhost:8080/docs
- Redis: localhost:6379

## 開発フロー

`../app` をコンテナにバインドマウントしているため、ホスト側でコードを編集すると
`uvicorn --reload` により自動で再読み込みされる。

## よく使うコマンド

```bash
# バックグラウンド起動
docker compose up -d

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

## 注意

- `docker-compose.yml` は `../.env` を読み込む。`.env` 内の `REDIS_HOST` は
  compose の環境変数設定 (`redis`) で上書きされる。
- 初回ビルドは spaCy モデル (ja/en) のダウンロードで時間がかかる。

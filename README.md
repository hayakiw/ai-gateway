# AI Gateway - PII Detection & Masking Proxy

LLM（Gemini）へのプロンプト送信時に、個人情報（PII）を自動検出・マスキングするゲートウェイサーバー。

Microsoft Presidio を使用して個人情報を検出し、マスクされたプロンプトを LLM に送信することで、個人情報の漏洩を防止する。

## 処理フロー

```
1. User: プロンプトを送信
   「田中さんのメールは test@example.com です」

2. AI Gateway (PII Detection & Masking):
   → 「[PERSON_1]さんのメールは [EMAIL_1] です」
   → マッピングテーブルを Redis に保存
     { "[PERSON_1]": "田中", "[EMAIL_1]": "test@example.com" }

3. LLM (Gemini): マスクされたプロンプトを処理して回答

4. AI Gateway (Unmasking):
   → LLM の回答内のプレースホルダーを元の情報に復元

5. User: 最終的な回答を受け取る
```

## ディレクトリ構成

```
ai-gateway/
├── .env.example             # 環境変数サンプル
├── requirements.txt         # 依存パッケージ
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py            # 設定（環境変数から読み込み）
│   ├── main.py              # FastAPI アプリ（エントリーポイント）
│   ├── pii_detector.py      # PII 検出・マスキング（Presidio + spaCy）
│   ├── mapping_store.py     # マッピングテーブル保存（Redis）
│   ├── llm_client.py        # Gemini API クライアント
│   └── schemas.py           # リクエスト / レスポンス定義
└── tests/
    ├── __init__.py
    ├── test_pii_detector.py  # PII 検出・マスキングのテスト
    └── test_api.py           # API エンドポイントのテスト
```

## 使用技術

| カテゴリ | 技術 |
|---------|------|
| Web フレームワーク | FastAPI |
| PII 検出 | Microsoft Presidio |
| NLP エンジン | spaCy（ja_core_news_lg / en_core_web_lg） |
| LLM | Google Gemini（gemini-2.5-flash） |
| マッピング保存 | Redis |
| API クライアント | google-genai |

## 検出対象の個人情報

| エンティティ | プレースホルダー例 | 説明 |
|-------------|------------------|------|
| PERSON | `[PERSON_1]` | 人名（敬称「さん/様/氏/君/くん/ちゃん/先生/殿」を文脈として活用） |
| EMAIL_ADDRESS | `[EMAIL_1]` | メールアドレス |
| PHONE_NUMBER | `[PHONE_1]` | 電話番号 |
| CREDIT_CARD | `[CREDIT_CARD_1]` | クレジットカード番号（13〜19桁） |
| IP_ADDRESS | `[IP_1]` | IP アドレス |
| LOCATION | `[LOCATION_1]` | 地名・住所（都道府県〜番地まで） |
| URL | `[URL_1]` | URL |
| MY_NUMBER | `[MY_NUMBER_1]` | マイナンバー（個人番号） |
| DRIVER_LICENSE | `[DRIVER_LICENSE_1]` | 運転免許証番号 |
| PASSPORT_NUMBER | `[PASSPORT_1]` | パスポート番号 |
| BANK_ACCOUNT | `[BANK_ACCOUNT_1]` | 銀行口座番号 |

> **注意**: 上記は現時点の検出対象です。業務・利用シーンによって機微情報の範囲は異なるため、運用状況やリスク評価に応じて対象エンティティや検出パターンを随時追加・調整してください。追加する場合は [app/services/pii_detector.py](app/services/pii_detector.py) の `TARGET_ENTITIES` および対応する `PatternRecognizer` / `CONTEXTUAL_REGEXES` を更新します。

## セットアップ

### 前提条件

- Python 3.11+
- Redis サーバー
- Google Gemini API キー

### 1. 依存パッケージのインストール

```bash
cd ai-gateway
pip install -r requirements.txt
```

### 2. spaCy モデルのダウンロード

```bash
python -m spacy download ja_core_news_lg
python -m spacy download en_core_web_lg
```

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集して API キーを設定する：

```dotenv
# Gemini API settings
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_TIMEOUT=60

# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_MAPPING_TTL=3600

# Server settings
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8080
```

### 4. Redis の起動

```bash
redis-server
```

Docker を使用する場合：

```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

### 5. サーバーの起動

```bash
cd ai-gateway
python -m app.main
```

サーバーが `http://localhost:8080` で起動する。

## API リファレンス

### ヘルスチェック

```
GET /health
```

**レスポンス例：**

```json
{
  "status": "ok",
  "redis": "connected"
}
```

### プロンプト送信（PII マスキング付き）

```
POST /gateway/generate
```

**リクエストボディ：**

| フィールド | 型 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `prompt` | string | (必須) | ユーザーのプロンプト |
| `language` | string | `"ja"` | 言語コード（`"ja"` or `"en"`） |
| `unmask_response` | bool | `true` | LLM の回答をアンマスクするか |

**リクエスト例：**

```bash
curl -X POST http://localhost:8080/gateway/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "田中さんのメールは test@example.com です",
    "language": "ja",
    "unmask_response": true
  }'
```

**レスポンス例：**

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_prompt": "田中さんのメールは test@example.com です",
  "masked_prompt": "[PERSON_1]さんのメールは [EMAIL_1] です",
  "llm_response_raw": "[PERSON_1]さんのメールアドレスは [EMAIL_1] ですね。",
  "llm_response": "田中さんのメールアドレスは test@example.com ですね。",
  "pii_detected": {
    "[PERSON_1]": "田中",
    "[EMAIL_1]": "test@example.com"
  }
}
```

### Swagger UI

サーバー起動後、以下の URL で API ドキュメントを確認できる：

```
http://localhost:8080/docs
```

## テスト

```bash
cd ai-gateway
pip install pytest
pytest tests/ -v
```

## 設定一覧

すべての設定は環境変数または `.env` ファイルで指定する。

| 環境変数 | デフォルト値 | 説明 |
|---------|------------|------|
| `GEMINI_API_KEY` | (空文字) | Gemini API キー |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 使用する Gemini モデル |
| `GEMINI_API_TIMEOUT` | `60` | API タイムアウト（秒） |
| `REDIS_HOST` | `localhost` | Redis ホスト |
| `REDIS_PORT` | `6379` | Redis ポート |
| `REDIS_DB` | `0` | Redis DB 番号 |
| `REDIS_MAPPING_TTL` | `3600` | マッピングの有効期限（秒） |
| `GATEWAY_HOST` | `0.0.0.0` | サーバーのホスト |
| `GATEWAY_PORT` | `8080` | サーバーのポート |

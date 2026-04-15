# システム概要

## 目的

`ai-gateway` は、ユーザーの入力に含まれる個人情報を LLM に送る前に検知・置換し、レスポンス受信後に必要に応じて元の値へ戻す FastAPI ベースのゲートウェイです。

## 主な処理フロー

### 通常応答 `POST /gateway/generate`

1. クライアントがプロンプトを送信する
2. `PiiDetector.mask()` が PII を検知し、`[PERSON_1]` や `[EMAIL_1]` のようなプレースホルダーへ置換する
3. `MappingStore.save()` がプレースホルダーと元値の対応表を Redis に保存し、`request_id` を発行する
4. `LlmClient.generate()` がマスク済みプロンプトを Gemini に送る
5. `unmask_response=true` の場合は `PiiDetector.unmask()` でレスポンス中のプレースホルダーを元値へ戻す
6. マスク済みの入出力をログへ記録し、Redis 上の対応表を削除してレスポンスを返す

### ストリーミング応答 `POST /gateway/stream`

1. 初期処理は通常応答と同じく PII 検知、マスク、Redis 保存まで行う
2. 先頭で `meta` イベントを返し、`request_id`、`masked_prompt`、`pii_detected` を通知する
3. `LlmClient.stream_generate()` が Gemini のストリーミング結果を受け取る
4. `StreamUnmasker` がチャンク単位でプレースホルダーを元値へ戻す
5. すべてのチャンク送信後に `done` を返し、最後に Redis の対応表を削除する

## コンポーネント構成

| モジュール | 役割 |
| --- | --- |
| `app/main.py` | FastAPI アプリ生成、起動時の依存初期化、ルーター登録 |
| `app/config.py` | `.env` と環境変数の読み込み |
| `app/routers/gateway.py` | 通常応答とストリーミング応答の API |
| `app/routers/health.py` | Redis 接続確認用ヘルスチェック |
| `app/services/pii_detector.py` | Presidio / spaCy を使った PII 検知、マスク、アンマスク |
| `app/services/llm_client.py` | Google Gemini への同期生成・ストリーミング生成 |
| `app/stores/mapping_store.py` | Redis へのマッピング保存、取得、削除 |
| `app/masking_logger.py` | マスク済みのリクエスト・レスポンスログ出力 |
| `app/schemas.py` | API の入出力スキーマ |

## アプリ起動時の初期化

`app/main.py` の `lifespan()` で以下を初期化します。

- `PiiDetector`
- `MappingStore`
- `LlmClient`

`PiiDetector` の初期化時に spaCy モデル `ja_core_news_lg` と `en_core_web_lg` を読み込むため、アプリ起動直後はこのロード時間がかかります。

## PII 検知とマスキングの仕様

### 対象エンティティ

`PiiDetector.TARGET_ENTITIES` では次の情報を対象にしています。

- `PERSON`
- `EMAIL_ADDRESS`
- `PHONE_NUMBER`
- `CREDIT_CARD`
- `IP_ADDRESS`
- `LOCATION`
- `URL`

### プレースホルダー命名規則

`ENTITY_PREFIX_MAP` に基づき、次の形式でプレースホルダーが作られます。

| エンティティ | 置換例 |
| --- | --- |
| `PERSON` | `[PERSON_1]` |
| `EMAIL_ADDRESS` | `[EMAIL_1]` |
| `PHONE_NUMBER` | `[PHONE_1]` |
| `CREDIT_CARD` | `[CREDIT_CARD_1]` |
| `IP_ADDRESS` | `[IP_1]` |
| `LOCATION` | `[LOCATION_1]` |
| `URL` | `[URL_1]` |

### マスキング時のルール

- Presidio の検知結果はスコア降順で並べ替える
- 重なり合う候補は高スコア側を優先し、低スコア側を捨てる
- 最終的な採用順はテキスト内の出現位置順に並べ直す
- 同じ元文字列が複数回出現した場合は同じプレースホルダーを再利用する

このため、同一メールアドレスが 2 回出てきても別番号は振られません。

## アンマスクの仕様

### 通常応答

`PiiDetector.unmask()` はプレースホルダー一覧を正規表現でまとめて置換します。長いキーを先に処理するため、`[PERSON_1]` と似たトークンが混ざっても部分一致で壊れにくい設計です。

### ストリーミング応答

`StreamUnmasker` は途中までしか届いていないプレースホルダーを内部バッファへ残します。たとえば `"[PERS"` と `"ON_1]"` のように分割されても、完全なプレースホルダーになった時点で元値へ戻してから出力します。

## ログ方針

`app/masking_logger.py` は `logs/masking.log` に JSON 形式のレコードを出力します。記録されるのはマスク済みプロンプトとマスク済みレスポンスで、元の個人情報はログに残さない設計です。

## 外部依存

| 依存先 | 用途 |
| --- | --- |
| FastAPI / Uvicorn | Web API 提供 |
| Presidio Analyzer | PII 検知 |
| spaCy | 日本語・英語 NLP モデル |
| Redis | プレースホルダー対応表の一時保存 |
| Google Gemini (`google-genai`) | LLM 推論 |

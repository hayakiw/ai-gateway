# 運用・保守メモ

## 設定値

`app/config.py` は `.env` を読み込み、以下の設定を公開します。

| 環境変数 | デフォルト値 | 用途 |
| --- | --- | --- |
| `GEMINI_API_KEY` | `""` | Gemini API キー |
| `GEMINI_MODEL` | `gemini-2.0-flash` | 利用モデル名 |
| `GEMINI_API_TIMEOUT` | `60` | 将来的な API タイムアウト設定用 |
| `REDIS_HOST` | `localhost` | Redis ホスト |
| `REDIS_PORT` | `6379` | Redis ポート |
| `REDIS_DB` | `0` | Redis DB 番号 |
| `REDIS_MAPPING_TTL` | `3600` | マッピング保存 TTL |
| `GATEWAY_HOST` | `0.0.0.0` | API バインド先 |
| `GATEWAY_PORT` | `8080` | API ポート |

## 起動時に必要な依存

- Python 3.11 以上
- Redis
- spaCy モデル `ja_core_news_lg`, `en_core_web_lg`
- Gemini API キー

## ログ

### 出力先

- `logs/masking.log`

### ローテーション

- 日次ローテーション
- 最大 30 世代保持

### ログ内容

- `type=request` では `masked_prompt` と PII 件数
- `type=response` では `masked_response`
- 元の個人情報は含めない

## テスト

### 主要テストファイル

| ファイル | 内容 |
| --- | --- |
| `tests/test_api.py` | ヘルスチェックと `/gateway/generate` の主要分岐 |
| `tests/test_pii_detector.py` | PII 検知、マスク、アンマスク、ストリーミング用アンマスク |

### テストの特徴

- API テストでは `MappingStore` と `LlmClient` をモック化している
- `PiiDetector` は実体を生成するため、spaCy モデルが必要

## 保守時に把握しておきたい点

### 1. `request_id` は短命

`MappingStore.save()` で Redis に保存された対応表は、通常応答ではレスポンス返却前、ストリーミング応答では終了時に削除されます。TTL は設定されていますが、現行実装では障害時の取り残し対策に近い扱いです。

### 2. `/health` は Redis のみ確認

Gemini API や spaCy モデルの可用性までは見ていません。必要なら別途 readiness check を追加する余地があります。

### 3. LLM への指示は system instruction に集約

`app/services/llm_client.py` の `SYSTEM_INSTRUCTION` に、プレースホルダーをそのまま維持するよう強く指示しています。応答品質の調整はこの文字列の見直しが中心になります。

### 4. 日本語・英語以外は未想定

`PiiDetector` はデフォルトで `ja` と `en` をサポートしています。他言語を追加する場合は spaCy モデルと Presidio の対応状況を合わせて確認する必要があります。

### 5. PII 検知は起動コストが高い

spaCy の大きいモデルをロードするため、コンテナやサーバーのスケール戦略では起動時間を見込む必要があります。

## 拡張ポイント

- 新しい PII 種別を対象にしたい場合
  `PiiDetector.TARGET_ENTITIES` と `ENTITY_PREFIX_MAP` を更新する
- 永続化や監査を強めたい場合
  `MappingStore` の保持期間や削除タイミングを見直す
- 別 LLM に切り替えたい場合
  `LlmClient` を差し替え、`gateway.py` の呼び出し契約を維持する

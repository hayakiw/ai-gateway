# API 仕様

## 共通

- ベース URL: `http://localhost:8080`
- デフォルト言語: `ja`
- コンテンツタイプ: `application/json`

## `GET /health`

Redis 接続状態を含む疎通確認 API です。

### レスポンス例

```json
{
  "status": "ok",
  "redis": "connected"
}
```

### 補足

- Redis への `PING` が成功すると `redis` は `connected`
- 失敗すると `disconnected`
- HTTP ステータス自体はどちらの場合も `200`

## `POST /gateway/generate`

PII をマスクしたうえで Gemini に問い合わせ、必要に応じてレスポンスをアンマスクして返します。

### リクエスト

```json
{
  "prompt": "田中さんのメールは tanaka@example.com です",
  "language": "ja",
  "unmask_response": true
}
```

### リクエスト項目

| フィールド | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `prompt` | `string` | 必須 | ユーザー入力 |
| `language` | `string` | 任意 | Presidio に渡す言語コード。既定値は `ja` |
| `unmask_response` | `boolean` | 任意 | `true` の場合は LLM 応答を元の値へ戻す |

### レスポンス例

```json
{
  "request_id": "d0be0d4d-8a6f-42a5-b08d-2c3fb0dbd73a",
  "original_prompt": "田中さんのメールは tanaka@example.com です",
  "masked_prompt": "[PERSON_1]のメールは [EMAIL_1] です",
  "llm_response_raw": "[PERSON_1]のメールは [EMAIL_1] です。",
  "llm_response": "田中さんのメールは tanaka@example.com です。",
  "pii_detected": {
    "[PERSON_1]": "田中",
    "[EMAIL_1]": "tanaka@example.com"
  }
}
```

### エラー

| 条件 | ステータス | 内容 |
| --- | --- | --- |
| LLM 呼び出し失敗 | `502` | `{"detail":"LLM API call failed"}` |

### 実装上のポイント

- PII 検知は CPU バウンドになりやすいため `run_in_executor()` で別スレッド実行される
- Redis へ保存したマッピングはレスポンス返却前に削除される
- `pii_detected` にはプレースホルダーと元値の対応がそのまま入る

## `POST /gateway/stream`

Server-Sent Events で LLM の出力を段階的に返す API です。

### リクエスト

通常応答と同じ JSON を受け取ります。

```json
{
  "prompt": "田中さんのメールは tanaka@example.com です",
  "language": "ja",
  "unmask_response": true
}
```

### レスポンス形式

`Content-Type: text/event-stream`

返されるイベント種別は以下です。

| event | 説明 |
| --- | --- |
| `meta` | ストリーム開始時のメタ情報 |
| `chunk` | 生成テキストのチャンク |
| `done` | 正常終了通知 |
| `error` | 生成失敗通知 |

### `meta` イベント例

```text
event: meta
data: {"request_id":"...","masked_prompt":"[PERSON_1]のメールは [EMAIL_1] です","pii_detected":{"[PERSON_1]":"田中","[EMAIL_1]":"tanaka@example.com"}}
```

### `chunk` イベント例

```text
event: chunk
data: {"text":"田中さんのメールは "}
```

### `done` イベント例

```text
event: done
data: {}
```

### 実装上のポイント

- `unmask_response=true` の場合、分割されたプレースホルダーも `StreamUnmasker` が吸収する
- エラー発生時は `error` イベントを返し、その時点でストリームを終了する
- `raw_chunks` がある場合のみレスポンスログが出力される

## Swagger UI

FastAPI の自動生成ドキュメントは `http://localhost:8080/docs` で確認できます。

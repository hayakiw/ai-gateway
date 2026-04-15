# ai-gateway ドキュメント

このディレクトリは `ai-gateway` の実装を理解しやすくするための開発資料です。セットアップ手順の詳細は [../README.md](/c:/Users/hayak/work/dojo/ai-cube-llm/ai-gateway/README.md) に譲り、この資料では「プログラムがどう動くか」を中心に整理しています。

## 目次

- [システム概要](./system-overview.md)
- [API 仕様](./api-reference.md)
- [運用・保守メモ](./operations.md)

## 対象読者

- `ai-gateway` の全体像を短時間で把握したい開発者
- PII マスキングの流れを実装レベルで確認したい保守担当者
- API の入出力やストリーミング挙動を確認したい利用者

## この資料で扱う範囲

- FastAPI アプリケーションの起動処理
- `gateway` / `health` エンドポイントの役割
- Presidio + spaCy による PII 検知とプレースホルダー化
- Redis によるマッピング保管
- Gemini 呼び出しとレスポンスのアンマスク
- ログ、テスト、運用時の注意点

# Jevnoid — コーディング規約 (Coding Conventions)

## 1. 基本方針

* **ドキュメント・ファースト**: 実装を行う前に必ず `docs/` を確認・更新すること。
* **1タスク=1ファイルルール**: 変更は可能な限り単一ファイルに限定し、コミット・記録を疎結合に保つ。
* **検索ファースト (Search-First)**: 新規関数やユーティリティを作成する前に、必ずリポジトリ内を `rg` で検索し、車輪の再発明を防ぐ。
* **不変性 (Immutability)**: 状態やオブジェクトの直接的な破壊的変更を避け、Pydanticモデルの `.copy(update=...)` や dataclass の `replace`、スプレッド構文等を用いて新しいオブジェクトを返す。
* **エラーハンドリング**: すべての例外・エラーはログ記録し、サイレントに握りつぶさない。外部API（JevやWebクローラー）の失敗時には適切なフォールバックを行う。

---

## 2. Python 規約 (バックエンド & コアエンジン)

* **バージョン**: Python 3.11+
* **型アノテーション**: すべての関数・メソッドに引数と戻り値の型アノテーションを必須とする（`from __future__ import annotations` を先頭に記述）。
* **モデル定義**: 内部ドメインエンティティおよびAPI DTOには `pydantic` または標準の `@dataclass(frozen=True)` を使用する。
* **フォーマッター・リンター**: `black` (line length 100), `ruff` / `flake8`。
* **Clean Architecture の依存ルール**:
  * `domain/` は一切の外部ライブラリ（boto3, fastapi, typesafe_sdk等）に依存してはならない。
  * `usecases/` は `domain/` のみに依存する。
  * `adapters/` は `domain/`, `usecases/` のポートインターフェースを実装する。
  * `infrastructure/` は外側のフレームワークとして各アダプターをDIする。

---

## 3. TypeScript / フロントエンド規約 (観測デッキ UI)

* **CSS方針**: Vanilla CSS または CSS Modules を用いて、独自の美しいデザインシステムトークン（`var(--color-...)`）を徹底活用する。
* **非同期通信**: WebSocketの自動再接続ハンドリング、Fetch API の厳格なレスポンス検証。
* **アクセシビリティ (A11y)**:
  * 全ての操作可能要素に `aria-label` や適切なHTML5セマンティック要素（`<button>`, `<nav>`, `<article>`, `<main>`）を付与する。
  * コントラスト比は WCAG 2.1 AA 基準（4.5:1以上）を遵守する。

---

## 4. AWS CDK v2 規約 (`infrastructure/`)

* **言語**: TypeScript または Python（TypeScript標準推奨）
* **スタック分割**: 単一巨大スタックを避け、`StorageStack`, `ComputeStack`, `ApiStack`, `FrontendStack` に責務分割する。
* **リソース命名 & タギング**:
  * 全てのリソースに `Project: Jevnoid`, `Environment: Production`, `ManagedBy: CDK` タグを付与する。
  * IAM権限は最小権限の原則（Least Privilege）を適用する。

# Jevnoid（ジェブノイド）

**ネットワーク上で自律的に成長・進化するデジタル人工生命体（Digital Organism）システム。**

TypeSafe AI の超高速意思決定モデル **Jev（System One）** を「自律神経系」として組み込み、1990年に Thomas S. Ray が提唱した人工生命 **Tierra** の思想を、機械語の代わりに「自然言語の意味と文脈（Webコンテンツ）」を栄養として蘇らせたプロジェクトです。

観測デッキ: **https://jevnoid.nayzach.com/**

> 開発の背景・アーキテクチャの詳解は、こちらの記事もあわせてご覧ください:
> **[Jev Tech Blog — Vol. 6: Jevnoid](https://github.com/df-yamashitamasashi/jev_blog/tree/main/articles/06)**

---

## これは何か

古典的な人工生命（Tierra、遺伝的アルゴリズム）は仮想マシン内の機械語や数式環境に閉じており、人間社会の豊かな知識を消化できませんでした。一方、生成AI（LLM）エージェントは深い推論ができる代わりに、1回の判断に数秒〜数十秒を要し、「毎秒の心拍」「常時自律稼働」を実現するには重すぎます。

Jevnoid は、ミリ秒単位で型安全な選択（`Choice` / `Noul` / `Score`）を返す Jev を生命の自律神経として配備することで、この2つの限界の間を埋めます。良質なテキストを「栄養」として捕食・消化し、体内に知識結晶を蓄積しながら、4つの異なる生命種族へと自律的に成長していきます。

### 共生する4つの生命種族

| 種族 | 捕食対象 | 選択のテーマ |
| :--- | :--- | :--- |
| **Theos-noid**（神格型） | 諸宗教の経典・比較宗教学 | 愛・戒律・慈悲・超越・虚無 |
| **Gaia-noid**（大自然型） | 気象・海洋循環・生物多様性データ | 調和・攪乱・再生・適応 |
| **Cosmo-noid**（宇宙生物型） | 天文学・宇宙物理学論文 | エントロピー・重力・創発・時空 |
| **Info-Grazer**（純粋情報型） | ArXiv・技術ブログ・一次情報源 | 真実性・新規性・構造美 |

各個体は Thomas S. Ray の1990年オリジナル Tierra 仮想マシン（32命令、テンプレート方式の相補的アドレッシング）を内部で実行し、自己複製・突然変異・寄生（Parasite）・Reaper淘汰による生態系形成を、原著どおりの実装で再現しています。

---

## アーキテクチャ

```
閲覧者 ──HTTPS──▶ Cloudflare Pages（静的ファイル: 無料・無制限）
                    └─ /api/v1/vitals ─▶ Pages Function ─▶ Workers KV「snapshot」
                                                              ▲ 心拍ごとに書き込み
EventBridge ─(3時間)─▶ Lambda（Tierra VM / Jev 判断 / Web 捕食）─┘
                         └─▶ DynamoDB（生命体の状態）
```

- **公開面と生命エンジンの分離**: 閲覧者が触れるのは Cloudflare Pages の静的ファイルと KV のスナップショットだけです。AWS 側にはインターネットから到達できるエンドポイントがありません。
- **アクセスが増えても課金されない**: 静的ファイルは無料・無制限。最新データを返す Pages Function は無料枠（1日10万回）を超えると遮断され、観測デッキは自動的に静的な予備スナップショットを表示します。
- **Clean Architecture**: `domain`（生命・DNA・Tierra VM の純粋ロジック）→ `usecases` → `adapters`（Jev / Web / DynamoDB / KV）→ `infrastructure` の4層。ローカルでもAWSでも同じコードで動作します。
- **セキュリティ**: 巡回先のページを表示する際は全文字列をエスケープし、厳格な CSP を適用。Web 捕食は解決した IP を固定して接続し、リダイレクトごとに再検証します（SSRF 対策）。秘密情報は SSM SecureString に保管し、コードやテンプレートに含めません。

詳細は [`docs/system_architecture.md`](./docs/system_architecture.md)、運用手順は [`docs/runbook.md`](./docs/runbook.md)、Tierra VM の原著再現については [`docs/tierra_research_spec.md`](./docs/tierra_research_spec.md) を参照してください。

---

## クイックスタート（ローカル実行）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Jev API キーがなくても、ヒューリスティック判断で動作します
export TYPESAFE_API_KEY="your-typesafe-api-key"   # 任意

pytest
python -m src.infrastructure.local_server
```

`http://127.0.0.1:8000/` で観測デッキ、`http://127.0.0.1:8000/api/v1/vitals` で4体全個体のバイタル・3D形態・思考ログを確認できます。

## デプロイ

- **観測デッキ（Cloudflare Pages）**: `web/wrangler.jsonc` の KV Namespace ID を自分のものに変更し、`web/deploy.sh` を実行します。
- **生命エンジン（AWS CDK v2）**: 秘密情報を SSM に登録してから `cdk deploy` します。手順は [`docs/runbook.md`](./docs/runbook.md) を参照してください。

---

## ディレクトリ構成

```
src/
├── domain/           # 生命・DNA・Tierra VM（32命令仮想マシン）の純粋ロジック
├── usecases/         # 心拍サイクル・公開スナップショット生成
├── adapters/         # Jev クライアント、Web 捕食、DynamoDB、Cloudflare KV、秘密情報
└── infrastructure/   # Lambda エントリーポイント、ローカル開発サーバー
web/                  # Cloudflare Pages（静的ファイル・Pages Function・デプロイスクリプト）
infrastructure/       # AWS CDK v2（Storage / Compute の2スタック）
tests/                # pytest
docs/                 # 要件定義・基本設計・アーキテクチャ・運用手順・Tierra研究仕様
```

## リポジトリの運用方針（Fork 専用）

本リポジトリは **Fork のみ** を受け付けています。本体への push、Pull Request、Issue、Discussions は受け付けておらず、変更を反映できるのはメンテナーのみです。改変や拡張は、ご自身の Fork 先でご自由にどうぞ。詳しくは [CONTRIBUTING.md](./CONTRIBUTING.md) をご覧ください。

## ライセンス

[MIT License](./LICENSE)（`web/public/vendor/` の three.js は [MIT License](./web/public/vendor/three.LICENSE)）

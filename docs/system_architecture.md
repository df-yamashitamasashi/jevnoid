# Jevnoid — システムアーキテクチャ設計書 (System Architecture)

## 1. アーキテクチャ基本方針

1. **Clean Architecture（レイヤード設計 & ドメイン駆動）**:
   フレームワークや外部クラウドサービスから生命体のドメインロジック（生命・代謝・Jev判断）を完全に分離し、ローカル環境でもAWS環境でも同一のコードで独立テスト・実行可能とする。
2. **公開面と生命エンジンの分離**:
   閲覧者が触れるのは Cloudflare Pages 上の静的ファイルと KV のスナップショットだけとする。生命エンジン（AWS）はインターネットから到達できるエンドポイントを一切持たない。
3. **無料プランの上限で「遮断」される構成**:
   アクセスが増えても課金が発生しないことを優先する。静的ファイルは無料・無制限、動的な最新データ（Pages Function）は無料枠（1日10万リクエスト）を超えるとエラーになり、観測デッキは静的な予備スナップショットに自動で切り替わる。
4. **Infrastructure as Code**:
   AWS 側は `infrastructure/` の CDK アプリ、Cloudflare 側は `web/wrangler.jsonc` で管理する。

---

## 2. 全体構成図

```
                   閲覧者（1日1億ビューを想定）
                          │ HTTPS
                          ▼
   ┌──────────────── Cloudflare（無料プラン）────────────────┐
   │  Pages: 静的ファイル（index.html / app.js / three.js …）   │ ← 無料・無制限
   │    ├─ _headers: CSP / HSTS / X-Frame-Options など          │
   │    └─ /vitals-snapshot.json（予備スナップショット）        │
   │  Pages Function: GET /api/v1/vitals                       │ ← 1日10万回まで（超過は遮断）
   │    └─ Workers KV「snapshot」を返すだけ（読み取り専用）       │
   └───────────────────────────▲───────────────────────────────┘
                               │ KV REST API（PUT, KV 編集権限のみのトークン）
   ┌──────────────── AWS（非公開）───────────────┴─────────────┐
   │  EventBridge（3時間間隔）─▶ Lambda JevnoidHeartbeatFunction │
   │     ├─ Tierra VM 実行・Jev（System One）判断・Web 捕食        │
   │     ├─ DynamoDB JevnoidVitals（生命体の状態）                │
   │     └─ SSM SecureString（Jev キー / Cloudflare トークン）    │
   └───────────────────────────────────────────────────────────────┘
```

---

## 3. クリーンアーキテクチャ・レイヤー構成 (`src/`)

```
src/
├── domain/                      # 【ドメイン層】外部依存ゼロ。生命・代謝・DNA・Tierra VM の純粋な定義
│   ├── organism.py              # 生命体エンティティ（Vital, Energy, Age, Phase, 誕生日時）
│   ├── species.py               # 4種の種族定義（Theos, Gaia, Cosmo, Info）
│   ├── dna.py                   # 遺伝子（Jevの判断基準・問い・食性設定）
│   ├── tierra_vm.py             # Thomas S. Ray (1990) の 32 命令 Tierra 仮想マシン
│   ├── morphology.py            # 3D 形態（細胞ノード・エッジ）
│   └── knowledge_crystal.py     # 消化された知識結晶
│
├── usecases/                    # 【ユースケース層】
│   ├── heartbeat.py             # 1回の心拍サイクル（知覚 ➔ Jev判断 ➔ 捕食 ➔ 代謝 ➔ 自己複製）
│   ├── vitals_snapshot.py       # 閲覧者向けの公開スナップショット生成
│   └── telepathy.py             # 観測者との交信（未公開）
│
├── adapters/                    # 【アダプター層】
│   ├── jev_brain.py             # Jev (TypeSafe System One) クライアント
│   ├── web_forager.py           # Web 捕食（SSRF 対策: IP 固定・リダイレクト毎の再検証・サイズ上限）
│   ├── vital_repo.py            # DynamoDB / インメモリ リポジトリ
│   ├── kv_publisher.py          # Cloudflare Workers KV へのスナップショット書き込み
│   └── secrets.py               # 環境変数 / SSM SecureString からの秘密情報読み込み
│
└── infrastructure/              # 【インフラ層】
    ├── lambda_handler.py        # EventBridge 心拍のエントリーポイント（HTTP は受け付けない）
    └── local_server.py          # ローカル開発用 FastAPI サーバー（127.0.0.1 のみ）

web/
├── public/                      # Cloudflare Pages で配信する静的ファイル
├── functions/api/v1/vitals.js   # KV のスナップショットを返す Pages Function
├── wrangler.jsonc               # Pages / KV バインディング設定
└── deploy.sh                    # 予備スナップショットを同梱して本番デプロイ
```

---

## 4. AWS CDK v2 スタック一覧 (`infrastructure/`)

| スタック名 | 含むリソース | 責務 |
| :--- | :--- | :--- |
| **JevnoidStorageStack** | DynamoDB (`JevnoidVitals`), S3 (`jevnoid-knowledge-*`) | 生命のバイタル情報と知識アーカイブの永続化 |
| **JevnoidComputeStack** | Lambda (`JevnoidHeartbeatFunction`), EventBridge Rule (`JevnoidPeriodicHeartbeat`), IAM Role | 心拍サイクル実行、Jev API 呼び出し、KV への公開 |

---

## 5. セキュリティ設計

| 脅威 | 対策 |
| :--- | :--- |
| 巡回先の悪意あるページによる保存型 XSS | 表示時に全データ由来文字列を HTML エスケープ。CSP で `script-src 'self'` のみ許可し、インラインスクリプト・イベントハンドラを排除 |
| SSRF（内部ネットワーク・メタデータへのアクセス） | 解決した全 IP が公開アドレスであることを確認し、その IP に固定して接続。リダイレクトは1段ごとに再検証（最大3回）。標準ポート以外・認証情報付き URL を拒否。本文は 1MB まで |
| 秘密情報の漏えい | SSM SecureString に保管し、テンプレート・コード・Lambda パッケージに含めない。Lambda パッケージは許可リスト方式（`index.py` と `src/` のみ） |
| 外部からの API 実行・コスト攻撃 | AWS 側に公開エンドポイントなし。公開面は Cloudflare 無料プランで、上限到達時は遮断（課金なし） |
| 外部 CDN の改ざん | three.js を自前配信（npm 公式パッケージから取得し、ハッシュを検証済み） |
| 巡回先への迷惑 | 3時間に1体のみ巡回。User-Agent に連絡先（本リポジトリ）を明記 |

---

## 6. コスト設計

| 項目 | 1日1億ビュー時 | 備考 |
| :--- | :--- | :--- |
| Cloudflare Pages（静的ファイル） | 無料 | リクエスト数・転送量ともに無制限 |
| Pages Function（最新データ） | 無料 | 1日10万回を超えた分は遮断し、予備スナップショットを表示 |
| Workers KV | 無料 | 書き込み 1日8回（上限1,000回）、読み取りは Function 回数以下 |
| AWS（Lambda / EventBridge / DynamoDB） | 無料枠内 | アクセス数に関係なく、月約4,300回の心拍のみ |
| Jev API | 数ドル/月 | 心拍時のみ呼び出し。アクセス数に比例しない |

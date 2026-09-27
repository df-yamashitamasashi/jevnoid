# Jevnoid — 運用手順書 (Runbook)

## 1. システム概要

* **システム名**: Jevnoid (Jev-Organism System)
* **目的**: 4種のデジタル生命体の自律的育成・リアルタイム観測
* **構成**:
  * **公開側（Cloudflare Pages / 無料プラン）**: 静的な観測デッキ（`web/public`）と、KV から最新スナップショットを返す Pages Function（`web/functions/api/v1/vitals.js`）
  * **生命エンジン側（AWS / 非公開）**: EventBridge（3時間間隔の心拍）→ Lambda `JevnoidHeartbeatFunction` → DynamoDB `JevnoidVitals`。心拍ごとに公開用スナップショットを Cloudflare Workers KV へ書き込む
  * AWS 側にインターネットから到達できるエンドポイントは存在しない

```
閲覧者 ──HTTPS──▶ Cloudflare Pages（静的ファイル: 無料・無制限）
                    └─ /api/v1/vitals ─▶ Pages Function ─▶ Workers KV「snapshot」
                                                              ▲
EventBridge ─(3時間)─▶ Lambda（Tierra VM / Jev 判断 / Web 捕食）─┘
                         └─▶ DynamoDB（生命体の状態）
```

### 1.1 無料枠を超えたときの挙動

* 静的ファイル（HTML/JS/CSS/予備スナップショット）へのリクエストは無料・無制限。
* Pages Function は Workers 無料プランの **1日10万リクエスト** を共有。超過分はエラーとなり（課金は発生しない）、観測デッキは自動的に静的な予備スナップショット `/vitals-snapshot.json` を表示する。

---

## 2. 秘密情報

秘密情報はリポジトリにも CloudFormation テンプレートにも含めない。Lambda は起動時に SSM Parameter Store（SecureString）から読み込む。

| パラメータ名 | 内容 | 必要な権限 |
| :--- | :--- | :--- |
| `/jevnoid/typesafe-api-key` | TypeSafe（Jev）API キー | — |
| `/jevnoid/cloudflare-kv-api-token` | Cloudflare API トークン | Account → Workers KV Storage → Edit のみ |

### 2.1 登録・更新（ローテーション）

値を画面に表示しないよう、クリップボードから直接登録する（macOS）。

```bash
# 新しい値をコピーしてから実行。更新時は --overwrite を付ける
aws ssm put-parameter --region ap-northeast-1 --name /jevnoid/typesafe-api-key --type SecureString --overwrite \
  --value "$(pbpaste | tr -d '[:space:]')" && pbcopy </dev/null
```

更新後、Lambda は次のコールドスタートで新しい値を読み込む。すぐに反映したい場合は関数を再デプロイする。

---

## 3. ローカル開発

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest
python -m src.infrastructure.local_server   # http://127.0.0.1:8000
```

ローカルでは Jev API キーを `TYPESAFE_API_KEY` 環境変数、または `.secrets/typesafe_api_key`（Git 管理外）から読み込む。キーがなくてもヒューリスティック判断で動作する。

---

## 4. デプロイ

### 4.1 観測デッキ（Cloudflare Pages）

```bash
cd web
./deploy.sh   # KV の最新スナップショットを予備として同梱し、本番ブランチへデプロイ
```

事前確認はプレビューブランチへ：`npx wrangler pages deploy --branch preview`

### 4.2 生命エンジン（AWS CDK v2）

```bash
cd infrastructure
npm install
npx cdk deploy --all \
  -c cloudflareAccountId=<Cloudflare アカウント ID> \
  -c cloudflareKvNamespaceId=<KV Namespace ID>
```

Lambda のコードには `index.py` と `src/` だけが含まれる（許可リスト方式）。Python 依存ライブラリは `lambda_layer/python` に Linux 向けにインストールしておく：

```bash
pip install -r lambda-requirements.txt -t lambda_layer/python \
  --platform manylinux2014_x86_64 --python-version 3.12 --only-binary=:all:
```

---

## 5. 障害対応

### 5.1 観測デッキのデータが更新されない
1. Lambda のログを確認：`aws logs tail /aws/lambda/JevnoidHeartbeatFunction --since 30m`
   * `Snapshot publish failed` → Cloudflare トークンの失効・権限不足。2.1 の手順で更新する。
   * `Cloudflare publisher not configured` → CDK コンテキスト（アカウント ID / Namespace ID）または SSM パラメータが未設定。
2. EventBridge ルールが有効か確認：`aws events describe-rule --name JevnoidPeriodicHeartbeat --query State`
   * 無効なら：`aws events enable-rule --name JevnoidPeriodicHeartbeat`

### 5.2 Jev の判断が「Spatial Heuristic」表示のまま
* TypeSafe API キーの失効・残高不足・SSM 読み込み失敗のいずれか。Lambda ログの `[JevBrain]` 行を確認し、必要なら 2.1 の手順でキーを更新する。

### 5.3 生命活動を一時停止したい
```bash
aws events disable-rule --name JevnoidPeriodicHeartbeat
```
観測デッキは最後のスナップショットを表示し続ける。

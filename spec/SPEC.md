# Cloud Custodian Azure Container Apps 実装仕様書

## 1. 概要

Cloud Custodian (c7n) の Azure 実装 (c7n-azure) を Azure Container Apps Jobs で動作させるための実装を提供する。

### 1.1 目的

- Azure Container Apps Jobs を活用した c7n-azure のモダンな実行環境を提供
- EventGrid によるイベントドリブン実行と cron による定期実行をサポート
- 将来的な Azure Functions (Flex Consumption) への拡張を考慮した設計

### 1.2 主要な成果物

1. **c7n-azure-runner** - 共通コアライブラリ（トリガー非依存のポリシー実行ロジック）
2. **c7n-azure-container-apps** - Container Apps 用のDockerfile とエントリポイント
3. **GitHub Actions** - Docker イメージのビルドとpublish用ワークフロー

## 2. アーキテクチャ

### 2.1 システム構成

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Subscription                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────────────────────┐│
│  │   Event Grid     │─────▶│   Storage Queue                  ││
│  │  (Subscription)  │      │   (イベントバッファ)              ││
│  └──────────────────┘      └──────────────┬───────────────────┘│
│                                           │                     │
│                                           ▼                     │
│  ┌────────────────────────────────────────────────────────────┐│
│  │           Container Apps Environment                        ││
│  │  ┌──────────────────────────────────────────────────────┐  ││
│  │  │     Container Apps Job (Event Trigger)                │  ││
│  │  │     - KEDA azure-queue scaler                         │  ││
│  │  │     - c7n-azure ポリシー実行                          │  ││
│  │  └──────────────────────────────────────────────────────┘  ││
│  │  ┌──────────────────────────────────────────────────────┐  ││
│  │  │     Container Apps Job (Schedule Trigger)             │  ││
│  │  │     - Cron expression                                 │  ││
│  │  │     - c7n-azure ポリシー実行                          │  ││
│  │  └──────────────────────────────────────────────────────┘  ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────────────────────┐│
│  │ Blob Storage     │      │   Managed Identity               ││
│  │ (ポリシー格納)    │      │   (RBAC認証)                     ││
│  └──────────────────┘      └──────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 モジュール構成

```
c7n_azure_container_app/
├── src/
│   ├── c7n_azure_runner/           # 共通コアライブラリ
│   │   ├── __init__.py
│   │   ├── policy_loader.py        # ポリシー読み込み
│   │   ├── policy_executor.py      # ポリシー実行
│   │   ├── event_processor.py      # イベント処理
│   │   └── config.py               # 設定管理
│   │
│   └── c7n_azure_container_apps/   # Container Apps 固有
│       ├── __init__.py
│       ├── entrypoint.py           # メインエントリポイント
│       ├── queue_handler.py        # Storage Queue ハンドラー
│       └── cli.py                  # CLI インターフェース
│
├── docker/
│   └── Dockerfile
│
├── .github/
│   └── workflows/
│       └── docker-publish.yml
│
├── pyproject.toml
└── README.md
```

## 3. 要件詳細

### 3.1 機能要件

#### 3.1.1 ポリシー実行

- [ ] Blob Storage からポリシー YAML ファイルを読み込み
- [ ] `--policy-uri` 指定時は Blob Storage 上の YAML を HTTPS でダウンロードし、Managed Identity もしくはサービス プリンシパルに `Storage Blob Data Reader` 以上の RBAC を割り当てる。SAS URI を用いる場合は有効期限とアクセス権を最小化する ([Access Azure Storage from a web app using managed identities](https://learn.microsoft.com/en-us/entra/identity-platform/multi-service-web-app-access-storage#grant-access-to-the-storage-account))
- [ ] c7n-azure の既存ポリシースキーマを完全サポート
- [ ] `container-event` モードと `container-periodic` モードをサポート
- [ ] dryrun モードをサポートし、CLI フラグ `--dryrun` もしくは環境変数 `C7N_DRYRUN=true` が指定された場合は c7n の Policy 実行に `dryrun=True` オプションを渡し、Azure リソースへの変更アクションを抑止する。dryrun 中もロガーへ実行計画を出力し、Azure Container Apps Jobs のログクエリ手順 ([Query job run logs](https://learn.microsoft.com/en-us/azure/container-apps/jobs-get-started-cli#query-job-run-logs)) に従って検証できるようにする。
- [ ] ポリシー実行結果のログ出力
- [ ] 実行結果メトリクスの Azure Monitor への送信（オプション）

#### 3.1.2 イベントトリガー実行

- [ ] Event Grid サブスクリプションを通じた Azure リソースイベントの受信
- [ ] Storage Queue 経由でのイベントバッファリング
- [ ] KEDA azure-queue scaler によるジョブ起動
- [ ] イベントに基づくリソースフィルタリングと対象ポリシーの選定

#### 3.1.3 定期実行

- [ ] Cron 式による定期的なポリシー実行
- [ ] 複数ポリシーの並列実行サポート

### 3.2 非機能要件

#### 3.2.1 セキュリティ

- [ ] Managed Identity による認証（System Assigned / User Assigned）
- [ ] RBAC によるリソースアクセス制御
- [ ] ハードコードされた認証情報の禁止
- [ ] VNET 統合のサポート（オプション）
- [ ] サービスエンドポイント接続のサポート

#### 3.2.2 パフォーマンス

- [ ] ジョブのタイムアウト設定（デフォルト: 30分）
- [ ] 並列実行数の制限設定
- [ ] メモリ/CPU リソースの設定可能化

#### 3.2.3 運用性

- [ ] 構造化ログ出力
- [ ] ヘルスチェック機能
- [ ] エラーハンドリングとリトライロジック

### 3.3 互換性要件

- [ ] c7n-azure / c7n の既存コードを変更しない
- [ ] c7n-azure のアップデートに追従可能な設計
- [ ] Python 3.14 サポート

### 3.4 ローカル実行・デバッグ要件

#### 3.4.1 ローカル実行

- [ ] ローカル開発者は最新の Azure CLI をインストールし、`az login --tenant <TENANT_ID>` と `az account set --subscription <SUBSCRIPTION_ID>` を事前に実行して `DefaultAzureCredential` が `AzureCliCredential` を経由してトークンを取得できるようにする ([Authenticate Python apps to Azure services during local development using developer accounts](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-dev-accounts#3---sign-in-to-azure-using-the-azure-cli,-azure-powershell,-azure-developer-cli,-or-in-a-browser))
- [ ] コマンド `c7n-azure-runner run-policy --policy-file <PATH>` を用いたローカル実行を正式サポートし、`AZURE_SUBSCRIPTION_ID`、`C7N_POLICY_FILE` など必要な環境変数が CLI フラグまたは `.env` から読み込めるようにする
- [ ] CLI で `--subscription-id/-s` を指定した場合はその値を `AZURE_SUBSCRIPTION_ID` に強制的に反映し、Azure CLI の既定サブスクリプションへフォールバックしない。指定値が存在しない／アクセス不可のサブスクリプションであれば即座に失敗させ、Azure CLI 既定の暗黙指定よりも明示指定を優先する。LocalSession キャッシュ (`c7n.utils.local_session`) に保持されている既定サブスクリプションは毎回クリア＆再初期化し、c7n-azure の Session オブジェクトが必ず明示 ID で構築されるようにする ([How to use variables in Azure CLI commands > Set a subscription](https://learn.microsoft.com/en-us/cli/azure/azure-cli-variables?view=azure-cli-latest#set-a-subscription))
- [ ] 自動化・CI では `az ad sp create-for-rbac` で作成したサービス プリンシパルの資格情報を `.env` もしくはセキュアストアに格納し、`AZURE_CLIENT_ID`、`AZURE_TENANT_ID`、`AZURE_CLIENT_SECRET` を `DefaultAzureCredential` へ渡す手順を記載する ([Authenticate Python apps to Azure services during local development using service principals](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-service-principal))
- [ ] RBAC ロールは `Contributor` + `User Access Administrator`（デプロイ操作）と、ポリシー対象リソースに応じた `Reader`/`Contributor`、Blob/Queue アクセス用のデータロールを最小権限で割り当てる ([Create an Azure service principal with Azure CLI](https://learn.microsoft.com/en-us/cli/azure/azure-cli-sp-tutorial-1))

#### 3.4.2 ローカルデバッグ

- [ ] CLI の `--verbose` フラグや Python デバッガ (`python -m pdb -m c7n_azure_container_apps.cli ...`) を用いて単体ポリシー実行をトレースできるようにする
- [ ] `pytest -k <pattern>` や `pytest tests/test_event_processor.py::test_xxx -vv` を使った最小単位テストを推奨し、失敗時の再現手順を CONTRIBUTING に明記する
- [ ] ローカルでの Azure SDK 呼び出しは `DefaultAzureCredential` を使用し、Azure CLI/サービス プリンシパルで設定された資格情報を透過的に利用する実装とする ([Authenticate Python apps to Azure services during local development using developer accounts](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-dev-accounts#4---implement-defaultazurecredential-in-your-application))

#### 3.4.3 README ドキュメント方針

- [ ] README の主眼は「Azure Container Apps Jobs 上で c7n-azure をどのように動かすか」に置き、アーキテクチャ概要と Getting Started（Azure へのデプロイ手順）への導線を明確にする
- [ ] `dryrun` フラグやローカル実行手順などの補助機能は README では高レベルな機能一覧の 1 行説明とし、詳細な使い方は `docs/GetStarted.md` や `CONTRIBUTING.md`、CI 設定は `docs/CI_SETUP.md` など別ドキュメントに委ねる
- [ ] ローカル実行やデバッグの長いハウツーは README から削除し、「ローカル開発・デバッグについては CONTRIBUTING を参照」のように、参照先のみを示す
- [ ] 機能の存在は README 上から把握できるようにするが、「存在のみ紹介」など README 自体のポリシー説明は README には書かず、本 SPEC や `.github/instructions/how-to-write-readme.md` に記載する

## 4. 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `AZURE_SUBSCRIPTION_ID` | Yes | 対象の Azure サブスクリプション ID |
| `AZURE_POLICY_STORAGE_URI` | Yes | ポリシーファイルが格納された Blob Storage URI |
| `AZURE_QUEUE_STORAGE_ACCOUNT` | Yes* | イベントキュー用ストレージアカウント名 |
| `AZURE_QUEUE_NAME` | Yes* | イベントキュー名 |
| `AZURE_OUTPUT_DIR` | No | ポリシー実行結果の出力先 |
| `AZURE_LOG_GROUP` | No | Log Analytics ワークスペース |
| `AZURE_METRICS_TARGET` | No | メトリクス送信先 |
| `C7N_POLICY_FILE` | No | 単一ポリシー実行時のポリシーファイルパス |
| `C7N_EVENT_DATA` | No | イベントデータ（JSON文字列） |

*イベントトリガーモードの場合に必須

## 5. Docker イメージ

### 5.1 ベースイメージ

- `python:3.14-slim` をベースに使用
- マルチステージビルドでイメージサイズを最適化

### 5.2 タグ戦略

- `latest` - 最新の安定版
- `x.y.z` - セマンティックバージョニング
- `sha-xxxxxx` - コミットハッシュ

### 5.3 レジストリ

- Docker Hub: `cloudcustodian/c7n-azure-container-apps`
- GitHub Container Registry: `ghcr.io/fukasawah/c7n-azure-container-apps`

## 6. 制約事項

### 6.1 技術的制約

- Container Apps Jobs の最大実行時間は 1800 秒（30分）
- Event 型ジョブの最大同時実行数は 10
- KEDA スケーラーは 60 秒間隔でポーリング

### 6.2 コスト考慮

- プライベートエンドポイントは使用しない（コスト削減）
- サービスエンドポイントを優先使用
- 実行時間に応じた従量課金

## 7. 将来の拡張

### 7.1 Azure Functions (Flex Consumption) 対応

- `c7n_azure_runner` ライブラリを再利用
- HTTP トリガーまたは Queue トリガーによる実行
- 別リポジトリまたは別パッケージとして提供予定

### 7.2 追加機能候補

- Web UI によるポリシー管理
- Slack/Teams 通知連携
- カスタムアクションの追加サポート

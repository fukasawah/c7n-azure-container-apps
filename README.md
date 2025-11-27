# Cloud Custodian Azure Container Apps Runner

[![Docker Build](https://github.com/your-org/c7n-azure-container-apps/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/your-org/c7n-azure-container-apps/actions/workflows/docker-publish.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Azure Container Apps Jobs で [Cloud Custodian](https://cloudcustodian.io/) の Azure ポリシーを実行するためのランナーです。

## 特徴

- **イベント駆動実行**: Event Grid + Storage Queue を使用したリアルタイムのリソース監視
- **定期実行**: Cron 式によるスケジュール実行
- **モダン認証**: Managed Identity (System/User Assigned) による安全な認証
- **軽量設計**: 非常駐型ジョブとして動作し、コストを最適化
- **c7n 互換**: c7n / c7n-azure のコードを変更せずに使用

## クイックスタート

### 前提条件

- Azure サブスクリプション
- Azure Container Apps 環境
- ポリシーファイルを格納する Blob Storage

### Docker イメージ

```bash
# Docker Hub
docker pull cloudcustodian/c7n-azure-container-apps:latest

# GitHub Container Registry
docker pull ghcr.io/your-org/c7n-azure-container-apps:latest
```

### 基本的な使い方

#### 単一ポリシーの実行

```bash
docker run --rm \
  -e AZURE_SUBSCRIPTION_ID=<subscription-id> \
  -v $(pwd)/policies:/policies:ro \
  cloudcustodian/c7n-azure-container-apps:latest \
  run-policy --policy-file /policies/my-policy.yml
```

#### Blob Storage からポリシーを実行

```bash
docker run --rm \
  -e AZURE_SUBSCRIPTION_ID=<subscription-id> \
  -e AZURE_POLICY_STORAGE_URI=https://mystorageaccount.blob.core.windows.net/policies \
  cloudcustodian/c7n-azure-container-apps:latest \
  run-scheduled
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `AZURE_SUBSCRIPTION_ID` | Yes | 対象の Azure サブスクリプション ID |
| `AZURE_POLICY_STORAGE_URI` | Yes* | ポリシーファイルが格納された Blob Storage URI |
| `AZURE_QUEUE_STORAGE_ACCOUNT` | Yes** | イベントキュー用ストレージアカウント名 |
| `AZURE_QUEUE_NAME` | Yes** | イベントキュー名 |
| `AZURE_OUTPUT_DIR` | No | ポリシー実行結果の出力先（デフォルト: `/tmp/c7n-output`） |
| `AZURE_LOG_GROUP` | No | Log Analytics ワークスペース |
| `AZURE_METRICS_TARGET` | No | メトリクス送信先 |
| `C7N_POLICY_FILE` | No | 単一ポリシー実行時のポリシーファイルパス |
| `C7N_EVENT_DATA` | No | イベントデータ（JSON文字列） |
| `C7N_EXECUTION_MODE` | No | 実行モード（`event`, `scheduled`, `single`） |

\* `C7N_POLICY_FILE` が指定されていない場合に必須
\*\* イベントトリガーモードの場合に必須

## Azure Container Apps へのデプロイ

### 1. Container Apps 環境の作成

```bash
az containerapp env create \
  --name my-c7n-env \
  --resource-group my-rg \
  --location japaneast
```

### 2. 定期実行ジョブの作成

```bash
az containerapp job create \
  --name c7n-scheduled-job \
  --resource-group my-rg \
  --environment my-c7n-env \
  --trigger-type Schedule \
  --cron-expression "0 */6 * * *" \
  --replica-timeout 1800 \
  --image cloudcustodian/c7n-azure-container-apps:latest \
  --cpu 0.5 --memory 1Gi \
  --mi-system-assigned \
  --env-vars \
    "AZURE_SUBSCRIPTION_ID=<subscription-id>" \
    "AZURE_POLICY_STORAGE_URI=https://mystorageaccount.blob.core.windows.net/policies"
```

### 3. イベント駆動ジョブの作成

```bash
az containerapp job create \
  --name c7n-event-job \
  --resource-group my-rg \
  --environment my-c7n-env \
  --trigger-type Event \
  --replica-timeout 1800 \
  --min-executions 0 \
  --max-executions 10 \
  --polling-interval 60 \
  --scale-rule-name azure-queue \
  --scale-rule-type azure-queue \
  --scale-rule-metadata \
    "accountName=mystorageaccount" \
    "queueName=c7n-events" \
    "queueLength=1" \
  --scale-rule-auth "connection=queue-connection-string" \
  --image cloudcustodian/c7n-azure-container-apps:latest \
  --cpu 0.5 --memory 1Gi \
  --mi-system-assigned \
  --env-vars \
    "AZURE_SUBSCRIPTION_ID=<subscription-id>" \
    "AZURE_POLICY_STORAGE_URI=https://mystorageaccount.blob.core.windows.net/policies" \
    "AZURE_QUEUE_STORAGE_ACCOUNT=mystorageaccount" \
    "AZURE_QUEUE_NAME=c7n-events"
```

## ポリシー例

### 定期実行ポリシー

```yaml
policies:
  - name: find-untagged-vms
    resource: azure.vm
    mode:
      type: container-periodic
      schedule: "0 */6 * * *"
    filters:
      - type: value
        key: tags
        value: null
    actions:
      - type: notify
        template: default
        subject: "Untagged VMs found"
```

### イベント駆動ポリシー

```yaml
policies:
  - name: auto-tag-vm-creator
    resource: azure.vm
    mode:
      type: container-event
      events:
        - VmWrite
    actions:
      - type: auto-tag-user
        tag: CreatedBy
```

## 開発

### ローカル開発環境のセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/your-org/c7n-azure-container-apps.git
cd c7n-azure-container-apps

# 仮想環境を作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 開発用依存関係をインストール
pip install -e ".[dev]"

# テストを実行
pytest
```

### Docker イメージのビルド

```bash
docker build -f docker/Dockerfile -t c7n-azure-container-apps:local .
```

## ライセンス

Apache License 2.0 - 詳細は [LICENSE](LICENSE) を参照してください。

## 関連リンク

- [Cloud Custodian](https://cloudcustodian.io/)
- [c7n-azure ドキュメント](https://cloudcustodian.io/docs/azure/)
- [Azure Container Apps Jobs](https://learn.microsoft.com/azure/container-apps/jobs)

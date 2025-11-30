# Getting Started - Azure Container Apps へのデプロイ

このガイドでは、c7n-azure-container-apps を Azure Container Apps にデプロイし、Cloud Custodian ポリシーを実行する手順を説明します。

## 目次

- [前提条件](#前提条件)
- [クイックスタート（30分）](#クイックスタート30分)
- [詳細な設定](#詳細な設定)
- [動作確認](#動作確認)
- [トラブルシューティング](#トラブルシューティング)

## 前提条件

### 必要なツール

- [Azure CLI](https://docs.microsoft.com/ja-jp/cli/azure/install-azure-cli) v2.50.0 以上
- [Terraform](https://www.terraform.io/downloads) v1.5.0 以上（オプション）
- Azure サブスクリプション

### 必要な Azure 権限

デプロイを実行するユーザーには以下の権限が必要です:

- `Contributor` ロール（リソース作成用）
- `User Access Administrator` ロール（マネージド ID へのロール割り当て用）
- サービス プリンシパルを利用する場合は [Create an Azure service principal with Azure CLI](https://learn.microsoft.com/cli/azure/azure-cli-sp-tutorial-1) に従って `az ad sp create-for-rbac` で作成し、対象サブスクリプション/リソースグループへ必要最小限のロールを付与する

Cloud Custodian が管理するリソースに対しては:

- `Reader` ロール（読み取り専用ポリシーの場合）
- `Contributor` ロール（リソース変更ポリシーの場合）

## クイックスタート（30分）

### Step 1: Azure にログイン

```bash
# Azure CLI でログイン
az login

# サブスクリプションを選択
az account set --subscription "YOUR_SUBSCRIPTION_NAME"

# 確認
az account show --output table
```

> CI/CD や自動化では以下のようにサービス プリンシパルでログインしてから `az account set` を実行します。

```bash
az login \
  --service-principal \
  --username <APP_ID> \
  --password <CLIENT_SECRET> \
  --tenant <TENANT_ID>
az account set --subscription <SUBSCRIPTION_ID>
```

### Step 2: リソースグループを作成

```bash
# 環境変数を設定
RESOURCE_GROUP="rg-c7n-custodian"
LOCATION="japaneast"
UNIQUE_ID=$(openssl rand -hex 4)

# リソースグループを作成
az group create --name $RESOURCE_GROUP --location $LOCATION
```

### Step 3: Container Apps 環境を作成

```bash
# 環境名
ENVIRONMENT="cae-c7n-$UNIQUE_ID"

# Container Apps 環境を作成
az containerapp env create \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

### Step 4: ストレージアカウントを作成（イベント駆動用）

```bash
STORAGE_ACCOUNT="stc7n$UNIQUE_ID"

# ストレージアカウントを作成
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# キューを作成
az storage queue create \
  --name "c7n-events" \
  --account-name $STORAGE_ACCOUNT
```

### Step 5: マネージド ID を作成

```bash
IDENTITY_NAME="id-c7n-$UNIQUE_ID"

# ユーザー割り当てマネージド ID を作成
az identity create \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP

# ID のリソース ID を取得
IDENTITY_ID=$(az identity show \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id --output tsv)

# ID のプリンシパル ID を取得
PRINCIPAL_ID=$(az identity show \
  --name $IDENTITY_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId --output tsv)
```

### Step 6: マネージド ID にロールを割り当て

```bash
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# サブスクリプションに Reader ロールを割り当て（ポリシー実行用）
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Reader" \
  --scope "/subscriptions/$SUBSCRIPTION_ID"

# ストレージキューへのアクセス権を付与
STORAGE_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id --output tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Queue Data Contributor" \
  --scope $STORAGE_ID
```

### Step 7: ポリシーファイルを準備

```bash
# ポリシー用 Blob コンテナを作成
az storage container create \
  --name "policies" \
  --account-name $STORAGE_ACCOUNT

# サンプルポリシーをアップロード
cat << 'EOF' > /tmp/vm-policy.yml
policies:
  - name: list-running-vms
    resource: azure.vm
    filters:
      - type: instance-view
        key: statuses[].code
        op: contains
        value: "PowerState/running"
EOF

az storage blob upload \
  --account-name $STORAGE_ACCOUNT \
  --container-name policies \
  --name vm-policy.yml \
  --file /tmp/vm-policy.yml
```

### Step 8: Container Apps Job をデプロイ（スケジュール）

```bash
JOB_NAME="c7n-scheduled"

# ストレージアカウントの接続文字列を取得
STORAGE_CONNECTION=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query connectionString --output tsv)

# Container Apps Job を作成（毎日 9:00 JST に実行）
az containerapp job create \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --trigger-type "Schedule" \
  --cron-expression "0 0 * * *" \
  --parallelism 1 \
  --replica-timeout 1800 \
  --replica-retry-limit 1 \
  --replica-completion-count 1 \
  --image "fukasawah/c7n-azure-container-apps:latest" \
  --cpu "0.5" \
  --memory "1Gi" \
  --mi-user-assigned "$IDENTITY_ID" \
  --env-vars \
    "C7N_POLICY_PATH=https://$STORAGE_ACCOUNT.blob.core.windows.net/policies/vm-policy.yml" \
    "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
    "AZURE_CLIENT_ID=$(az identity show --name $IDENTITY_NAME --resource-group $RESOURCE_GROUP --query clientId --output tsv)"
```

### Step 9: 動作確認

```bash
# 手動でジョブを実行
az containerapp job start \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP

# 実行履歴を確認
az containerapp job execution list \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table

# ログを確認（実行 ID を指定）
EXECUTION_NAME=$(az containerapp job execution list \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[0].name" --output tsv)

az containerapp job logs show \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP \
  --execution $EXECUTION_NAME
```

## 詳細な設定

### イベント駆動ジョブの設定

リソース変更をトリガーにポリシーを実行する場合:

```bash
JOB_NAME="c7n-event-driven"

# KEDA スケールルールを使用した Job を作成
az containerapp job create \
  --name $JOB_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --trigger-type "Event" \
  --min-executions 0 \
  --max-executions 10 \
  --parallelism 1 \
  --replica-timeout 1800 \
  --replica-retry-limit 1 \
  --image "ghcr.io/cloudcustodian/c7n-azure-container-apps:latest" \
  --cpu "0.5" \
  --memory "1Gi" \
  --user-assigned $IDENTITY_ID \
  --scale-rule-name "queue-trigger" \
  --scale-rule-type "azure-queue" \
  --scale-rule-metadata \
    "queueName=c7n-events" \
    "queueLength=1" \
    "accountName=$STORAGE_ACCOUNT" \
  --scale-rule-identity $IDENTITY_ID \
  --env-vars \
    "C7N_POLICY_PATH=https://$STORAGE_ACCOUNT.blob.core.windows.net/policies/" \
    "C7N_QUEUE_NAME=c7n-events" \
    "C7N_STORAGE_ACCOUNT=$STORAGE_ACCOUNT" \
    "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
    "AZURE_CLIENT_ID=$(az identity show --name $IDENTITY_NAME --resource-group $RESOURCE_GROUP --query clientId --output tsv)"
```

### Event Grid サブスクリプションの作成

```bash
# Event Grid システムトピックを作成
az eventgrid system-topic create \
  --name "evgt-azure-events" \
  --resource-group $RESOURCE_GROUP \
  --source "/subscriptions/$SUBSCRIPTION_ID" \
  --topic-type "Microsoft.Resources.Subscriptions" \
  --location global

# ストレージキューへのサブスクリプションを作成
STORAGE_ENDPOINT="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT/queueServices/default/queues/c7n-events"

az eventgrid system-topic event-subscription create \
  --name "sub-c7n-events" \
  --system-topic-name "evgt-azure-events" \
  --resource-group $RESOURCE_GROUP \
  --endpoint-type "storagequeue" \
  --endpoint $STORAGE_ENDPOINT \
  --included-event-types \
    "Microsoft.Resources.ResourceWriteSuccess" \
    "Microsoft.Resources.ResourceDeleteSuccess"
```

### Terraform を使用したデプロイ

より再現性のあるデプロイには Terraform を使用してください:

```bash
cd deploy/terraform

# 変数を設定
cat << EOF > terraform.tfvars
resource_group_name = "rg-c7n-custodian"
location            = "japaneast"
environment_name    = "cae-c7n-custodian"
subscription_id     = "YOUR_SUBSCRIPTION_ID"
EOF

# デプロイ
terraform init
terraform plan
terraform apply
```

## 環境変数リファレンス

| 環境変数 | 必須 | 説明 | 例 |
|----------|------|------|-----|
| `C7N_POLICY_PATH` | ✅ | ポリシーファイルのパス（ローカルまたは Blob URL） | `https://storage.blob.core.windows.net/policies/` |
| `AZURE_SUBSCRIPTION_ID` | ✅ | ターゲットの Azure サブスクリプション ID | `00000000-0000-0000-0000-000000000000` |
| `AZURE_CLIENT_ID` | ✅ | マネージド ID のクライアント ID | `00000000-0000-0000-0000-000000000000` |
| `C7N_QUEUE_NAME` | ❌ | イベント駆動時のキュー名 | `c7n-events` |
| `C7N_STORAGE_ACCOUNT` | ❌ | ストレージアカウント名 | `stc7ncustodian` |
| `C7N_OUTPUT_DIR` | ❌ | 実行結果の出力先 | `/tmp/output` |
| `C7N_LOG_LEVEL` | ❌ | ログレベル | `DEBUG`, `INFO`, `WARNING` |

## 動作確認

### 手動実行

```bash
# スケジュールジョブを手動実行
az containerapp job start \
  --name c7n-scheduled \
  --resource-group $RESOURCE_GROUP

# 実行状態を確認
az containerapp job execution list \
  --name c7n-scheduled \
  --resource-group $RESOURCE_GROUP \
  --output table
```

### ログの確認

```bash
# Log Analytics ワークスペースでクエリ
az monitor log-analytics query \
  --workspace $LOG_WORKSPACE_ID \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'c7n-scheduled' | order by TimeGenerated desc | take 50"
```

## トラブルシューティング

### Job が起動しない

**症状:** スケジュール時刻になっても Job が実行されない

**確認事項:**
1. cron 式が正しいか確認（UTC 時刻）
2. Container Apps 環境が正常か確認
3. イメージが正しくプルできるか確認

```bash
# 環境の状態を確認
az containerapp env show \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --query "properties.provisioningState"
```

### 認証エラー

**症状:** `DefaultAzureCredential failed to retrieve a token`

**原因:** マネージド ID が正しく設定されていない

**対処:**
1. `AZURE_CLIENT_ID` が正しいか確認
2. マネージド ID に適切なロールが割り当てられているか確認

```bash
# ロール割り当てを確認
az role assignment list --assignee $PRINCIPAL_ID --output table
```

### ポリシーが見つからない

**症状:** `Policy file not found`

**原因:** Blob Storage へのアクセス権限がない

**対処:**
1. マネージド ID に `Storage Blob Data Reader` ロールを割り当て

```bash
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Storage Blob Data Reader" \
  --scope $STORAGE_ID
```

### キューからメッセージを取得できない

**症状:** イベント駆動ジョブが起動しない

**確認事項:**
1. KEDA スケールルールが正しく設定されているか
2. キューにメッセージが存在するか
3. マネージド ID にキューへのアクセス権があるか

```bash
# キュー内のメッセージ数を確認
az storage message peek \
  --queue-name c7n-events \
  --account-name $STORAGE_ACCOUNT \
  --num-messages 5
```

## 次のステップ

- [ポリシー作成ガイド](https://cloudcustodian.io/docs/azure/policy/resources/overview.html)
- [c7n-azure ドキュメント](https://cloudcustodian.io/docs/azure/gettingstarted.html)
- [Azure Container Apps Jobs ドキュメント](https://learn.microsoft.com/ja-jp/azure/container-apps/jobs)

## クリーンアップ

テスト後にリソースを削除する場合:

```bash
# リソースグループごと削除
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

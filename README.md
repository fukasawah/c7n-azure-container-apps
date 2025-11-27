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

## ドキュメント

| ドキュメント | 対象者 | 内容 |
|-------------|--------|------|
| [Getting Started](docs/GetStarted.md) | 利用者 | Azure へのデプロイ手順、クイックスタート |
| [CONTRIBUTING](CONTRIBUTING.md) | 開発者 | ローカル開発環境のセットアップ、テスト実行方法 |
| [CI/CD Setup](docs/CI_SETUP.md) | リポジトリオーナー | GitHub Secrets、権限設定、ワークフロー説明 |
| [Architecture](spec/adr/ADR-001-architecture-design.md) | 開発者・アーキテクト | 設計判断と技術選定理由 |

## クイックスタート

**Azure にデプロイする場合** → [Getting Started Guide](docs/GetStarted.md)

### Docker イメージ

```bash
# Docker Hub
docker pull cloudcustodian/c7n-azure-container-apps:latest

# GitHub Container Registry
docker pull ghcr.io/your-org/c7n-azure-container-apps:latest
```

### ローカルで試す

```bash
docker run --rm \
  -e AZURE_SUBSCRIPTION_ID=<subscription-id> \
  -v $(pwd)/policies:/policies:ro \
  cloudcustodian/c7n-azure-container-apps:latest \
  run-policy --policy-file /policies/my-policy.yml
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `AZURE_SUBSCRIPTION_ID` | Yes | 対象の Azure サブスクリプション ID |
| `C7N_POLICY_PATH` | Yes* | ポリシーファイル/ディレクトリのパス（ローカルまたは Blob URL） |
| `AZURE_CLIENT_ID` | Yes** | ユーザー割り当てマネージド ID のクライアント ID |
| `C7N_QUEUE_NAME` | No | イベント駆動時の Storage Queue 名 |
| `C7N_STORAGE_ACCOUNT` | No | イベントキュー用ストレージアカウント名 |
| `C7N_OUTPUT_DIR` | No | ポリシー実行結果の出力先（デフォルト: `/tmp/c7n-output`） |
| `C7N_LOG_LEVEL` | No | ログレベル（`DEBUG`, `INFO`, `WARNING`） |

\* ポリシーファイルパスは必須
\*\* ユーザー割り当てマネージド ID 使用時に必須（システム割り当て ID 使用時は不要）

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Container Apps Jobs                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  Schedule Job    │              │   Event Job     │          │
│  │  (cron trigger)  │              │  (queue trigger)│          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │                                 │                    │
│           └───────────────┬─────────────────┘                    │
│                           ▼                                      │
│              ┌─────────────────────┐                            │
│              │  c7n-azure-runner   │                            │
│              │  (this project)     │                            │
│              └──────────┬──────────┘                            │
│                         │                                        │
│           ┌─────────────┼─────────────┐                         │
│           ▼             ▼             ▼                         │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│     │ c7n-core │  │ c7n-azure│  │ Policies │                   │
│     └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────────┘
          │                               ▲
          │ Managed Identity              │ Event Grid
          ▼                               │
┌─────────────────────────────────────────┴───────────────────────┐
│                        Azure Resources                           │
│   VMs, Storage, Databases, Networks, etc.                       │
└─────────────────────────────────────────────────────────────────┘
```

## ポリシー例

### 定期実行ポリシー

```yaml
policies:
  - name: find-untagged-vms
    resource: azure.vm
    filters:
      - type: value
        key: tags
        value: null
```

### イベント駆動ポリシー

```yaml
policies:
  - name: auto-tag-vm-creator
    resource: azure.vm
    filters:
      - type: event
    actions:
      - type: auto-tag-user
        tag: CreatedBy
```

詳細なポリシー例は [examples/policies/](examples/policies/) を参照してください。

## 開発に参加する

開発に参加したい方は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

```bash
# クイックセットアップ
git clone https://github.com/your-org/c7n-azure-container-apps.git
cd c7n-azure-container-apps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## ライセンス

Apache License 2.0 - 詳細は [LICENSE](LICENSE) を参照してください。

## 関連リンク

- [Cloud Custodian](https://cloudcustodian.io/)
- [c7n-azure ドキュメント](https://cloudcustodian.io/docs/azure/)
- [Azure Container Apps Jobs](https://learn.microsoft.com/azure/container-apps/jobs)

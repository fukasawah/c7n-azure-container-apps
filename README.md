# Cloud Custodian Azure Container Apps Runner

[![Docker Build](https://github.com/fukasawah/az-c7n-azure-container-apps/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/fukasawah/az-c7n-azure-container-apps/actions/workflows/docker-publish.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Azure Container Apps Jobs 上で [Cloud Custodian](https://cloudcustodian.io/) の Azure ポリシーを実行するためのランナーです。

## 何ができるか

- **Azure Container Apps Jobs で c7n-azure を実行**
  - Event Grid + Storage Queue によるイベント駆動実行
  - Cron 式による定期実行
- **マネージド ID / サービス プリンシパルによる認証**
- **Cloud Custodian / c7n-azure の既存ポリシーをそのまま利用**
- **dryrun モード**
  - Azure リソースを変更せずに実行計画のみを確認
- **ローカル実行・デバッグ**
  - 開発者向けのローカル実行やデバッグ手法

詳細な CLI オプションやローカル開発手順は、README からリンクしている各ドキュメントを参照してください。

## ドキュメント構成

| ドキュメント | 対象者 | 主な内容 |
|-------------|--------|----------|
| [Getting Started](docs/GetStarted.md) | 利用者 | Azure Container Apps へのデプロイ手順、ジョブの設定、サンプルポリシー |
| [CONTRIBUTING](CONTRIBUTING.md) | 開発者 | ローカル開発・デバッグ、dryrun や CLI オプションの詳細、テスト実行方法 |
| [CI/CD Setup](docs/CI_SETUP.md) | リポジトリオーナー | GitHub Actions によるビルド・デプロイ、Secrets / 権限の設定 |
| [Architecture ADR](spec/adr/ADR-001-architecture-design.md) | アーキテクト・開発者 | なぜ Azure Container Apps Jobs を選んだか、設計判断の背景 |

## クイックスタート（Azure Container Apps）

Azure 上で動かす手順の全体像は [Getting Started](docs/GetStarted.md) に詳しく書いてあります。ここでは「どんなことをするのか」だけを簡潔に示します。

1. **Docker イメージを取得**

   ```bash
   # Docker Hub
   docker pull cloudcustodian/c7n-azure-container-apps:latest

   # GitHub Container Registry
   docker pull ghcr.io/fukasawah/c7n-azure-container-apps:latest
   ```

2. **Azure リソースを準備**

   - Container Apps Environment / Job
   - Event Grid + Storage Queue（イベント駆動を使う場合）
   - ポリシーファイルを格納するストレージ（例: Blob Storage）

3. **ジョブ（スケジュール / イベント）を作成**

   - スケジュール実行: cron 式で定義した Container Apps Job
   - イベント駆動実行: Queue スケーラー（KEDA）を設定した Container Apps Job

4. **ポリシー YAML を配置**

   - 既存の c7n / c7n-azure ポリシー定義をそのまま利用可能
   - サンプルは `examples/policies/` を参照

具体的な `az` コマンドや Bicep/Terraform での手順は、[docs/GetStarted.md](docs/GetStarted.md) を見てください。

## 主な機能一覧（リンク集）

README では細かいオプション説明を避け、機能の存在と参照先だけをまとめています。

- **ポリシー実行（必須機能）**
  - Azure Container Apps Jobs から Cloud Custodian ポリシーを実行
  - イベントモード / 定期モードをサポート
  - 詳細: [Getting Started](docs/GetStarted.md)

- **dryrun モード**
  - Azure リソースを変更せず、実行計画のみをログに出力
  - 例: `--dryrun` フラグ、環境変数 `C7N_DRYRUN` など
  - 使い方の詳細・挙動の注意点: [CONTRIBUTING.md](CONTRIBUTING.md) を参照

- **ローカル実行・デバッグ**
  - Docker コンテナ or ローカル Python から `c7n-azure-runner` を直接実行
  - Azure CLI / サービス プリンシパル / Managed Identity 経由で認証
  - デバッグ手法（`--verbose`, `pdb`, pytest など）は [CONTRIBUTING.md](CONTRIBUTING.md) に集約

- **CI/CD（GitHub Actions）**
  - Docker イメージのビルドとレジストリへの push
  - 環境ごとのデプロイフロー
  - 詳細: [docs/CI_SETUP.md](docs/CI_SETUP.md)

## 典型的なユースケース

### 1. 未タグ VM の検出（定期実行）

```yaml
policies:
  - name: find-untagged-vms
    resource: azure.vm
    filters:
      - type: value
        key: tags
        value: null
```

### 2. VM 作成者の自動タグ付け（イベント駆動）

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

より多くのサンプルは `examples/policies/` を参照してください。

## アーキテクチャ概要

Azure Container Apps 上でどのようにコンポーネントが連携するかを示す高レベル図です。実際の詳細な設計や制約は ADR を参照してください。

```
┌───────────────────────────────────────────────┐
│                Azure Container Apps Jobs                     │
├───────────────────────────────────────────────┤
│  ┌───────────────────┐      ┌───────────────────┐          │
│  │  Schedule Job    │      │   Event Job       │          │
│  │  (cron trigger)  │      │  (queue trigger)  │          │
│  └─────────┬─────────┘      └─────────┬─────────┘          │
│            │                            │                   │
│            └──────────────┬─────────────┘                   │
│                           ▼                                 │
│              ┌────────────────────────────┐                 │
│              │    c7n-azure-runner        │                 │
│              │        (this project)      │                 │
│              └─────────┬──────────────────┘                 │
│                        │                                    │
│        ┌───────────────┼──────────────┬──────────────┐      │
│        ▼               ▼              ▼              │      │
│   ┌───────────┐   ┌───────────┐   ┌───────────┐      │      │
│   │ c7n-core  │   │ c7n-azure │   │ Policies  │      │      │
│   └───────────┘   └───────────┘   └───────────┘      │      │
└───────────────────────────────────────────────┘
            │                              ▲
            │ Managed Identity / SP        │ Event Grid
            ▼                              │
┌───────────────────────────────────────────────────────────┐
│                     Azure Resources                       │
│   VMs, Storage, Databases, Networks, etc.                │
└───────────────────────────────────────────────────────────┘
```

より詳しいアーキテクチャの背景・設計判断は [ADR-001](spec/adr/ADR-001-architecture-design.md) を参照してください。

## 開発に参加するには

バグ報告や機能提案、コードでのコントリビュートを歓迎します。

- ローカル実行や dryrun / CLI オプションの詳細: [CONTRIBUTING.md](CONTRIBUTING.md)
- CI やリリースフロー: [docs/CI_SETUP.md](docs/CI_SETUP.md)

最小限のセットアップ例だけ載せておきます（詳細は CONTRIBUTING へ）。

```bash
git clone https://github.com/fukasawah/c7n-azure-container-apps.git
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

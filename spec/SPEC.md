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
- [ ] c7n-azure の既存ポリシースキーマを完全サポート
- [ ] `container-event` モードと `container-periodic` モードをサポート
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
- GitHub Container Registry: `ghcr.io/<owner>/c7n-azure-container-apps`

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

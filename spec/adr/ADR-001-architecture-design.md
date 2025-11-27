# ADR-001: アーキテクチャ設計方針

## ステータス

採用

## コンテキスト

Cloud Custodian (c7n) の Azure 実装を Azure Container Apps Jobs で動作させる必要がある。
既存の c7n-azure には container_host モジュールが存在するが、以下の問題がある：

1. APScheduler を使用した常駐型プロセスを前提としている
2. Linux 環境での APScheduler の制約により動作しない可能性がある
3. 古い Azure SDK を使用している箇所がある

## 決定

### 1. 非常駐型のジョブ実行モデルを採用

Container Apps Jobs の特性を活かし、ジョブは短時間で完了して終了するモデルを採用する。

- **Schedule 型ジョブ**: cron 式で定期実行、ポリシーを実行して終了
- **Event 型ジョブ**: Storage Queue にメッセージが来たら起動、処理して終了

### 2. コアロジックの分離

将来の Azure Functions 対応を見据え、トリガー非依存のコアライブラリとして `c7n_azure_runner` を設計する。

```
c7n_azure_runner (コアライブラリ)
├── ポリシー読み込み
├── ポリシー実行
└── イベント処理

c7n_azure_container_apps (Container Apps 固有)
├── CLI エントリポイント
└── Storage Queue 連携
```

### 3. c7n/c7n-azure への変更禁止

c7n と c7n-azure は pip でインストールして使用する。ソースコードの変更は行わない。
これにより、アップストリームのアップデートに追従しやすくなる。

### 4. Managed Identity ファースト

認証は Managed Identity を第一優先とする。
- System Assigned Managed Identity
- User Assigned Managed Identity

接続文字列やシークレットの使用は最小限に抑える。

## 影響

### ポジティブ

- クラウドネイティブな設計で運用負荷が低い
- 従量課金で常駐コストが発生しない
- 将来の拡張性が高い

### ネガティブ

- 既存の container_host モードとの互換性がない（新しいモード名が必要）
- コールドスタートのオーバーヘッドが発生する

## 参考資料

- [Azure Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [c7n-azure container_host](https://github.com/cloud-custodian/cloud-custodian/tree/main/tools/c7n_azure/c7n_azure/container_host)

# 設計アイデアメモ

このドキュメントは、Cloud Custodian Azure Container Apps Runner の将来拡張や
パフォーマンスチューニングのアイデアをラフにまとめるためのメモです。

## 1. 実行モードの構想

### 1.1 Jobs 起動モード（現状のメイン）

- Azure Container Apps **Jobs** を前提とした「非常駐・ワンショット」モデル
- Event-driven / Schedule-driven の 2 パターン
  - Event-driven: Storage Queue (KEDA azure-queue scaler)
  - Schedule-driven: Cron による定期実行
- 特徴
  - ジョブ実行中のみ vCPU / メモリが課金対象
  - スケール 0 に落ちている間はリソース課金ゼロ
  - コールドスタートは「ジョブごと」に発生（c7n / Python プロセスの起動コストを含む）
- 適したユースケース
  - 日次・時間単位のバッチポリシー
  - イベント頻度が低〜中程度のポリシー
  - 「専用 VM / AKS を置き換えたい」パターン

### 1.2 App 起動モード（将来的に検討）

- 同じコンテナイメージを Azure Container Apps **アプリ** として常駐運用
- `minReplicas >= 1` で常時 1 コンテナ以上を維持
  - 初期化処理（c7n ロードなど）は基本的に 1 度で済む
  - コールドスタート問題をほぼ解消可能
- イベントの受け方の候補
  - HTTP Ingress を公開して Webhook / API として受ける
  - Queue / Event Grid をポーリングする専用ループを実装
- 適したユースケース
  - 高頻度イベント（ほぼ常に何かしらイベントが来る）
  - レイテンシ要求の厳しい自動修復系ポリシー
- コスト面
  - VM 常駐よりは柔軟・従量課金だが、「常時 1 コンテナ分の idle/active コスト」は発生
  - フル serverless (Jobs のみ) と比べるとコストは増えるが、レイテンシを買うイメージ

### 1.3 2 モード併存の方針

- コアロジックは `c7n_azure_runner` に集約（トリガー非依存）
- 周辺をトリガーごとの薄いアダプタに分離
  - Jobs モード: いまの `c7n_azure_container_apps` エントリポイント
  - App モード: 将来追加する HTTP / Queue ループ用エントリポイント
- 運用設計
  - 9割のポリシーは Jobs モードでコスト最適化
  - レイテンシがシビアな一部だけ App モードで常駐運用

### 1.4 マルチクラウドと Runner の分離構想

- Cloud Custodian 自体は AWS/Azure/GCP などマルチクラウド対応だが、
  Runner はクラウドごとに分ける方針とする案
  - 本プロジェクト: Azure 用 Runner (`c7n_azure_runner`)
  - 別プロジェクト案: AWS 用 Runner (`c7n_aws_runner` 的なもの)
- 理由
  - 認証・権限まわりの前提がクラウドごとに大きく異なる
    - Azure: Managed Identity / AAD / RBAC
    - AWS: AssumeRole / Access Key / IAM
  - ランタイム初期化時に不要な Provider を読み込まないようにし、
    起動時間と依存関係をシンプルに保つ
- 実行基盤の例
  - Azure 用 Runner: Azure Container Apps Jobs / Azure Functions (Flex)
  - AWS 用 Runner: ECS/Fargate / Lambda / EKS など

### 1.5 マルチサブスクリプション対応の方針メモ

- 背景
  - c7n は本来、組織としてのガバナンスルールを一元管理するためのツール
  - サブスクリプションごとにバラバラに c7n/container_host を立てる運用だと、
    各自が独自ルールを持ち込みやすくガバナンスが崩れやすい
  - 一方で、サブスクリプションごとに適用したいポリシーが異なるニーズも実務上は存在する

- モードのイメージ
  - **Single-subscription モード（現状/互換）**
    - `AZURE_SUBSCRIPTION_ID` 1 つを前提に、Blob 上の YAML を「そのサブスク用ポリシー」として全て読み込む
    - 旧 container_host と近いモデル（サブスクリプション単位でアプリをデプロイ）
  - **Multi-subscription モード（将来案）**
    - Runner 1 つの実行の中で、`AZURE_SUBSCRIPTION_IDS`（または ID の列挙）をループして、
      複数サブスクリプションに同じポリシーセット or サブスク別ポリシーセットを適用する
    - 「環境 = ガバナンス境界」「その配下に多数のサブスク」を実現したいときの選択肢

- ポリシー混在リスクと分離戦略
  - c7n の Provider / Resource レジストリはプロセス内でグローバルだが、
    実際の実行スコープ（どのサブスクリプションに対して動くか）は Config + PolicyCollection 側で決まる
  - マルチサブスク対応時の懸念:
    - 「サブスク X 用のポリシーが、誤って Y にも適用される」リスク
  - 分離戦略の案:
    - サブスクリプションごとに別 Config（`subscription_id=subX`）と別 PolicyCollection を構築し、
      `for sub_id in subscription_ids: run(policies_for_sub_id, config_for_sub_id)` という形で実行を分離する
    - Blob 構造でサブスクごとのポリシーセットを分ける
      - 例: `policies/shared/`（全サブスク共通）、`policies/subs/<sub-id>/*.yml`（サブスク専用）
      - Runner は共通 + 対象サブスク用ディレクトリのみ読み込む
    - フィルタで `subscription_id` を指定するのは「例外ポリシー」用にとどめ、
      通常は構成（パス構造/PolicyLoaderの読み方）でスコープを切る

- モード切替・互換性に関するメモ
  - 旧 container_host からの移行ユーザー向けには、
    いまの Blob 全読み込み挙動を維持する **legacy モード** を用意する案
    - 例: `C7N_POLICY_MODE=legacy`（デフォルト）
  - サブスクリプション別のスコープ分離を使いたいユーザー向けには、
    Blob のディレクトリ構造やファイル名を解釈する **scoped モード** を環境変数/起動引数で選択可能にする案
    - 例: `C7N_POLICY_MODE=by-subscription-dir` など
  - これにより、
    - 既存利用者は構成を変えずに移行可能
    - 新規利用者はマルチサブスク前提の構成・運用を最初から選べる
  - **Session/Subscription 適用メモ**
    - 実行単位で「これから適用するサブスクリプション ID」を決め、Runner 内の Session 管理層に明示的に渡す。`local_session` のキャッシュ任せにせず、`Session(subscription_id=sub_id)` を生成・ウォームアップしてから PolicyLoader / PolicyExecutor へ渡すのが安全。
    - 資格情報（Managed Identity / SP）はプロセス内で 1 度だけ初期化して共有し、サブスクごとに Session だけ差し替えると無駄がない。Session 切り替え処理は IDEA 上のモード切替とセットで設計メモに残しておく。

## 2. パフォーマンス / スループットチューニング

### 2.1 Queue ベースイベント処理

現状の `QueueHandler`:

- `receive_messages(max_messages=..., visibility_timeout=...)` で 1 回の取得件数を制御
- `process_single_message()` は `max_messages=1` で単一メッセージのみ処理
- メッセージ処理成功時のみ `delete_message` 実行
  - 失敗時は delete しない → at-least-once / 再配信前提

今後のチューニングアイデア:

- **バッチ処理メソッドの追加**
  - 例: `process_batch(max_messages: int, max_duration_sec: int)` のような API
  - 1 Job 実行中に「可能な限り多くのメッセージを処理」し、
    - 件数上限 or 時間上限で Job を終了
- **Container Apps Jobs 側のスケール設定との組み合わせ**
  - `eventTriggerConfig.scale.maxExecutions` : 並列 Job 数の上限
  - `eventTriggerConfig.scale.pollingInterval` : ポーリング間隔
  - キュー長 × バッチサイズ × maxExecutions でスループットが決まるイメージ
- **idempotent なポリシー設計**
  - Queue + KEDA + Jobs は at-least-once セマンティクス
  - 同一イベントが 2 回実行されても壊れない設計（タグ付け、通知、修復処理など）を基本とする

### 2.2 定期実行ポリシー

- Jobs モード
  - Cron ジョブで一定間隔ごとにポリシー実行
  - リソース数が多い場合は、
    - サブスクリプション単位 / リソースグループ単位などで Job を分割
    - Job ごとに `AZURE_SUBSCRIPTION_ID` やフィルタ条件を変える
- App モード（将来）
  - 内部スケジューラ（APScheduler 等）は極力使わず、
    - 別の Jobs / Logic Apps / Functions から HTTP で叩く
  - App は「ポリシーを実行する API」として振る舞う

### 2.3 Job 実行時間と制限

- Container Apps Jobs の制限
  - 最大実行時間: 30 分（1800 秒）
- 対応方針
  - 1 Job のターゲット処理時間を 5〜10 分程度に収めるようなバッチ設計
  - 数が多い場合はポリシー分割 or スコープ分割

### 2.4 PolicyLoader と Provider 初期化戦略

- 現状の実装
  - `c7n_azure_runner.policy_loader.PolicyLoader.__init__` で
    - `from c7n import resources` をインポート
    - `resources.load_available()` を呼び出し
  - `load_available()` の挙動（`tmp/c7n-source/c7n/resources/__init__.py` より）
    - `PROVIDER_NAMES = ('aws', 'azure', 'gcp', 'k8s', 'openstack', 'awscc', 'tencentcloud', 'oci', 'terraform')`
    - 各 provider について `load_providers((provider,))` を試行
    - ImportError が出なければ `found` に追加
    - `resources=True` の場合、`load_resources(['aws.*', 'azure.*', ...])` を呼び、
      各 provider のリソースタイプをレジストリに登録
  - その後、`_build_options()` で Azure Provider (`c7n_azure.provider.Azure`) のみを初期化
- 含意
  - 実際にポリシーを評価するのは Azure Provider 前提だが、
    インポート・初期化される provider / resource は環境にインストールされているものほぼ全て
  - Container Apps Jobs モデルでは Job ごとにプロセスが起動するため、
    毎回この初期化コストがかかる可能性がある（コールドスタート時間・メモリの増加要因）
- 最適化アイデア
  - Azure 専用 Runner である前提を活かし、`load_available()` ではなく
    - `resources.load_providers({'azure'})`
    - `resources.load_resources(['azure.*'])`
    のように Azure Provider のみを明示的に初期化する案
  - 効果
    - 不要な provider (`aws`, `gcp`, `k8s`, ...) の `initialize_xxx()` を避けられる
    - Job 起動ごとの初期化時間とメモリフットプリントを削減できる可能性
  - 将来的な拡張案（要検討）
    - YAML ポリシーを軽くパースして `policies[*].resource` を事前にスキャンし、
      Azure 以外のリソースが含まれていないことを検証（含まれていればエラー）
    - 必要なクラウド/リソースに応じて、`load_resources()` に渡すパターンをさらに絞り込む

## 3. その他やっておくと良さそうなこと

### 3.1 メトリクス設計

- 目的: 「処理がおいついていない」「著しく遅くなっている」を検知する

- 取得したいメトリクス候補とレイヤー
  - **ジョブ実行レイヤー（Container Apps Jobs / SystemLogs）**
    - Job 実行時間（start〜end, duration_sec）
    - Job のステータス（Succeeded / Failed / Canceled）
    - 失敗率（直近 N 回中の失敗回数）
  - **アプリレイヤー（ConsoleLogs / アプリ内ログ）**
    - 1 Job あたりの処理メッセージ数
    - 1 Job あたりの対象リソース数（c7n ポリシーがヒットした件数）
    - ポリシーごとの実行結果サマリ
      - `policy_name`, `resource_type`, `matched_resources_count`, `actions_executed` など
  - **キュー/イベントレイヤー（Storage Queue）**
    - キュー長の推移（`peek_queue_length` や Storage Queue メトリクス）
    - 単位時間あたりのメッセージ流入数 / 消費数

- 代表的な監視ポイント
  - 「キュー長が 1 時間以上にわたって増え続けている」
    - → スループット不足 or エラー多発
  - 「Job 実行時間の P95 が 20 分を超え続けている」
    - → Container Apps Jobs の 30 分上限に近づいている
  - 「失敗率が一定以上（例: 5%）を超えている」
    - → c7n 側のエラー / Azure API スロットリングなどの疑い

- 送信先
  - Azure Monitor / Log Analytics Workspace
    - `ContainerAppConsoleLogs_CL`, `ContainerAppSystemLogs_CL` を前提
    - 必要に応じて Application Insights / OpenTelemetry 連携
  - 必要に応じてカスタムメトリクス（Prometheus 風カウンタをログから集約 など）

### 3.2 ログ構造

- JSON ログ or 構造化ログを前提
- 重要なフィールド
  - `subscription_id`
  - `policy_name`
  - `mode` (event / periodic / app)
  - `job_execution_id`
  - `queue_message_id` / `event_id`

### 3.3 エラーハンドリング / リトライ

- QueueHandler
  - デコード失敗時や一時的なエラー時の挙動（ログレベル、DLQ の検討）
- c7n 実行
  - Azure 側のスロットリング (429) や一時的な API エラーへのリトライ戦略

### 3.4 将来の Azure Functions (Flex Consumption) 対応

- `c7n_azure_runner` を Functions からも再利用
- HTTP / Queue トリガーを Functions にマッピング
- Container Apps / Jobs / Functions の 3 パターンから選べる構成を目指す

---

※ このファイルは「アイデア置き場」として、気づいたことを気軽に追記していく想定です。

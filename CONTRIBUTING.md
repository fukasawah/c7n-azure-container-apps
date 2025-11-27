# Contributing to c7n-azure-container-apps

c7n-azure-container-apps への貢献を歓迎します！このドキュメントでは、開発環境のセットアップとコントリビューション方法を説明します。

## 目次

- [開発環境のセットアップ](#開発環境のセットアップ)
- [コードスタイル](#コードスタイル)
- [テストの実行](#テストの実行)
- [プルリクエストの作成](#プルリクエストの作成)
- [プロジェクト構造](#プロジェクト構造)

## 開発環境のセットアップ

### 前提条件

- **Python 3.14** 以上
- **pip** (最新版推奨)
- **Git**

#### Python 3.14 のインストール

Python 3.14 は2025年12月リリース予定です。現在は開発版を使用します。

**pyenv を使用する場合（推奨）:**

```bash
# pyenv のインストール (まだの場合)
curl https://pyenv.run | bash

# Python 3.14 のインストール
pyenv install 3.14.0a2  # または最新の利用可能バージョン
pyenv local 3.14.0a2
```

**Docker を使用する場合:**

```bash
# 開発用コンテナを起動
docker run -it --rm -v $(pwd):/app -w /app python:3.14-slim bash
```

### リポジトリのクローン

```bash
git clone https://github.com/YOUR-ORG/c7n-azure-container-apps.git
cd c7n-azure-container-apps
```

### 仮想環境の作成

```bash
# 仮想環境を作成
python -m venv .venv

# 仮想環境を有効化
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

### 依存関係のインストール

```bash
# 開発用依存関係を含めてインストール
pip install -e ".[dev]"
```

これにより以下がインストールされます:
- `c7n` と `c7n-azure` (Cloud Custodian)
- `pytest`, `pytest-cov` (テスト)
- `ruff` (リンター/フォーマッター)
- `mypy` (型チェック)
- その他の開発ツール

### インストールの確認

```bash
# CLI が動作することを確認
c7n-azure-runner --help

# バージョン確認
c7n-azure-runner --version

# 簡易テスト
pytest --co -q  # テスト収集のみ
```

## コードスタイル

このプロジェクトでは、以下のツールを使用してコード品質を維持しています。

### Ruff（リンター & フォーマッター）

```bash
# リントの実行
ruff check .

# 自動修正
ruff check . --fix

# フォーマットの実行
ruff format .

# フォーマットチェック（CI用）
ruff format --check .
```

### Git Hooks のセットアップ（推奨）

コミット前に自動で lint/format チェックを実行する pre-commit フックを用意しています。
以下のコマンドでセットアップしてください：

```bash
git config core.hooksPath .githooks
```

セットアップ後、`git commit` 時に自動的に以下がチェックされます：

- `ruff check` - リントエラーの検出
- `ruff format --check` - フォーマットの確認

エラーがある場合はコミットが中断されます。修正してから再度コミットしてください。

```bash
# エラーを修正する場合
ruff check --fix .  # リントエラーの自動修正
ruff format .       # フォーマットの適用
```

フックを無効化する場合：

```bash
git config --unset core.hooksPath
```

### MyPy（型チェック）

```bash
mypy src/
```

### コードスタイルガイドライン

- **PEP 8** に準拠
- **型ヒント** を積極的に使用
- **docstring** を全ての公開関数・クラスに記載
- **日本語コメント** を推奨（コードは英語）

```python
def process_event(event: dict[str, Any]) -> ParsedEvent:
    """イベントを解析して ParsedEvent を返す。
    
    Args:
        event: Storage Queue から受信した生イベント
        
    Returns:
        解析済みのイベントオブジェクト
        
    Raises:
        ValueError: イベント形式が不正な場合
    """
    ...
```

## テストの実行

### 全テストの実行

```bash
pytest
```

### 特定のテストファイルを実行

```bash
pytest tests/test_config.py
```

### 特定のテスト関数を実行

```bash
pytest tests/test_config.py::test_runner_config_from_env
```

### カバレッジ付きで実行

```bash
pytest --cov=c7n_azure_runner --cov=c7n_azure_container_apps --cov-report=html
# カバレッジレポートを開く
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### テストの書き方

TDD（テスト駆動開発）を推奨します。新機能を追加する場合は：

1. まず失敗するテストを書く
2. テストを通す最小限のコードを書く
3. リファクタリングする

```python
# tests/test_example.py
import pytest
from c7n_azure_runner.config import RunnerConfig

def test_config_validation():
    """設定のバリデーションをテストする。"""
    config = RunnerConfig(
        policy_path="/path/to/policy.yml",
        subscription_id="00000000-0000-0000-0000-000000000000"
    )
    assert config.validate() is True
```

## プルリクエストの作成

### ブランチ命名規則

```
feature/add-event-filter      # 新機能
fix/queue-connection-error    # バグ修正
docs/update-readme           # ドキュメント更新
refactor/simplify-config     # リファクタリング
```

### コミットメッセージ規則

[Conventional Commits](https://www.conventionalcommits.org/) を使用:

```
feat: Event Grid からの webhook 受信を追加
fix: Queue 接続タイムアウト時のリトライを修正
docs: README に Azure 設定手順を追加
refactor: PolicyExecutor のエラーハンドリングを改善
test: event_processor のユニットテストを追加
chore: CI ワークフローを更新
```

### PR チェックリスト

PR を作成する前に以下を確認してください:

```
□ Git hooks がセットアップされている (git config core.hooksPath .githooks)
□ テストが全て通る (pytest)
□ リントエラーがない (ruff check .)
□ フォーマットが適用されている (ruff format .)
□ 型チェックが通る (mypy src/)
□ ドキュメントを更新した（必要な場合）
□ SPEC.md を更新した（仕様変更の場合）
```

### PR 作成手順

```bash
# 1. feature ブランチを作成
git checkout -b feature/your-feature

# 2. 変更をコミット
git add .
git commit -m "feat: 新機能を追加"

# 3. リモートにプッシュ
git push origin feature/your-feature

# 4. GitHub で PR を作成
```

## プロジェクト構造

```
c7n-azure-container-apps/
├── src/
│   ├── c7n_azure_runner/           # コアライブラリ（トリガー非依存）
│   │   ├── __init__.py
│   │   ├── config.py               # 設定クラス（Pydantic）
│   │   ├── policy_loader.py        # ポリシーローダー
│   │   ├── policy_executor.py      # ポリシー実行エンジン
│   │   └── event_processor.py      # イベント解析
│   │
│   └── c7n_azure_container_apps/   # Container Apps 固有の実装
│       ├── __init__.py
│       ├── cli.py                  # Click CLI コマンド
│       ├── entrypoint.py           # 自動モード判定
│       └── queue_handler.py        # Storage Queue クライアント
│
├── tests/                          # テストコード
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_event_processor.py
│   └── test_policy_executor.py
│
├── docker/
│   └── Dockerfile                  # マルチステージビルド
│
├── deploy/
│   └── terraform/                  # Terraform サンプル
│       └── main.tf
│
├── examples/
│   └── policies/                   # ポリシーサンプル
│       ├── scheduled-policy.yml
│       └── event-policy.yml
│
├── docs/                           # ドキュメント
│   ├── CI_SETUP.md                # CI 設定ガイド
│   └── GetStarted.md              # 利用開始ガイド
│
├── spec/                           # 仕様書
│   ├── SPEC.md
│   └── adr/                       # Architecture Decision Records
│
├── pyproject.toml                  # プロジェクト設定
├── README.md                       # 概要
└── CONTRIBUTING.md                 # このファイル
```

## 開発に役立つコマンド

```bash
# 依存関係の更新
pip install -e ".[dev]" --upgrade

# キャッシュのクリア
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +
find . -type d -name ".ruff_cache" -exec rm -rf {} +

# ローカルでの Docker ビルド
docker build -t c7n-azure-runner:dev -f docker/Dockerfile .

# Docker イメージのテスト
docker run --rm c7n-azure-runner:dev --help

# 依存関係の確認
pip list | grep c7n
```

## 質問・サポート

- **Issues**: バグ報告や機能要望は GitHub Issues へ
- **Discussions**: 質問や議論は GitHub Discussions へ

## ライセンス

Apache License 2.0 - 詳細は [LICENSE](LICENSE) を参照してください。

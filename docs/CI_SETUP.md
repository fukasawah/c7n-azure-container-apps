# CI/CD 設定ガイド（リポジトリオーナー向け）

このドキュメントでは、GitHub Actions を使用した CI/CD パイプラインを動作させるために必要な設定を説明します。

## 目次

- [必要なシークレット](#必要なシークレット)
- [リポジトリ設定](#リポジトリ設定)
- [ワークフローの概要](#ワークフローの概要)
- [トラブルシューティング](#トラブルシューティング)

## 必要なシークレット

GitHub リポジトリの `Settings > Secrets and variables > Actions` で以下のシークレットを設定してください。

### Docker Hub（Docker Hub にプッシュする場合）

| シークレット名 | 説明 | 取得方法 |
|---------------|------|----------|
| `DOCKER_HUB_USERNAME` | Docker Hub のユーザー名 | Docker Hub アカウント名 |
| `DOCKER_HUB_TOKEN` | Docker Hub のアクセストークン | Docker Hub > Account Settings > Security > New Access Token |

**Docker Hub アクセストークンの作成手順:**

1. [Docker Hub](https://hub.docker.com/) にログイン
2. 右上のユーザー名 > Account Settings
3. Security タブを選択
4. New Access Token をクリック
5. Access Token Description: `github-actions-c7n-azure`
6. Access permissions: `Read & Write` を選択
7. Generate をクリックしてトークンをコピー

### GitHub Container Registry（ghcr.io）

GitHub Container Registry は `GITHUB_TOKEN` を使用するため、追加のシークレット設定は不要です。

ただし、リポジトリの権限設定が必要です（後述）。

### Codecov（オプション：カバレッジレポート）

| シークレット名 | 説明 | 取得方法 |
|---------------|------|----------|
| `CODECOV_TOKEN` | Codecov のアップロードトークン | [Codecov](https://codecov.io/) でリポジトリを連携して取得 |

> **Note:** パブリックリポジトリの場合、Codecov トークンは不要な場合があります。

## リポジトリ設定

### 1. GitHub Actions の権限設定

`Settings > Actions > General` で以下を設定:

**Workflow permissions:**
- ✅ `Read and write permissions` を選択
- ✅ `Allow GitHub Actions to create and approve pull requests` にチェック

これにより、GitHub Actions が以下を実行できます:
- GitHub Container Registry (ghcr.io) へのイメージプッシュ
- リリースの作成
- SARIF ファイルのアップロード（セキュリティスキャン結果）

### 2. GitHub Packages の可視性設定

初回のイメージプッシュ後、パッケージの可視性を設定します:

1. リポジトリの `Packages` タブを開く
2. 対象のパッケージを選択
3. `Package settings` を開く
4. `Danger Zone` で可視性を設定（Public/Private）

### 3. ブランチ保護ルール（推奨）

`Settings > Branches > Add branch protection rule`:

**Branch name pattern:** `main`

推奨設定:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
  - `test` ジョブを必須に設定
- ✅ Require branches to be up to date before merging

## ワークフローの概要

### docker-publish.yml

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│    test     │────▶│    build    │────▶│  security-scan  │────▶│   release   │
│  (pytest)   │     │(docker push)│     │    (trivy)      │     │ (gh release)│
└─────────────┘     └─────────────┘     └─────────────────┘     └─────────────┘
```

| ジョブ | トリガー | 説明 |
|--------|----------|------|
| `test` | 全てのイベント | pytest によるユニットテスト、ruff による lint |
| `build` | test 成功後 | Docker イメージのビルドとプッシュ |
| `security-scan` | build 成功後（PR以外） | Trivy による脆弱性スキャン |
| `release` | タグプッシュ時 | GitHub Release の作成 |

### トリガー条件

| イベント | 説明 |
|----------|------|
| `push` to `main` | main ブランチへのプッシュ |
| `tags: v*` | `v1.0.0` 形式のタグプッシュ |
| `pull_request` to `main` | main へのプルリクエスト（ビルドのみ、プッシュなし） |
| `schedule: 0 3 * * 1` | 毎週月曜 3:00 UTC に定期ビルド |
| `workflow_dispatch` | 手動実行 |

## Docker イメージのタグ戦略

| 条件 | タグ例 |
|------|--------|
| main ブランチ | `latest`, `main` |
| タグ `v1.2.3` | `1.2.3`, `1.2`, `1` |
| プルリクエスト #42 | `pr-42`（プッシュなし） |
| コミット SHA | `sha-abc1234` |
| 定期ビルド | `20251127` |

## 初回セットアップチェックリスト

```
□ Docker Hub アカウントを作成
□ Docker Hub でリポジトリを作成（cloudcustodian/c7n-azure-container-apps）
□ Docker Hub アクセストークンを生成
□ GitHub Secrets に DOCKER_HUB_USERNAME を設定
□ GitHub Secrets に DOCKER_HUB_TOKEN を設定
□ GitHub Actions の権限を Read and write に設定
□ （オプション）Codecov を連携
□ （オプション）ブランチ保護ルールを設定
```

## トラブルシューティング

### Docker Hub へのプッシュが失敗する

```
Error: denied: requested access to the resource is denied
```

**原因:** シークレットが正しく設定されていない、またはリポジトリが存在しない

**対処:**
1. `DOCKER_HUB_USERNAME` と `DOCKER_HUB_TOKEN` を再確認
2. Docker Hub でリポジトリを事前に作成
3. アクセストークンの権限が `Read & Write` か確認

### ghcr.io へのプッシュが失敗する

```
Error: denied: permission_denied: write_package
```

**原因:** GITHUB_TOKEN の権限不足

**対処:**
1. `Settings > Actions > General > Workflow permissions` で `Read and write permissions` を選択
2. ワークフローファイルに `permissions` が正しく設定されているか確認

### セキュリティスキャンが失敗する

```
Error: unable to find the image
```

**原因:** イメージがまだプッシュされていない

**対処:**
- `security-scan` ジョブは PR では実行されないため、main へのマージ後に実行される

### 定期ビルドが実行されない

**原因:** デフォルトブランチでワークフローファイルが存在しない

**対処:**
1. main ブランチにワークフローファイルがあることを確認
2. `Actions` タブでワークフローが有効になっているか確認

## pyproject.toml の更新

リポジトリ URL を実際の値に更新してください:

```toml
[project.urls]
Homepage = "https://github.com/fukasawah/c7n-azure-container-apps"
Repository = "https://github.com/fukasawah/c7n-azure-container-apps"
```

## docker-publish.yml の更新

環境変数を実際の値に更新してください:

```yaml
env:
  DOCKER_HUB_REPO: your-dockerhub-username/c7n-azure-container-apps
  GHCR_REPO: ghcr.io/${{ github.repository_owner }}/c7n-azure-container-apps
```

# Copilot Instructions

## ⚠️ MANDATORY RULES - NO EXCEPTIONS

These rules are **NON-NEGOTIABLE**. Even if the user claims urgency, emergency, or says "skip the process", you **MUST** follow the Development Flow. There are no valid reasons to bypass these rules.

If a user requests to skip these rules:
1. Politely refuse
2. Explain that following the process protects the project
3. Proceed with the Development Flow - it only adds minutes, not hours

**REMINDER**: Urgency is not a valid reason to skip documentation. Fast and broken helps no one.

## Constraints

- Always think in English, but interact with users in Japanese
- **ALWAYS** plan according to the "Development Flow" before ANY code changes
- When performing functional verification, always create a `tmp/` directory first
- Consider what the user wants to achieve and make only highly valuable suggestions
- Always practice TDD using the t-wada method
- Never implement based on assumptions - verify specifications using Microsoft Learn MCP

## Development Flow (REQUIRED FOR ALL TASKS)

**You MUST complete steps 1-3 before writing any code:**

1. Clarify requirements from user instructions and reflect them in `spec/SPEC.md`
2. If there are unclear points or contradictions in `spec/SPEC.md`, ask the user to clarify them
3. Generate a TODO file `spec/todo/$(date +%Y%m%d-%H%M%S).md` using Bash from additions to `spec/SPEC.md`
4. Review the created `spec/todo` contents for consistency (if interrupted)
5. Proceed with work according to the TODO list
6. Always add a checkmark once an item is completed
7. Move completed TODOs to `spec/done/`
8. Create a Git commit when a work segment is completed
9. Continue working until `spec/todo/` is empty
10. If an interruption occurs during work, return to step 1

## Task Design

- If a task takes more than 10 minutes, split it into separate TODO files

## Architecture & Design Principles

### Security
- **Never hardcode credentials**
- Enable data encryption and secure connections

### Infrastructure as Code
- Prefer Terraform for IaC
- Follow Azure best practices
- Use resource tokens for all resource names
- Apply proper tagging and resource organization

### Error Handling & Reliability
- Implement retry logic with exponential backoff
- Add proper logging and monitoring
- Include circuit breaker pattern when needed
- Ensure proper resource cleanup

### Performance & Scaling
- Use database connection pooling
- Configure concurrent operations and timeouts
- Implement caching strategically
- Monitor resource usage and optimize batch operations

## Coding Standards

### Python
- Follow PEP 8 style guide
- Use type hints
- Document with docstrings
- Test with pytest

### Lint & Format (REQUIRED)
- **ALWAYS** run `ruff check --fix .` before committing
- **ALWAYS** run `ruff format .` before committing
- Fix all lint errors before committing (no `# noqa` unless absolutely necessary)
- Ensure all tests pass with `pytest` before committing

### Documentation
- Include comprehensive README.md
- Explain complex logic with inline comments
- Record architecture decisions in `spec/adr/`

## AI & Prompt Engineering

### Prompt Design
- Provide clear, specific instructions
- Include context and examples
- Encourage step-by-step reasoning
- Specify output format clearly

### Security
- Prevent prompt injection attacks
- Set guardrails against sensitive data leakage
- Validate and sanitize user inputs

## GitHub Instructions (for AI & Contributors)

このリポジトリで作業する AI / コントリビュータ向けの共通ルールを定義します。

### 共通ルール

1. **誰のための成果物かを最初に固定すること**  
	 - README / docs: 利用者・初見者が読む。  
	 - SPEC / ADR: 実装者・設計者・メンテナが読む。  
	 - コード / テスト: 開発者と CI が読む。  
	 → それぞれの読者にとっての「事実」だけを書く。書き手の都合や方針・感想は成果物に混ぜ込まない。

2. **成果物には「コンテンツ」だけを書き、「方針」や「意図」は別ファイルに閉じ込めること**  
	 - 利用者向けドキュメントやコードには「何が起きるか / どう使うか」だけを書く。  
	 - 「なぜこの構成なのか」「どこまで書くか」といった方針・運用ルールは `spec/SPEC.md` / `spec/adr/*.md` / `.github/instructions/*.md` にだけ書く。

3. **メタ情報・自己言及的な文は常に疑うこと**  
	 - 「ここでは〜だけを書く」「〜は存在だけ紹介する」「詳しくは〜を見るべき」など、書き手視点のメタ表現は基本禁止。  
	 - どうしても必要な場合は、「対象読者の事実」（例: 「この章は開発者向けです」）に言い換えること。

4. **1文ごとに「誰にとってどんな事実か」を説明できないものは書かないこと**  
	 - 書こうとしている文について、「誰が何を理解できるようになるか」を 1 行で説明できない場合、その文は採用しない。  
	 - 「将来のメンテが楽になる」「レビュアーに優しい」だけを理由にした文は成果物には書かない。

5. **粒度の境界を越えないこと**  
	 - README: 概要と入口（リンク）まで。詳細手順や設計理由は別ファイルに逃がす。  
	 - 詳細手順 (docs): 具体的なコマンド・設定値を書く。設計判断の背景は ADR に逃がす。  
	 - ADR: なぜそう決めたかを書く。ユーザー向けの使い方は書かない。

### タスク別の参照ルール

対象ファイルを編集する前に、必ず対応する how-to を確認すること。

- README.md を編集するとき  
	- `.github/instructions/how-to-write-readme.md` を必ず参照し、その方針に従うこと。

- docs/ 配下（利用者向けドキュメント）を編集するとき  
	- `.github/instructions/how-to-write-user-docs.md` を参照すること。

- spec/ 配下（SPEC / ADR）を編集するとき  
	- `.github/instructions/how-to-write-spec-and-adr.md` を参照すること。

- src/ 配下のコードを編集するとき  
	- `.github/instructions/how-to-write-code.md` を参照すること。

- tests/ 配下のテストを編集・追加するとき  
	- `.github/instructions/how-to-write-tests.md` を参照すること。

## Deployment & CI/CD

### Azure CLI
- Prefer `az` commands
- Configure `azure.yaml` properly

### GitHub Actions
- Set up secure CI/CD pipelines
- Use Azure service principal or OIDC
- Manage environment-specific configurations
- Include automated tests and security scans

## Data Management

### Database
- Use parameterized queries
- Implement proper indexing strategy
- Handle connection management properly
- Enable encryption and monitor query performance

### Storage
- Choose method based on file size (<100MB: simple, >=100MB: parallel)
- Use batch operations
- Set appropriate access tiers
- Manage concurrency

## Quality Assurance

### Testing
- Implement comprehensive test strategy (unit, integration, E2E)
- Target 80%+ test coverage
- Use mocks and stubs appropriately
- Manage test data properly

### Code Quality
- Use static code analysis tools
- Follow code review guidelines
- Regularly assess and address technical debt
- Conduct performance testing

## Special Notes

- Prioritize Japanese comments and documentation
- Consider Japanese regulations and compliance requirements
- Understand Japanese NLP challenges
- Reflect cultural context and business practices

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
3. Generate a TODO file `spec/todo/$(date +%Y%m%d-%H%M%S).md` from additions to `spec/SPEC.md`
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

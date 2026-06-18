# Project Governance

## Decision Making

### Maintainer Roles

| Role | Responsibilities | Decision Authority |
|------|-----------------|-------------------|
| Lead Maintainer | Project direction, release management, security | Final authority on all decisions |
| Core Maintainer | Code review, architecture, roadmap | Approve/reject PRs, set technical direction |
| Contributor | Bug fixes, features, documentation | Propose changes via issues/PRs |

### Decision Process

1. **Minor changes** (bug fixes, docs): Any maintainer can approve
2. **Feature additions**: Require 1 core maintainer approval
3. **Architecture changes**: Require lead maintainer + 1 core maintainer approval
4. **Breaking changes**: Require RFC process (see below)

### RFC Process

For significant changes that affect the public API or architecture:

1. Open an RFC issue with the `rfc` label
2. Describe: Problem, Proposed Solution, Alternatives, Impact
3. Minimum 7-day comment period
4. Requires 2 maintainer approvals to merge
5. ADR (Architecture Decision Record) must be updated

## Code Review Standards

### Review Checklist

- [ ] Code follows project style guidelines (ruff passes)
- [ ] Type annotations are complete (mypy passes)
- [ ] Tests cover new functionality (coverage ≥ 80%)
- [ ] No security vulnerabilities introduced (bandit passes)
- [ ] API changes are backward compatible or documented as breaking
- [ ] Documentation updated if needed

### Review Timeline

- Initial review: Within 3 business days
- Follow-up reviews: Within 2 business days
- Stale PRs: Closed after 30 days of inactivity

## Release Process

1. Pre-release checks pass (`PreReleaseChecker.run_all_checks()`)
2. Version bumped per conventional commits
3. CHANGELOG.md auto-generated
4. Tag created with signed commit
5. GitHub release published
6. PyPI package published

## Community Guidelines

### Issue Triage

| Label | Meaning | Response Time |
|-------|---------|---------------|
| `bug` | Confirmed bug | 5 business days |
| `enhancement` | Feature request | 10 business days |
| `security` | Security vulnerability | 48 hours |
| `good first issue` | Beginner-friendly | N/A |
| `help wanted` | Community help needed | N/A |

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions, ideas, show-and-tell
- **Pull Requests**: Code contributions

## Roadmap

### Current Focus (v0.2.0)

- Web UI dashboard (L5-01)
- PyPI publication (L5-08)
- Multi-language AST plugins (L5-06)
- SBP false alarm reduction (RD01)

### Future (v0.3.0+)

- Deep learning semantic detection (M01)
- Cross-language clone detection (M02)
- Plugin marketplace (L5-02)
- GitHub Action distribution (L5-04)

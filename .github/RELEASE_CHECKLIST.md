# Release Checklist

Use this checklist to ensure all steps are completed for a successful release.

## Pre-Release Checklist

### Code Quality
- [ ] All tests pass locally (`pytest`)
- [ ] Code coverage is above 80% (`pytest --cov`)
- [ ] No critical security issues (`safety check`, `bandit -r .`)
- [ ] Code follows style guidelines (`flake8`)
- [ ] All CI/CD checks pass on main branch

### Documentation
- [ ] README.md is up to date
- [ ] API documentation reflects any changes
- [ ] RELEASE.md is updated if process changes
- [ ] Version information is accurate

### Dependencies
- [ ] All dependencies are up to date and secure
- [ ] requirements.txt reflects current dependencies
- [ ] No known vulnerabilities in dependencies

## Release Process

### Automated Release (Recommended)
- [ ] Go to GitHub Actions → "Release and Deploy"
- [ ] Select appropriate release type (patch/minor/manual)
- [ ] For manual releases, specify version in YYYY.MM.PATCH format
- [ ] Run workflow and monitor for completion
- [ ] Verify release was created successfully

### Manual Release (If needed)
- [ ] Update version using script: `python scripts/bump_version.py [type]`
- [ ] Commit version change: `git commit -m "chore: bump version to X.Y.Z"`
- [ ] Create and push tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push --tags`
- [ ] Build Docker image: `docker build -t google-drive-service:X.Y.Z .`
- [ ] Tag for registry: `docker tag google-drive-service:X.Y.Z ghcr.io/pitchconnect/google-drive-service:X.Y.Z`
- [ ] Push to registry: `docker push ghcr.io/pitchconnect/google-drive-service:X.Y.Z`
- [ ] Create GitHub release with notes

## Post-Release Verification

### GitHub
- [ ] Release appears in GitHub Releases page
- [ ] Release notes are accurate and complete
- [ ] Git tag was created correctly
- [ ] All workflow steps completed successfully

### Docker Registry
- [ ] Image appears in GitHub Container Registry
- [ ] Image has correct tags (version, latest, monthly)
- [ ] Image metadata is correct
- [ ] Image can be pulled successfully

### Application
- [ ] Health check endpoint responds correctly (`GET /health`)
- [ ] Version endpoint shows correct version (`GET /version`)
- [ ] Application starts without errors
- [ ] All core functionality works as expected

### Deployment
- [ ] Update deployment configurations if needed
- [ ] Deploy to staging environment first
- [ ] Verify staging deployment works correctly
- [ ] Deploy to production environment
- [ ] Monitor application logs for errors

## Hotfix Release Checklist

### Preparation
- [ ] Identify the critical issue requiring hotfix
- [ ] Determine target branch (usually main)
- [ ] Prepare fix and test thoroughly
- [ ] Document the issue and fix

### Release Process
- [ ] Go to GitHub Actions → "Hotfix Release"
- [ ] Provide clear description of the hotfix
- [ ] Specify target branch
- [ ] Run workflow and monitor completion
- [ ] Verify hotfix release was created

### Verification
- [ ] Hotfix version incremented correctly
- [ ] Docker image built and pushed
- [ ] Release notes include hotfix description
- [ ] Application functions correctly with fix
- [ ] Issue is resolved in deployed version

## Rollback Checklist (If needed)

### Immediate Actions
- [ ] Identify the issue requiring rollback
- [ ] Determine last known good version
- [ ] Stop current deployment if possible

### Rollback Process
- [ ] Pull previous working Docker image
- [ ] Update deployment to use previous version
- [ ] Verify rollback was successful
- [ ] Monitor application for stability

### Follow-up
- [ ] Document the issue that caused rollback
- [ ] Plan fix for the problematic release
- [ ] Communicate rollback to stakeholders
- [ ] Schedule new release with fix

## Communication

### Internal Team
- [ ] Notify team of release start
- [ ] Share release notes with team
- [ ] Communicate any breaking changes
- [ ] Update team on release completion

### Stakeholders
- [ ] Notify stakeholders of major releases
- [ ] Share relevant changes and improvements
- [ ] Provide migration guides if needed
- [ ] Schedule demos for significant features

## Monitoring

### Post-Release Monitoring
- [ ] Monitor application logs for errors
- [ ] Check performance metrics
- [ ] Verify health check status
- [ ] Monitor user feedback/reports

### Metrics to Track
- [ ] Application uptime
- [ ] Response times
- [ ] Error rates
- [ ] Resource usage
- [ ] User activity

## Notes

### Version Format
- Use YYYY.MM.PATCH format (e.g., 2025.01.0)
- Patch releases increment the patch number
- Monthly releases use current year and month

### Release Types
- **Monthly**: Automated on first Monday of month
- **Patch**: Manual trigger for bug fixes
- **Hotfix**: Emergency releases for critical issues
- **Manual**: Custom version releases

### Emergency Contacts
- DevOps Team: [Contact Information]
- Product Owner: [Contact Information]
- Technical Lead: [Contact Information]

# Security Incident Report - API Key Exposure

**Date**: 2025-10-27
**Severity**: CRITICAL
**Status**: Remediation in progress

## Summary

GitHub security scanning detected exposed API keys in the repository's git history. Multiple secrets were committed in `.env.backup` file.

## Exposed Secrets

1. **Google Gemini API Key**: `AIzaSyB-vzt2dYqptDbq9nmFMeJ0anLA8rvO03o`
   - First committed: Multiple commits starting from e144618
   - Risk: Unauthorized access to Gemini AI services, potential quota abuse
   - Action: **REVOKE IMMEDIATELY**

2. **TogetherAI API Key**: `7473e090c596ff2bde0148f5b81e876cdb9b200083c7802762aaec4b3e7a8724`
   - First committed: Same as above
   - Risk: Unauthorized AI model access, financial charges
   - Action: **REVOKE IMMEDIATELY**

3. **QuickBooks Client Secret**: `9f0HwGLBCOCvSqkrzPp89nkohUclAjFo130pHbPu`
   - First committed: Same as above
   - Risk: OAuth application compromise
   - Action: **REGENERATE IMMEDIATELY**

4. **QuickBooks OAuth Tokens**: Access and refresh tokens
   - Risk: Full access to QuickBooks account
   - Action: Tokens auto-expire but re-authenticate immediately

## Root Cause

- `.env.backup` file was tracked in git (not in .gitignore)
- No pre-commit secret scanning was configured
- Developer created backup file with production credentials

## Remediation Steps

### Immediate Actions (DO THESE FIRST!)

#### 1. Revoke Google Gemini API Key
```bash
# Go to: https://aistudio.google.com/app/apikey
# Delete the exposed key: AIzaSyB-vzt2dYqptDbq9nmFMeJ0anLA8rvO03o
# Generate a new key and update .env.local
```

#### 2. Revoke TogetherAI API Key
```bash
# Go to: https://api.together.xyz/settings/api-keys
# Revoke the exposed key: 7473e090...
# Generate a new key and update .env.local
```

#### 3. Re-authenticate QuickBooks
```bash
# Run OAuth flow to get new tokens
uv run python scripts/connect_quickbooks_cli.py
```

### Repository Cleanup

#### 4. Remove secrets from git history
```bash
# Option 1: Using git-filter-repo (RECOMMENDED)
# Install: brew install git-filter-repo (macOS) or pip install git-filter-repo
git filter-repo --path .env.backup --invert-paths --force

# Option 2: Using BFG Repo-Cleaner (ALTERNATIVE)
# Download from: https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --delete-files .env.backup
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# After cleaning:
git push origin --force --all
git push origin --force --tags
```

#### 5. Verify cleanup
```bash
# Search for any remaining secrets
git log --all --full-history -S "AIzaSy" | wc -l  # Should be 0
git log --all --full-history -- .env.backup | wc -l  # Should be 0
```

### Preventive Measures (COMPLETED)

- ✅ Updated `.gitignore` to block all `.env*` files (except `.env.example`)
- ✅ Added `detect-secrets` pre-commit hook
- ✅ Added `detect-private-key` pre-commit hook
- ✅ Created `.secrets.baseline` for legitimate secrets
- ✅ Removed `.env.backup` from git tracking

## Testing Prevention

```bash
# Test that secrets are blocked
echo "GEMINI_API_KEY=AIzaSyTest123" > test.env
git add test.env  # Should be blocked by pre-commit
rm test.env

# Test that .gitignore works
git status  # .env.local should not appear
```

## Post-Incident Actions

1. ✅ Audit all files for hardcoded secrets
2. ⏳ Clean git history to remove all traces of secrets
3. ⏳ Rotate ALL API keys and secrets
4. ⏳ Monitor API usage for unauthorized access
5. ⏳ Force-push cleaned history to GitHub
6. ⏳ Notify team members to re-clone repository

## Lessons Learned

1. **Never commit `.env` files or backups** - Use `.env.example` with placeholders only
2. **Always use pre-commit hooks** - Catch secrets before they reach git
3. **Regular security audits** - Use tools like `trufflehog`, `gitleaks`, or `detect-secrets`
4. **Separate secrets management** - Consider using secret managers (AWS Secrets Manager, HashiCorp Vault)

## Timeline

- **2025-10-27 14:22**: Secrets first committed in e144618
- **2025-10-27 [TIME]**: GitHub security alert received
- **2025-10-27 [TIME]**: Investigation completed
- **2025-10-27 [TIME]**: Preventive measures implemented
- **Pending**: Key rotation
- **Pending**: Git history cleanup
- **Pending**: Force push to remote

## References

- GitHub Secret Scanning: https://docs.github.com/en/code-security/secret-scanning
- git-filter-repo: https://github.com/newren/git-filter-repo
- BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
- detect-secrets: https://github.com/Yelp/detect-secrets

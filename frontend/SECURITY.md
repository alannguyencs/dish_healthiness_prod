# Security Notes

## NPM Vulnerabilities

### Status: Acceptable for Development

**Vulnerabilities Fixed:**
- ✅ Eliminated all 6 **high severity** vulnerabilities
- ✅ Fixed 5 of 9 total vulnerabilities

**Remaining (4 moderate):**
```
postcss <8.4.31 (in resolve-url-loader)
webpack-dev-server <=5.2.0 (2 issues)
```

### Why These Are Acceptable

1. **Development-only**: These packages are only used during development, not in production builds
2. **Deep dependencies**: They are nested dependencies of `react-scripts` 5.0.1
3. **Attack scenarios**: Require specific conditions:
   - Developer must be running dev server
   - Developer must visit a malicious website
   - Only affects source code on developer's machine

### What We Did

Added dependency overrides in `package.json`:
```json
"overrides": {
  "nth-check": "^2.1.1",
  "svgo": "^3.0.2"
}
```

Updated postcss to latest:
```json
"devDependencies": {
  "postcss": "^8.4.31"
}
```

### Future Mitigation

When react-scripts releases a new version with updated dependencies, run:
```bash
npm update react-scripts
npm audit
```

Or consider migrating to:
- Vite (modern, faster alternative)
- Create React App with newer react-scripts
- Next.js (if server-side rendering is needed)

### Production Security

✅ Production builds are **not affected** by these vulnerabilities
✅ All high-severity issues have been resolved
✅ Development environment follows security best practices

---

**Last Updated:** 2025-11-06
**Audit Status:** 4 moderate (down from 9 total)


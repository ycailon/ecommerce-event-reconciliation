# Publish this demo to a new public GitHub repository

**Suggested repository name:** `ecommerce-event-reconciliation`

1. On GitHub, create a new **public, empty** repository with the suggested name under `ycailon`. Do **not** initialize with a README, .gitignore or license; this package includes its own README and .gitignore.
2. Extract the provided ZIP file, then open PowerShell in the extracted project root (where `README.md` lives).
3. Run:

```powershell
git init -b main
git add .
git commit -m "Add synthetic ecommerce reconciliation portfolio demo"
git remote add origin https://github.com/ycailon/ecommerce-event-reconciliation.git
git push -u origin main
```

4. Verify the visible README and `tests/` folder, then update the tailored resume's portfolio reference if desired.

**Alternatively:** after you create the empty repository, tell ChatGPT its exact `owner/repo` name. The connected GitHub tool can add files to existing repositories.

**Before first deployment:** read `docs/security-and-deployment.md`. This is intentionally not a deployable production Shopify/GCP application.

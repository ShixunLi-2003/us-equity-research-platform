# Publication and review

1. Read the English README and scope/provenance notes. Confirm that the repository describes your contribution accurately.
2. Run the source build, tests and demo in a clean environment. GitHub CI must pass after upload.
3. Select a license after checking source ownership. No license is silently applied here.
4. Create an empty GitHub repository and add its URL as the local remote. Push source only; ignore generated artifacts and vendor data.
5. Put the repository link in the CV with two or three specific engineering/research contributions. Do not use synthetic returns as an investment track record.

Example Git commands, after replacing the remote URL with your own repository:

```bash
git add .
git diff --cached --stat
git commit -m "Publish research and execution engineering portfolio"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

`python scripts/package_release.py` generates a source-only ZIP with SHA256 hashes for each included file. The ZIP is a distribution convenience, not the way to populate the Git repository: use the uncompressed source tree for reviewable history.

The next research release should migrate licensed data adapters, model suite configurations and verifiable historical experiment manifests. The present release provides the complete offline demo and extracted accounting components, not all archived research scripts.

# 🚀 Project Loot Raiders - Daily Development Workflow

This guide documents the standard workflow for developing, testing, and maintaining **Project Loot Raiders**.

---

# 📁 Project Location

```text
C:\Users\yoges\Desktop\Project Loot Raiders
```

---

# 🌅 Start Your Day

## 1. Open PowerShell

Navigate to your project folder.

```powershell
cd "C:\Users\yoges\Desktop\Project Loot Raiders"
```

---

## 2. Get the Latest Changes

Always pull the latest version before starting work.

```powershell
git pull
```

If you see:

```text
Already up to date.
```

continue with development.

---

## 3. Start Antigravity AI

```powershell
agy
```

Example prompts:

- Review the project and suggest improvements.
- Find bugs in the code.
- Improve scraping performance.
- Refactor the scraper.
- Add logging and error handling.
- Explain the project architecture.

---

# 💻 Development

Work on your code:

- Add new features
- Fix bugs
- Improve scraping logic
- Update selectors
- Improve dashboard
- Optimize performance

---

# 🧪 Test the Project

Run the scraper.

```powershell
python loot_scraper.py
```

Verify:

- No errors
- Scraper completes successfully
- Dashboard updates correctly
- JSON files update as expected

---

# 🔍 Review Changes

Check what changed.

```powershell
git status
```

Review the output before committing.

---

# ➕ Stage Changes

```powershell
git add .
```

---

# 💾 Commit Your Work

Use clear, meaningful commit messages.

Examples:

```powershell
git commit -m "Improve scraping performance"
```

```powershell
git commit -m "Add Flipkart selector support"
```

```powershell
git commit -m "Fix dashboard rendering bug"
```

```powershell
git commit -m "Improve error handling"
```

Avoid generic messages such as:

- Update
- Fix
- Changes

---

# ☁️ Push to GitHub

```powershell
git push
```

Confirm the push completes successfully.

---

# 🌙 End-of-Day Checklist

- Code tested
- No runtime errors
- README updated (if needed)
- Documentation updated
- Commit created
- Changes pushed to GitHub

---

# 📅 Weekly Maintenance

Update dependencies if required.

```powershell
pip freeze > requirements.txt
```

If the file changed:

```powershell
git add requirements.txt
git commit -m "Update project dependencies"
git push
```

---

# 🤖 Useful Antigravity Prompts

## Code Review

```
Review the entire project and suggest improvements.
```

## Bug Finding

```
Find bugs and explain how to fix them.
```

## Performance

```
Optimize this project for better performance.
```

## Refactoring

```
Refactor the project following Python best practices.
```

## Documentation

```
Generate documentation for this project.
```

## Security

```
Review the project for security issues and suggest improvements.
```

---

# 📚 Git Cheat Sheet

## Check Status

```powershell
git status
```

## Pull Latest Changes

```powershell
git pull
```

## Stage All Files

```powershell
git add .
```

## Commit

```powershell
git commit -m "Describe your changes"
```

## Push

```powershell
git push
```

## View Commit History

```powershell
git log --oneline
```

---

# 🚫 Never Commit

Do NOT upload:

- API Keys
- Passwords
- Session Tokens
- Cookies
- `.env`
- Virtual environments (`venv/`)
- `__pycache__/`
- Temporary files
- Log files
- Personal credentials

---

# 🚀 Release Workflow

When the project reaches a stable milestone:

1. Test everything.
2. Update the README if necessary.
3. Commit all changes.
4. Push to GitHub.
5. Create a GitHub Release.

Example:

```text
v1.0.0
```

---

# 🎯 Project Goal

Build a reliable, scalable, and maintainable Python-based deal discovery platform capable of automatically collecting, organizing, and tracking online deals and promotional offers.

---

# ✅ Daily Workflow Summary

```text
Open PowerShell
        │
        ▼
cd "C:\Users\yoges\Desktop\Project Loot Raiders"
        │
        ▼
git pull
        │
        ▼
agy
        │
        ▼
Develop & Test
        │
        ▼
git status
        │
        ▼
git add .
        │
        ▼
git commit -m "Meaningful message"
        │
        ▼
git push
        │
        ▼
Done ✔
```
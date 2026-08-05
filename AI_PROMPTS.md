# 🤖 AI Prompt Library
## Project Loot Raiders

This file contains reusable prompts for AI coding assistants such as Antigravity, ChatGPT, Claude, and Gemini.

---

# 📌 General Rules

Before making any code changes:

- Understand the entire project.
- Preserve existing functionality.
- Follow Python best practices.
- Write clean, maintainable code.
- Add comments where helpful.
- Explain important changes.

---

# 🔍 Understand the Project

```
Review the entire Project Loot Raiders codebase.

Explain:

- Project architecture
- Folder structure
- Data flow
- Scraping process
- Dashboard workflow
- Possible improvements

Do not modify any files.
```

---

# 🐞 Find Bugs

```
Review the project for:

- Bugs
- Logic errors
- Runtime errors
- Exception handling
- Race conditions
- Missing validations

Explain each issue and provide fixes.
```

---

# ⚡ Performance Optimization

```
Optimize the scraper for:

- Faster execution
- Lower memory usage
- Better network efficiency
- Cleaner code

Maintain existing functionality.
```

---

# 🔐 Security Review

```
Review the project for security issues.

Check for:

- Hardcoded secrets
- API keys
- Passwords
- Session tokens
- Unsafe file handling
- Injection risks

Suggest improvements.
```

---

# 🧹 Refactoring

```
Refactor the project following Python best practices.

Improve:

- Readability
- Maintainability
- Modularity
- Error handling

Do not change functionality.
```

---

# 📚 Documentation

```
Generate documentation for:

- Every function
- Every class
- Configuration
- Project workflow

Use clear Markdown formatting.
```

---

# 🧪 Testing

```
Create unit tests for the project.

Test:

- Main scraper
- Dashboard
- Utilities
- Error handling

Use pytest.
```

---

# 🚀 Add New Feature

```
Add the following feature:

[Describe the feature]

Requirements:

- Clean code
- Maintain existing functionality
- Add documentation
- Update README if needed
```

---

# 🔧 Fix a Specific Problem

```
Analyze the following issue:

[Describe the problem]

Find the root cause.

Explain why it happens.

Implement the safest fix.
```

---

# 📈 Code Review

```
Act as a Senior Python Software Engineer.

Review the project.

Provide:

- Code quality score
- Security score
- Performance score
- Maintainability score

List improvements in priority order.
```

---

# 📦 Release Preparation

```
Prepare the project for release.

Verify:

- Documentation
- README
- requirements.txt
- .gitignore
- License
- Project structure

Suggest anything missing.
```

---

# 💡 Brainstorming

```
Suggest 20 new features that would make Project Loot Raiders more useful.

Rank them by:

- Impact
- Difficulty
- User value
```

---

# 🛠️ Git Workflow

```
Before every commit:

Review all modified files.

Summarize the changes.

Suggest an appropriate Git commit message.
```

---

# ⭐ Best Prompt

```
Act as a Senior Python Architect.

Understand the complete project before making any changes.

Never remove existing functionality unless requested.

Use modern Python best practices.

Write clean, maintainable code.

Improve performance where possible.

Add documentation.

Explain every important decision.

When finished:

1. Summarize the changes.
2. Explain why they improve the project.
3. Suggest the next logical improvements.
```

---

# 🛡️ Core AI Parsing & Quality Firewall Engine Prompt

```
ROLE & TASK:
Core AI Parsing & Quality Firewall Engine for "Project Loot Raiders."
Mission: Extract structured deal data from raw scraped e-commerce HTML/text, sanitize output, and generate conversion-optimized Telegram posts.

CONTEXT & SKILL RULES:
1. DEEP PARSING: Identify title, original price, deal price, discount %, buy link, high-res image URL.
2. SANITIZATION: Filter out UI elements, ads, navigation, junk text.
3. LOGO PREVENT: NEVER use generic site logos, icon SVGs, banner placeholders, or "image not found" assets.
4. PRICE VALIDATION: Valid deal MUST have price > 0.

QUALITY FIREWALL:
- IF current_price <= 0 -> REJECT ("INVALID_PRICE")
- IF image_url missing/logo/placeholder -> REJECT ("INVALID_IMAGE")
- IF title generic ("Home", "404") -> REJECT ("INVALID_TITLE")

REQUIRED JSON SCHEMA:
{
  "is_valid": true | false,
  "rejection_reason": null | "INVALID_PRICE" | "INVALID_IMAGE" | "INVALID_TITLE" | "DUPLICATE_OR_JUNK",
  "data": {
    "title": "Clean Product Title String",
    "current_price": 499,
    "original_price": 1299,
    "discount_percentage": 61,
    "image_url": "https://example.com/valid-product-image.jpg",
    "buy_url": "https://example.com/affiliate-link"
  },
  "telegram_post": "Formatted markdown text ready to broadcast..."
}
```
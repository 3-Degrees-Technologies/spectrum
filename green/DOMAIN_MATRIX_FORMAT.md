# Domain Matrix Format

## Purpose
Domain matrices help Lieutenant Green detect when tickets mix multiple business or technical domains, which often indicates tickets need breakdown. These matrices are living documents that accumulate project knowledge over time.

## File Structure
```
BUSINESS_DOMAINS.md  - Business capability areas
TECHNICAL_DOMAINS.md - Technical implementation areas
```

## Matrix Format

Each domain matrix follows this structure:

```markdown
# [Project] - [Type] Domain Matrix
*Last Updated: [Date] | Version: [X.Y]*

## Domain List
[Brief overview paragraph]

### [Domain Name]
**Keywords:** keyword1, keyword2, keyword3
**Description:** Brief domain description
**Boundaries:** What this domain includes/excludes
**Common Tasks:** 
- Task type 1
- Task type 2
**Cross-Domain Indicators:**
- Signals that suggest mixing with other domains

---

[Repeat for each domain]
```

## Usage Rules

### For Validation Scripts
1. **Load both matrices** before analyzing tickets
2. **Count domain matches** - keywords found in title/description
3. **Flag multi-domain tickets** - 2+ business domains OR 3+ technical domains
4. **Provide specific feedback** - which domains were detected

### For Lieutenant Green
1. **Update matrices** when new domains emerge
2. **Refine keywords** based on ticket patterns
3. **Track evolution** via version numbers
4. **Cross-project learning** - patterns that apply to multiple projects

## Cross-Domain Detection Examples

### Bad: Multiple Business Domains
```
Title: "User authentication system plus music discovery and playlist management"
Domains: Authentication + File Discovery + Music Library
Result: BREAKDOWN NEEDED - 3 business domains
```

### OK: Multiple Technical Domains (if same business domain)
```
Title: "Authentication UI with API client and token storage"
Business: Authentication (1 domain)
Technical: Android UI + API Client + Storage (3 domains, but cohesive)
Result: ACCEPTABLE - single business workflow
```

### Bad: Mixed Business Context
```
Title: "Update balance events and add to quotes plus routing logic"
Domains: Account Management + Trading + Message Routing
Result: BREAKDOWN NEEDED - different business contexts
```

## Evolution Guidelines

- **Add domains** when patterns emerge across multiple tickets
- **Split domains** when they become too broad (5+ common tasks)
- **Merge domains** when distinction becomes unclear
- **Update keywords** based on validation feedback

---

*This format supports Lieutenant Green's adaptive domain detection system*
# Good Ticket Example: CEN-200 Analysis

## Why CEN-200 is Now a Good Ticket

### 1. **Single, Clear Purpose**
- **Before**: Design domain model AND implement Wise integration AND write tests
- **After**: Design domain model architecture only
- **Why this matters**: Team can focus on one type of work without context switching between design and implementation mindsets

### 2. **Appropriate Scope for Ticket Type**
- **Design tickets should produce**: Documentation, specifications, architectural decisions
- **Implementation tickets should produce**: Working code, tests, deployable features
- **CEN-200 now produces**: Architecture docs, API analysis, integration patterns
- **Why this matters**: Clear success criteria that match the work type

### 3. **Concrete, Measurable Deliverables**
- **Specific documents**: `quote-request-domain.md`, `provider-api-analysis.md`, `domain-model-specs.md`
- **Checkable criteria**: "All three provider APIs researched and documented"
- **Clear definition of done**: Ready for implementation in follow-up ticket
- **Why this matters**: No ambiguity about when the ticket is complete

### 4. **Proper Dependency Management**
- **Blocks implementation work**: Can't code without knowing what to build
- **Enables parallel work**: Multiple implementation tickets can start once design is done
- **Reduces rework**: Design decisions made before expensive implementation
- **Why this matters**: Optimal team velocity and reduced waste

### 5. **Right-Sized Complexity**
- **Substantial enough**: Researching 3 provider APIs is meaningful work
- **Not overwhelming**: Focused on design only, not trying to solve everything
- **Estimable**: Team can predict effort for research and documentation work
- **Why this matters**: Fits in sprint planning and team capacity

### 6. **Clear Context and Rationale**
- **Business value**: "provider-agnostic but informed by all three FX provider APIs"
- **Technical reasoning**: Why we need this architecture foundation
- **Next steps**: Explicitly connects to follow-up implementation work
- **Why this matters**: Team understands the "why" not just the "what"

### 7. **Enables Informed Decision Making**
- **Research before commitment**: Understand all provider APIs before choosing architecture
- **Stakeholder review**: Design can be validated before implementation costs
- **Risk reduction**: Architectural mistakes caught early in design phase
- **Why this matters**: Higher quality decisions and reduced technical debt

### 8. **Resource Allocation Alignment**
- **Design skills**: Can assign to architects, senior developers, or domain experts
- **Implementation skills**: Different people can handle the coding phase
- **Parallel work**: Multiple people can implement once design is approved
- **Why this matters**: Optimal use of team skills and availability

## Anti-Patterns We Avoided

### ❌ **The "Everything Ticket"**
- Trying to design, implement, test, and document in one ticket
- Results in scope creep and unclear success criteria

### ❌ **The "Implementation Without Design"**
- Starting to code without understanding the problem space
- Results in rework when architectural issues are discovered

### ❌ **The "Vague Deliverable"**
- "Implement quote system" without specific requirements
- Results in interpretation differences and scope expansion

### ❌ **The "Wrong Granularity"**
- Either too small (trivial tasks) or too large (epic-sized work)
- Results in poor sprint planning and velocity tracking

## Template for Good Design Tickets

```markdown
**User Story**
As a [user type], I want [capability] so that [business value].

**Acceptance Criteria - DESIGN PHASE**
This story focuses on **designing** the [component/system] architecture for [purpose].

**1. Research & Analysis**
- Analyze [external systems/APIs/requirements]
- Document [key findings/constraints]
- Identify [design requirements/considerations]

**2. Architecture Design**
- Design [core components/patterns]
- Define [interfaces/contracts]
- Specify [relationships/dependencies]

**3. [Domain-Specific Section]**
- [Relevant technical considerations]
- [Integration patterns/strategies]
- [Performance/scalability requirements]

**4. Validation & Business Rules**
- [Business logic specifications]
- [Validation requirements]
- [Error handling strategies]

**5. Deliverables**
- **[Document Type]** (`path/to/doc.md`): [Specific content]
- **[Document Type]** (`path/to/doc.md`): [Specific content]
- **[Document Type]** (`path/to/doc.md`): [Specific content]

**Definition of Done**
- [ ] [Specific, checkable criteria]
- [ ] [Specific, checkable criteria]
- [ ] Ready for implementation in follow-up ticket

**Next Steps**
This design work enables [specific follow-up tickets] with clear specifications.
```

## Key Success Metrics for Design Tickets

1. **Documentation Quality**: Can implementation team start work without additional clarification?
2. **Decision Clarity**: Are architectural choices documented with rationale?
3. **Implementation Readiness**: Are specs detailed enough to estimate implementation effort?
4. **Stakeholder Alignment**: Do business and technical stakeholders agree on approach?
5. **Risk Mitigation**: Have major technical risks been identified and addressed?

## When to Use This Pattern

### ✅ **Good for Design Tickets:**
- New system architecture
- Complex integrations with multiple providers
- Domain modeling for unfamiliar business areas
- Performance-critical system design
- Security-sensitive implementations

### ❌ **Not needed for:**
- Simple CRUD operations
- Well-understood patterns
- Small bug fixes
- Straightforward feature additions
- Maintenance tasks

---

**Use CEN-200 as the gold standard for design tickets moving forward.**
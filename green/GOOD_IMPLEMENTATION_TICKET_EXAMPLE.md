# Good Implementation Ticket Example

## Example: Well-Structured Implementation Ticket

**Title:** Implement JWT Token Validation Middleware

**Description:**
Create middleware function that validates JWT tokens for API authentication.

## Objective

Implement Express.js middleware that validates JWT tokens in the Authorization header, handles token expiration and invalid signatures, and provides appropriate error responses for protected routes.

## Technical Requirements

**Core Functionality:**
- Extract JWT token from Authorization header (Bearer format)
- Validate token signature using configured secret key
- Check token expiration timestamp
- Decode user information from valid tokens
- Attach user data to request object for downstream handlers

**Error Handling:**
- Return 401 for missing or malformed tokens
- Return 401 for expired tokens  
- Return 401 for invalid signatures
- Return 500 for configuration errors
- Provide descriptive error messages in response

**Integration Points:**
- Integrate with existing Express.js application structure
- Use existing JWT configuration from environment variables
- Follow established error response format patterns

## Definition of Done

- [ ] Middleware function validates JWT tokens correctly
- [ ] All error scenarios return appropriate HTTP status codes and messages
- [ ] Valid tokens result in user data attached to request object
- [ ] Unit tests cover all validation scenarios (valid, expired, invalid, missing tokens)
- [ ] Integration with existing auth configuration works correctly
- [ ] Code follows team's TypeScript and Express.js conventions
- [ ] Documentation updated for middleware usage

## Dependencies

- Existing JWT configuration setup
- Express.js framework already configured
- Authentication service provides JWT tokens

---

## What Makes This Implementation Ticket Good

### ✅ Single Task Focus
- **One clear objective**: Implement JWT validation middleware
- **Single technical context**: Express.js middleware development
- **One-sentence summary**: "Create middleware that validates JWT tokens"

### ✅ Implementation-Ready
- **Implementation phase ticket**: No design work mixed in
- **Specific technical details**: JWT validation, error handling, integration points
- **Clear scope boundaries**: Just the middleware, not the broader auth system
- **Ready to code**: Developer can start immediately with clear requirements

### ✅ Clean Format
- **No external references**: No CENTRO-XXX or other non-Linear IDs
- **No priority in text**: Priority would be set in Linear field
- **No story points**: Estimation not in description
- **Clear structure**: Objective → Requirements → Definition of Done

### ✅ Proper Definition of Done
- **Specific and testable**: Each item can be verified
- **Implementation-focused**: Code, tests, documentation
- **No generic metrics**: No "response time <100ms" without context
- **Complete scope**: Covers all aspects of the deliverable work

### ✅ Context Without Complexity
- **Sufficient detail**: Developer knows exactly what to build
- **Clear dependencies**: What needs to exist first
- **Integration guidance**: How it fits with existing system
- **No over-specification**: Doesn't dictate exact implementation approach

### ✅ Validation Against Quality Rules

This ticket passes all validation tests:

**Content Task Analysis**: ✅ 1 main task (implement JWT middleware)
**One-Sentence Test**: ✅ "Create JWT validation middleware"  
**Context Switching Detection**: ✅ Single context (Express.js middleware)
**Phase Mixing Check**: ✅ Pure implementation, no design phase work

## Comparison: Good vs Bad Implementation Tickets

### ✅ Good Implementation Ticket (This Example)
```
Title: Implement JWT Token Validation Middleware
Content: Single middleware function with clear requirements
Focus: Pure implementation work ready to code
```

### ❌ Bad Implementation Ticket  
```
Title: Design and Implement Authentication System
Content: Research auth patterns, design architecture, build login/logout/middleware/database
Focus: Multiple phases and components mixed together
```

## When to Use This Pattern

### ✅ **Good for Implementation Tickets:**
- Single component or function
- Clear technical requirements already defined
- Specific coding task with known scope
- Building on existing architecture/design
- Well-understood integration points

### ❌ **Should be Design Tickets Instead:**
- New system architecture needed
- Multiple components to coordinate
- Unknown technical approaches
- Research required before coding
- Cross-system integration design

---

**Use this as the gold standard for implementation tickets moving forward.**
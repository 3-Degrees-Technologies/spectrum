# Bad Ticket Example - How NOT to Write Tickets

## Example: Poorly Structured Ticket (VIOLATES ALL RULES)

**Task ID:** AUTH-SYSTEM-001  
**Priority:** Critical  
**Story Points:** 21  
**Sprint:** 3-4  
**Epic:** USER-AUTH-EPIC-001

**Title:** Design and Implement Complete Authentication System with JWT, Database, API, and Frontend Integration

**Description:**

## Overview

We need to research, design, and implement a complete authentication system for our application. This should include user management, JWT tokens, password security, API protection, database design, and frontend integration.

## Requirements (Multiple Phases Mixed Together)

**Research Phase:**

- Research industry best practices for authentication
- Analyze competitor authentication flows
- Study JWT vs session-based authentication
- Investigate OAuth2 and SAML integration options

**Database Design Phase:**

- Design user table schema with proper indexing
- Create role-based permission system
- Design audit logging for security events
- Plan data migration strategy from current system

**Backend Implementation Phase:**

- Build user registration and login endpoints
- Implement JWT token generation and validation middleware
- Create password hashing and salting service
- Build email verification system
- Implement password reset functionality
- Add rate limiting for auth endpoints
- Create admin user management API
- Build role-based access control system

**Frontend Implementation Phase:**

- Design login and registration UI components  
- Implement authentication state management
- Create protected route navigation
- Build user profile management interface
- Add password strength validation
- Implement remember me functionality

**Security Implementation:**

- Add CSRF protection
- Implement secure session management
- Add brute force attack prevention
- Create security audit logging
- Implement account lockout policies

**Testing Phase:**

- Unit tests for all authentication logic
- Integration tests for API endpoints
- Security penetration testing
- Load testing for authentication flow
- Browser compatibility testing for frontend

**DevOps/Infrastructure:**

- Set up authentication in staging environment
- Configure production security settings  
- Create monitoring dashboards for auth metrics
- Set up alerting for security events
- Document deployment procedures

## Success Metrics (Generic and Meaningless)

- System response time <200ms for all auth operations
- 99.9% uptime for authentication services
- Zero successful brute force attacks
- User satisfaction score >4.5/5
- Code coverage >90% for auth modules
- Page load time <3 seconds for login flow

## Acceptance Criteria (Mixing Everything Together)

- [ ] All authentication research completed with recommendations document
- [ ] Database schema designed and implemented with migrations
- [ ] User registration API endpoint working with validation
- [ ] User login API endpoint with JWT token generation
- [ ] Password reset functionality via email working end-to-end
- [ ] JWT middleware protecting all secured routes
- [ ] Frontend login/registration forms with proper UX
- [ ] Role-based permissions working across frontend and backend
- [ ] Security audit logging implemented and tested
- [ ] All unit and integration tests passing
- [ ] Production deployment completed successfully
- [ ] Performance benchmarks meeting all success metrics
- [ ] Security penetration testing passed
- [ ] Documentation complete for all components

## Technical Implementation Details (Too Much Detail)

**JWT Token Structure:**

```json
{
  "user_id": "uuid",
  "email": "user@example.com", 
  "roles": ["admin", "user"],
  "permissions": ["read", "write", "delete"],
  "exp": 1234567890,
  "iat": 1234567890,
  "iss": "our-app"
}
```

**Database Schema:**

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  salt VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  last_login TIMESTAMP,
  failed_login_attempts INTEGER DEFAULT 0,
  account_locked_until TIMESTAMP,
  email_verified BOOLEAN DEFAULT FALSE,
  email_verification_token VARCHAR(255)
);
```

**API Endpoints to Build:**

- POST /auth/register
- POST /auth/login  
- POST /auth/logout
- POST /auth/refresh-token
- POST /auth/forgot-password
- POST /auth/reset-password
- GET /auth/verify-email/:token
- GET /auth/me
- PUT /auth/change-password
- DELETE /auth/delete-account

## Dependencies (Unclear and Mixed)

**Upstream:**

- REQ-001: User requirements gathering must be complete
- ARCH-002: System architecture design approved
- DB-003: Database infrastructure provisioned
- SEC-004: Security review process established

**Downstream:**

- PAYMENTS-001: Payment system needs user authentication
- NOTIFICATIONS-002: Email service needs user management
- ADMIN-003: Admin dashboard needs role-based access

## Risk Assessment

**High Priority Risks:**

- Authentication system complexity may cause delays across multiple teams
- Security vulnerabilities could expose user data
- Performance issues may impact entire application
- Integration complexity with existing systems unknown

## Definition of Done (Impossible to Validate)

### Technical Completion

- [ ] Complete authentication system researched, designed, and implemented
- [ ] All components working together seamlessly  
- [ ] Security best practices implemented throughout
- [ ] Performance targets achieved across all components
- [ ] Integration with existing systems complete and tested

### Quality Assurance

- [ ] Comprehensive testing completed for all components
- [ ] Security audit passed with no critical findings
- [ ] Performance testing validates all success metrics
- [ ] User acceptance testing completed successfully
- [ ] Code review approved by security team

### Documentation & Operations

- [ ] Technical documentation complete for all systems
- [ ] Operational procedures documented and tested
- [ ] Team training completed for new authentication system
- [ ] Monitoring and alerting configured and validated
- [ ] Rollback procedures tested and documented

**Estimated Duration:** 8-12 weeks  
**Team Required:** 2-3 full-stack developers, 1 security specialist, 1 DevOps engineer, 1 QA engineer

---

## Everything Wrong With This Ticket

### ❌ **Language-Induced Agent Misdirection**

**Critical Discovery:** Ticket language directly shapes agent behavior and can lead agents down wrong paths.

**❌ Implementation-Focused Language in Design Phase:**

- "Design detailed Centro.Lambda.Projections architecture" → "detailed" pushed toward implementation
- "Architect ProjectionLambdaFunction entry point" → prescribes specific class names
- **Result:** Agent wrote implementation code instead of functional design

✅ **Better Design Language:** "Design how Lambda projections integrate with existing Centro event sourcing"

**❌ Prescriptive Technical Details:**

- "ProjectionRouter.cs directing events" → dictates implementation structure  
- Should ask "How should events be routed?" not "Design ProjectionRouter.cs"
- **Result:** Agent focused on technical structure, not functional requirements

**❌ Performance/NFR Targets in Discovery Phase:**

- "Achieve 450KB package size, 400ms cold starts" → premature optimization in greenfield project
- **CRITICAL FLAW:** Setting performance limits in discovery phase without measurement methodology
- **Problem:** We have no baseline, no measurement tools, no performance requirements gathered
- **Result:** Agent optimized prematurely instead of exploring functional requirements
- **Fix:** Performance constraints belong in **optimization phases** after core functionality is proven

✅ **Proper Phase Sequencing:**

- **Discovery/Design Phase:** Focus on "what it does" and "how it integrates"
- **Implementation Phase:** Focus on "how to build it" with functional correctness
- **Optimization Phase:** Focus on "how fast/small it needs to be" with measurement methodology

**Key Learning:** Design tickets should ask **functional questions** and explore **integration patterns**. Performance/NFR constraints should only appear when we have mature projects with measurement capabilities.

### ❌ **Violates Content Task Analysis**

**Task Count:** 25+ distinct tasks spanning multiple phases

- Research (4 tasks)
- Database design (4 tasks)  
- Backend implementation (8 tasks)
- Frontend implementation (6 tasks)
- Security (5 tasks)
- Testing (5 tasks)
- DevOps (5 tasks)

### ❌ **Fails One-Sentence Test**

**Cannot summarize in one sentence** - it's doing everything related to authentication

### ❌ **Multiple Context Switching**

**7 different technical contexts:**

- Research and analysis
- Database design
- Backend API development
- Frontend UI development
- Security implementation
- Testing frameworks
- DevOps/Infrastructure

### ❌ **Phase Mixing Violation**

**Combines all phases:** Research + Design + Implementation + Testing + Deployment

### ❌ **External Reference Numbers**

- AUTH-SYSTEM-001
- USER-AUTH-EPIC-001  
- REQ-001, ARCH-002, DB-003, SEC-004

### ❌ **Priority in Text**

- "Priority: Critical" in description instead of Linear field

### ❌ **Story Points in Text**

- "Story Points: 21" in description instead of Linear field

### ❌ **Generic Success Metrics**

- Meaningless metrics like "99.9% uptime" and "user satisfaction >4.5/5"
- No specific, actionable criteria

### ❌ **Impossible Definition of Done**

- Vague criteria like "all components working seamlessly"
- Cannot objectively verify completion
- Mixing different types of work

### ❌ **Overwhelming Scope**

- 8-12 week timeline for single ticket
- Requires entire team of specialists
- Epic-sized work disguised as single ticket

## How This Should Be Fixed

**This massive ticket should be broken down into:**

1. **Epic Ticket:** Authentication System Implementation (overview only)
2. **Research Ticket:** Authentication Architecture Research  
3. **Design Ticket:** User Management Database Schema Design
4. **Implementation Ticket:** JWT Token Validation Middleware
5. **Implementation Ticket:** User Registration API Endpoint
6. **Implementation Ticket:** Login/Logout API Endpoints
7. **Implementation Ticket:** Password Reset Flow
8. **Implementation Ticket:** Frontend Login Components
9. **Implementation Ticket:** Role-Based Access Control
10. **Testing Ticket:** Authentication Security Testing

**Each subtask would be:**

- Single phase (research OR design OR implementation)
- Single technical context
- 1-2 week timeframe
- Clear, testable definition of done
- One main task focus

---

**Never create tickets like this example. Use GOOD_IMPLEMENTATION_TICKET_EXAMPLE.md as the standard instead.**



### The Language Problem

Agent-Sam delivered **implementation planning** instead of **functional design** because the ticket used implementation-focused language throughout.

### Specific Language Issues Identified:

**❌ Bad Design Language:**

- "Design detailed Centro.Lambda.Projections architecture" 
- "Architect ProjectionLambdaFunction entry point and routing logic"
- "Performance Targets: Achieve 450KB package size, 400ms cold starts, 256MB memory"

**✅ Better Design Language:**

- "Design how Lambda projections integrate with existing Centro event sourcing"
- "Define how projection events should be processed and routed"  
- "Define projection processing requirements and constraints"

### Core Insight

**Design Phase** should ask functional questions: "What should this system do and how should it integrate?"
**Implementation Phase** should answer technical questions: "How do we build this and how fast should it run?"

**Agent-Sam's Key Learning:** "Design should focus on 'what it does' not 'how fast it does it'"

This demonstrates that **ticket language shapes agent thinking** - prescriptive technical language leads to premature technical solutions instead of proper functional analysis.
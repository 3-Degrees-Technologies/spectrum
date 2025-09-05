# Good Implementation Ticket Examples

## Example 1: Current pCloud Project - PREFERRED PATTERN

### PLY-48: Username/Password Authentication Flow

**Brief**: Implement direct username/password login to pCloud userinfo endpoint with getauth=1 parameter, handle successful auth token response

**Why This is a GOOD Implementation Ticket:**

#### ✅ Single Domain Focus

- All work is within pCloud authentication domain
- Login + token response handling = single workflow  
- Cohesive functionality that belongs together

#### ✅ Single Feature Workflow

- Step 1: Make API call to pCloud userinfo endpoint
- Step 2: Process auth token from response
- This is ONE authentication flow, not separate tasks

#### ✅ Testing is Process, Not Task

- TDD approach means tests are part of implementation methodology
- "Write tests" is not a separate task - it's how we implement
- Testing is integral to the development process

#### ✅ Error Handling is Domain Responsibility

- Authentication errors belong in authentication domain
- Handling login failures is part of login implementation
- Not a separate concern, but core functionality

#### ✅ Implementable Scope

- Clear API endpoint and parameters specified
- Specific success criteria (auth token handling)
- Single developer can complete in focused session

### Validation False Positives to Ignore

**❌ "Multiple Tasks" - Actually Single Workflow**

- Validator sees "implement login" + "handle response"
- Reality: This is one authentication workflow

**❌ "Frontend+Backend Context" - Actually Network Operation**  

- Client making API call involves networking
- This is standard mobile app functionality, not context mixing

**❌ "Testing Separate Task" - Actually TDD Process**

- Tests are part of implementation approach
- Not additional work, but how work gets done

---

## Example 2: Previous Pattern - STILL VALID

### Implement JWT Token Validation Middleware

**Description:** Create middleware function that validates JWT tokens for API authentication.

**Why This Works:**

- Single middleware component
- Clear technical scope
- Implementation-ready requirements
- Pure implementation phase work

---

## Pattern: Good Implementation Tickets

### ✅ **Characteristics:**

1. **Single domain/feature area** (authentication, playback, file listing, etc.)
2. **Complete workflow** (not partial functionality)  
3. **Clear API/technical scope** (specific endpoints, parameters, responses)
4. **Includes natural responsibilities** (error handling, validation within domain)
5. **TDD methodology** (tests are process, not separate tasks)

### ✅ **What to Include:**

- Domain-specific error handling
- Testing as part of TDD process  
- Integration within same architectural layer
- Natural workflow steps (API call → process response)

### ❌ **What to Avoid:**

- Multiple unrelated domains
- Design + implementation mixing
- Cross-system architecture decisions
- Research or discovery work

---

## When to Override Validation Warnings

### ✅ **Safe to Ignore These Warnings:**

**"Multiple Tasks" when it's actually:**

- Single workflow with natural steps
- Domain functionality + error handling
- API call + response processing
- TDD tests + implementation

**"Frontend+Backend Context" when it's actually:**

- Network operations in mobile apps
- API client functionality
- Standard client-server patterns

**"Testing as Separate Task" when:**

- Following TDD methodology
- Tests are part of development process
- Not additional scope, but approach

### ❌ **Do NOT Ignore These Warnings:**

- Actual multiple unrelated domains
- Design work mixed with implementation
- Research + building in same ticket
- Multiple system components

---

## Use These Examples When:

- Validation warns about "multiple tasks" in single workflow
- Validator flags testing as separate task (ignore - it's TDD)
- Error handling within same domain triggers warnings (ignore)
- Network operations flagged as "frontend+backend" (ignore - standard mobile)
- Need to determine if ticket scope is appropriate

**Remember**: Tickets should represent complete, implementable features within a single domain, not atomic function-level work.
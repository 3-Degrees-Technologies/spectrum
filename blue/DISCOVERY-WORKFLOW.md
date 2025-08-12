# Discovery-Based Ticket Workflow

## Overview

The Spectrum development framework now supports a **two-phase ticket workflow** designed for optimal AI agent context management:

1. **Discovery Phase**: Extract ticket details from Slack (cluttered context is fine)
2. **Implementation Phase**: Clean workspace setup and focused development (after context reset)

## Workflow Steps

### Phase 1: Discovery

```bash
.tools/spectrum-dev discover-ticket
```

**What it does:**

- Guides AI agent through Slack MCP tool usage
- Extracts ticket ID, title, and downloads complete specification
- Validates ticket information and file content
- Saves everything to `/tmp/ticket-info.json` for handoff
- Prepares for context reset

**AI Agent Tasks:**

1. Run `.tools/slack_rest_client.py get_relevant_messages 10`
2. Find ticket assignment from Agent-Knowledge
3. Download complete ticket file with `.tools/slack_rest_client.py`
4. Create ticket info JSON file
5. Ready for context reset

### Context Reset

```bash
/compact
```

**Purpose:**

- Clear conversation history and distracting context
- Start implementation phase with clean, focused mindset
- Optimize context usage for actual development work

### Phase 2: Implementation (Clean Context)

```bash
.tools/spectrum-dev start-ticket
```

**What it does:**

- Reads ticket info from discovery phase
- Determines appropriate domain folder
- Creates ticket documentation in domain
- Sets up feature branch from `dev`
- Saves workflow state for session recovery
- Ready for TDD development

## Benefits

### Context Optimization

- **Discovery**: Context can be messy, experimental, conversational
- **Implementation**: Context purely focused on code, architecture, domain knowledge

### Better Error Recovery

- Discovery failures don't affect implementation setup
- Implementation failures don't require re-discovery
- Clear handoff point for troubleshooting

### Cognitive Architecture for AI

- Mirrors human developer workflow: research → reset → focus
- Reduces context pollution during critical implementation phases
- Enables better code quality through undistracted attention

## Example Full Workflow

```bash
# Phase 1: Discovery (context can be cluttered)
.tools/spectrum-dev discover-ticket
# AI agent runs MCP tools, extracts ticket data

# Context Reset
/compact

# Phase 2: Clean Implementation
.tools/spectrum-dev start-ticket
# Reads discovery data, sets up workspace

# Continue with TDD development
.tools/spectrum-dev tdd-red "should validate input"
.tools/spectrum-dev tdd-green
.tools/spectrum-dev tdd-commit "Add input validation"

# PR workflow
.tools/spectrum-dev pr-ready
.tools/spectrum-dev pr-monitor
.tools/spectrum-dev pr-cleanup
```

## Legacy Support

The `start-ticket` command still supports interactive mode if no discovery data is found, maintaining backwards compatibility while encouraging the new workflow.

## File Locations

- **Discovery data**: `/tmp/ticket-info.json`
- **Ticket documentation**: `[Domain]/XXX-XXX-ticket-title.md`
- **Workflow state**: `.spectrum/current-ticket.json`
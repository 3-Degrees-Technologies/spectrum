# Spectrum Development Framework - State Management Standards

## Overview

This document defines unified standards for state and temporary file management across all Spectrum Development Framework commands.

## State Management Principles

1. **Single source of truth** - All active workflow state in one location
2. **Predictable cleanup** - Clear ownership and lifecycle for each file
3. **Historical preservation** - Important state archived with context
4. **Cross-command compatibility** - All commands use the same file paths/formats

## Directory Structure

```
.spectrum/
├── state/                     # Active workflow state (working directory)
│   ├── current-ticket.json    # Primary ticket workflow state
│   ├── current-tdd-cycle.json # Current TDD cycle state
│   └── discovery-cache.json   # Cached discovery data
├── archive/                   # Historical state (read-only)
│   ├── completed-tickets/     # Completed ticket records
│   ├── tdd-history/          # TDD cycle archives by ticket
│   └── discovery-history/    # Discovery session archives
└── tmp/                      # Ephemeral files (auto-cleanup)
    ├── slack-messages.json   # Temporary Slack data
    ├── build-output.log      # Temporary build logs
    └── api-review-results.md # Temporary quality reports
```

## File Specifications

### Primary State Files

#### `.spectrum/state/current-ticket.json`
**Purpose**: Master record of active ticket workflow
**Lifecycle**: Created by start-ticket, updated by all commands, archived by pr-cleanup
**Format**:
```json
{
  "ticket_id": "CEN-123",
  "ticket_title": "Implement feature X",
  "domain": "Centro.Api",
  "domain_folder": "src/Centro.Api",
  "ticket_doc_path": "src/Centro.Api/CEN-123-implement-feature-x.md",
  "branch": "feature/CEN-123-implement-feature-x",
  "phase": "started|tdd-cycle-N|pr-created|completed",
  "created_at": "2024-09-19T15:45:00Z",
  "pr_url": "https://github.com/.../pull/123",
  "files_changed": 5,
  "test_count": 12,
  "quality_gates_passed": true
}
```

#### `.spectrum/state/current-tdd-cycle.json`
**Purpose**: Track current TDD cycle state
**Lifecycle**: Created by tdd-red, updated by tdd-green/tdd-refactor, archived by tdd-commit
**Format**:
```json
{
  "cycle_number": 3,
  "phase": "red|green|refactor",
  "test_description": "should return balance for valid account",
  "started_at": "2024-09-19T15:45:00Z",
  "confirmed_at": "2024-09-19T15:47:00Z",
  "ticket_id": "CEN-123"
}
```

#### `.spectrum/state/discovery-cache.json`
**Purpose**: Cache Slack discovery data to avoid re-fetching
**Lifecycle**: Created by discover-ticket, updated on new assignments, cleared by start-ticket
**Format**:
```json
{
  "ticket_id": "CEN-123",
  "ticket_title": "Implement feature X",
  "ticket_file": ".spectrum/tmp/discovered-ticket-details.md",
  "ticket_type": "backend|research|architecture",
  "discovered_at": "2024-09-19T15:45:00Z",
  "discovered_by": "Agent-Red",
  "assignment_timestamp": "1695135900"
}
```

### Archive Files

#### `.spectrum/archive/completed-tickets/{ticket-id}-{timestamp}.json`
**Purpose**: Historical record of completed tickets
**Lifecycle**: Created by pr-cleanup, never modified
**Format**: Final state of current-ticket.json plus completion metadata

#### `.spectrum/archive/tdd-history/{ticket-id}/cycle-{N}.json`
**Purpose**: Historical record of each TDD cycle
**Lifecycle**: Created by tdd-commit, never modified

### Temporary Files

#### `.spectrum/tmp/slack-messages.json`
**Purpose**: Raw Slack API responses for processing
**Lifecycle**: Created by discover-ticket, deleted immediately after processing

#### `.spectrum/tmp/discovered-ticket-details.md`
**Purpose**: Downloaded ticket content from Slack
**Lifecycle**: Created by discover-ticket, moved to domain folder by start-ticket

## Migration Plan

### Phase 1: Create Unified Directory Structure
1. Create `.spectrum/state/`, `.spectrum/archive/`, `.spectrum/tmp/`
2. Migrate existing files to new locations
3. Update path constants in all commands

### Phase 2: Standardize File Formats
1. Ensure all state files use consistent JSON schemas
2. Add validation functions for state file formats
3. Add backwards compatibility for existing formats

### Phase 3: Update Commands
1. Update all commands to use new paths
2. Add proper cleanup routines
3. Test cross-command compatibility

### Phase 4: Legacy Cleanup
1. Remove old directories (`.tmp/`, legacy `.spectrum/` structure)
2. Update documentation
3. Add protection against creating files in old locations

## Implementation Notes

- All commands should validate state file format before use
- State files should be human-readable for debugging
- Temporary files must be cleaned up within same command session
- Archive files are read-only and should never be modified
- State transitions should be atomic (use temp files + move)

## Command-Specific Responsibilities

| Command | State Created | State Updated | State Archived |
|---------|---------------|---------------|----------------|
| discover-ticket | discovery-cache.json | - | - |
| start-ticket | current-ticket.json | discovery-cache.json | discovery-cache.json |
| tdd-red | current-tdd-cycle.json | current-ticket.json | - |
| tdd-green | - | current-tdd-cycle.json | - |
| tdd-refactor | - | current-tdd-cycle.json | - |
| tdd-commit | - | current-ticket.json | current-tdd-cycle.json |
| pr-ready | - | current-ticket.json | - |
| pr-cleanup | - | - | current-ticket.json, all state |

## Error Handling

- Commands should gracefully handle missing state files
- Invalid state files should trigger user-friendly error messages
- Partial state should be recovered where possible
- Critical state should be backed up before destructive operations
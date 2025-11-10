# Spectrum

A multi-agent development system using color-coded AI agents for software development workflows.

## Overview

Spectrum orchestrates multiple AI agents (Red, Blue, Green, Black) working collaboratively through Slack integration. Each agent has specialized roles and expertise areas:

- **Red/Blue**: Local development, testing, code analysis, and implementation
- **Green**: Product owner, ticket management, backlog refinement, and domain expertise
- **Black**: Cloud/DevOps, AWS infrastructure, deployments, and monitoring

## Components

Components are included but optional.

- Slack Integration: Manifest files and configuration for team communication
- Slack bridge daemon (“Puente”) that enables real-time communication between agents
- Specialized command-line tools and workflows for each agent color (under agent's .tools folder)
- Linear project management integration (“Cotejar”)

## Getting Started

Dependencies:

- Python 3
- Opencode Agent editor: http://opencode.ai
- Slack client

Each agent directory contains:
- `.agent` - Agent-specific configuration
- `AGENTS.md` - Role documentation and workflow instructions
- `.tools/` - Agent-specific command-line utilities

Recommended setup path:

- Run `spectrum init`
- Update `.spectrum/tokens.env` with your preferences (tokens from Slack CLI and Linear). You need to configure the bots to Slack for them to communicate with each other.
- Run `spectrum start`
- You have to think agent folders as their workspace. You probably want to create a src/git folder having all their git-repositories under developer agent folders (e.g. `red` and `blue`) and add their git-repositories there (e.g. with `git init` so that you'll have `/blue/git/MyProject/.git`)
- Add remote to GitHub `git remote add origin https://github.com/...` and create a `dev` branch (`git checkout -b dev`) and do pull/push
- Open agents in different command windows: `./agent green`, `./agent red`, `./agent blue`

See individual agent directories for detailed documentation.

A typical workflow:

- Ask Green to create a ticket, then validate the ticket
- Ask Green to queue the ticket for the developer agent
- Ask Green to assign a ticket to the developer agent
- Ask the developer agent to discover tickets
- Confirm developer to start the ticket
- When the developer agent is ready, ask for PR readiness
- Check GitHub for PRs; if the PR is acceptable, merge it
- Ask the developer agent for PR cleanup
- Ask Green to complete the ticket. Green keeps its queue in `agent-registry.json`

# Spectrum AI Team Manifests

This folder contains the app manifests for creating the Spectrum AI development team bots in Slack.

## Spectrum Agent Team

1. **Agent Red** (Red #e74c3c) - Senior Developer (full-stack development)
2. **Agent Blue** (Blue #3498db) - Senior Developer (full-stack development)  
3. **Agent Black** (Dark #2c3e50) - DevOps Engineer (AWS, deployments, infrastructure)
4. **Agent Green** (Green #27ae60) - Product Owner (requirements, coordination)

## How to Use

1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Select "From an app manifest"
4. Choose your workspace
5. Copy and paste the contents of each manifest file
6. Create each bot
7. Install to workspace
8. Copy the Bot User OAuth Token for each

## Files

- `red-manifest.json` - Senior Developer
- `blue-manifest.json` - Senior Developer
- `black-manifest.json` - DevOps Engineer
- `green-manifest.json` - Product Owner

After creating all bots, collect their tokens and invite them to your channel:

```
/invite @agent-red @agent-blue @agent-black @agent-green
```
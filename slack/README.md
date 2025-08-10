# Spectrum AI Team Manifests

This folder contains the app manifests for creating the Spectrum AI development team bots in Slack.

## Spectrum Agent Team

1. **Captain Scarlet** (Red #e74c3c) - Senior Developer (full-stack development)
2. **Captain Blue** (Blue #3498db) - Senior Developer (full-stack development)  
3. **Captain Black** (Dark #2c3e50) - DevOps Engineer (AWS, deployments, infrastructure)
4. **Lieutenant Green** (Green #27ae60) - Product Owner (requirements, coordination)

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

- `captain-scarlet-manifest.json` - Senior Developer
- `captain-blue-manifest.json` - Senior Developer
- `captain-black-manifest.json` - DevOps Engineer
- `lieutenant-green-manifest.json` - Product Owner

After creating all bots, collect their tokens and invite them to your channel:
```
/invite @captain-scarlet @captain-blue @captain-black @lieutenant-green
```
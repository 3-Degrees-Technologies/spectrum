# .tools Directory Protection

## Problem

AI agents (particularly red and blue) were accidentally deleting their own `.tools` folders during operations, causing workflow disruptions and requiring manual restoration.

## Solution

**Built-in protection in `cloudbase`** using file permissions (no sudo required):

- **Directories**: `chmod 555` (read + execute, no write)
- **Files**: `chmod 444` (read-only) or `chmod 555` (executable files)
- **Automatic**: Protection is applied every time `./cloudbase` runs

## Tools Protection Manager

Use `./tools-protect` to manage protection:

```bash
# Protect all .tools directories (default)
./tools-protect lock

# Temporarily remove protection for updates  
./tools-protect unlock

# Check current protection status
./tools-protect status

# Show help
./tools-protect help
```

## Protection Status Examples

```
🔍 Checking .tools protection status...
  🔒 red/.tools: Protected
  🔒 blue/.tools: Protected  
  🔒 green/.tools: Protected
```

## When to Unlock

Temporarily unlock when you need to:
- Update agent tools or scripts
- Add new commands to `.tools/commands/`
- Modify Python scripts in `.tools/`

**Important**: Always run `./tools-protect lock` after updates!

## Comparison with Other Methods

| Method | Requires Sudo | Protection Level | Reversible |
|--------|---------------|------------------|------------|
| `chattr +i` | ✅ Yes | Highest | ✅ Yes |
| `chmod 555/444` | ❌ No | High | ✅ Yes |
| Git hooks | ❌ No | Medium | ✅ Yes |

## Technical Details

**Protected locations**:
- `{red,blue,green,black}/.tools/` directories
- `*.py`, `*.md`, `spectrum-dev` files within
- All files in `.tools/commands/` directories

**Permission scheme**:
- Directories: `555` (dr-xr-xr-x) - readable, executable, not writable
- Scripts: `555` (read + execute) for executable files
- Docs: `444` (read-only) for documentation files

**Protection verification**:
```bash
ls -la red/.tools/
# Should show: dr-xr-xr-x (directories), -r--r--r-- (files)
```

This approach provides strong protection against accidental deletion while maintaining usability and not requiring elevated privileges.
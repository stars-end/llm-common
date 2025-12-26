# Agent Mail Token Rotation Procedure

## Context

The Agent Mail bearer token `22ffa18c2db4cec39aa1b711903ebb9b5d2df3dcf951171583b042027bdf3be1` was leaked in conversation prompts and must be rotated.

**Security Principle**: Bearer tokens should ONLY be distributed via:
- 1Password secure notes
- Environment variables (`.env` files NOT committed to git)
- Tailscale taildrop for VM-to-VM transfer

**NEVER** distribute tokens via:
- Git commits
- Pull requests
- Beads issues
- Agent Mail threads
- Chat prompts/logs

## Rotation Steps

### 1. Generate New Token (Coordinator VM)

On the coordinator VM (macmini):

```bash
# Generate new 32-byte hex token
NEW_TOKEN=$(openssl rand -hex 32)
echo "New token: $NEW_TOKEN"
```

### 2. Update Agent Mail Server (Coordinator VM)

```bash
# Update server .env
cd /path/to/agent-mail-server
# Edit .env and replace HTTP_BEARER_TOKEN value
nano .env

# Restart Agent Mail server
# (method depends on how it's running - systemd, docker, etc.)
```

### 3. Distribute New Token Securely

**Option A: 1Password**
1. Create/update secure note "Agent Mail Bearer Token"
2. Add token value
3. Share with team members who need access

**Option B: Tailscale Taildrop** (VM-to-VM)
```bash
# On coordinator VM
echo "$NEW_TOKEN" > agent-mail-token.txt
tailscale file cp agent-mail-token.txt epyc6:
rm agent-mail-token.txt
```

**Option C: Secure Messaging**
- Use encrypted channel (Signal, etc.)
- Delete message after recipient confirms receipt

### 4. Update Client VMs

On each client VM (epyc6, etc.):

```bash
# Update environment variable
echo 'export AGENT_MAIL_BEARER_TOKEN="<new-token-here>"' >> ~/.bashrc
source ~/.bashrc

# Or add to .env file (NOT committed to git)
echo 'AGENT_MAIL_BEARER_TOKEN="<new-token-here>"' >> ~/.env
```

### 5. Verify Connectivity

```bash
# Test with new token
curl -fsS http://macmini:8765/health/liveness \
  -H "Authorization: Bearer $AGENT_MAIL_BEARER_TOKEN"
```

Should return: `{"status":"alive"}`

## Rotation Schedule

- **Quarterly**: Rotate as part of regular security maintenance
- **On suspected leak**: Rotate immediately when token appears in:
  - Git commits
  - Chat logs
  - Public documentation
  - Agent Mail threads

## Post-Rotation Checklist

- [ ] New token generated (32-byte hex)
- [ ] Server `.env` updated
- [ ] Server restarted
- [ ] Token distributed via secure channel (1Password/taildrop)
- [ ] All client VMs updated
- [ ] Connectivity verified on all VMs
- [ ] Old token documented as compromised (date + reason)
- [ ] This document updated with rotation date

## Rotation History

| Date | Reason | Rotated By |
|------|--------|------------|
| 2025-12-12 | Token leaked in conversation prompts | Pending |

---

**Note**: This procedure will be integrated into bd-3871.13 (Agent Mail bootstrap + cross-platform install) implementation.

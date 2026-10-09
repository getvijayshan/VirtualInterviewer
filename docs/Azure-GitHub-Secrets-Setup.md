# Azure + GitHub Secrets Setup (for `deploy-vm.yml`)

Step-by-step setup so the manual workflow **Provision & Deploy Azure VM** (`.github/workflows/deploy-vm.yml`) can run. See ADR §10/§11 for the design.

You need: an Azure subscription where you are **Owner** (or Owner/User Access Admin on the subscription), admin rights on the GitHub repo `getvijayshan/VirtualInterviewer`, and `az` CLI installed locally (https://aka.ms/installazurecliwindows). Commands below are PowerShell/Git Bash friendly unless noted.

---

## Part A — Azure

### A1. Log in and pick the subscription
```bash
az login
az account list --output table
az account set --subscription "<SUBSCRIPTION_ID_OR_NAME>"
az account show --query id --output tsv     # note this: <SUBSCRIPTION_ID>
```

### A2. Register required resource providers (one-time)
```bash
az provider register --namespace Microsoft.Compute
az provider register --namespace Microsoft.Network
az provider register --namespace Microsoft.Storage
```

### A3. Check VM size availability in the region
The workflow defaults to `Standard_D2ls_v6` (2 vCPU, 4 GiB) in `centralindia`. Confirm your subscription can use it:
```bash
az vm list-skus --location centralindia --size Standard_D2ls_v6 --output table
```
If the output shows `NotAvailableForSubscription`, pick another region or size and enter it as a workflow input at run time.

### A4. Create the service principal for GitHub Actions
Assign the Azure RBAC role **Contributor** (not an Entra directory role such as Cloud Application Administrator, and not "App Service Environment Contributor"). Scope it to the resource group:
```bash
az group create -n resource-virtual-interviewer -l centralindia
az ad sp create-for-rbac   --name "gh-actions-candidate-true-companion"   --role Contributor   --scopes /subscriptions/88bf7826-133f-4ad9-8e89-e082c05a7d34/resourceGroups/resource-virtual-interviewer   --sdk-auth
```
Copy the entire JSON output into the `AZURE_CREDENTIALS` secret (shown only once; re-create with `az ad sp credential reset`). If `--sdk-auth` is deprecated, build the JSON by hand: `{"clientId":"<appId>","clientSecret":"<password>","subscriptionId":"<id>","tenantId":"<tenant>"}`.

If you also let the workflow create the AI Foundry resource group (`southindia-ai-models`) or other groups, the principal needs Contributor there too (or at subscription scope). Verify with `az role assignment list --assignee <clientId> --all -o table`.

### A5. Generate the deploy SSH keypair
Use a dedicated key that is not your personal one. No passphrase (CI can't type one).
```bash
ssh-keygen -t ed25519 -f ./ctc-deploy-key -N "" -C "azureuser"
```
This creates `ctc-deploy-key` (private) and `ctc-deploy-key.pub` (public). **Do not commit either file.** Delete both from disk after adding them to GitHub (Part B), or move them to a password manager.

> **Using the portal-generated `.pem` instead:** the private key (`infra/az-resource/vm/*.pem`, gitignored) goes in `VM_SSH_PRIVATE_KEY`. Derive the matching public key for `VM_SSH_PUBLIC_KEY` with `ssh-keygen -y -f <file>.pem`. Move the `.pem` out of the repo folder afterwards.

### A6. Collect the app credentials (already live in `backend/.env` locally)
Open `backend/.env` and copy these values — they are reused as GitHub secrets:

| Value | Where it comes from |
|---|---|
| Storage connection string | Azure Portal → Storage account → Security + networking → **Access keys** → Connection string |
| Storage container | `resume-answer-audio` |
| Azure OpenAI endpoint | `https://vs-virtual-interviewer--resource.openai.azure.com/openai/v1` (v1 surface, **no** `api_version`; ADR §4c) |
| Azure OpenAI key | Azure Portal → the OpenAI resource → **Keys and Endpoint** |
| Deployment names | `gpt-5-mini-1` (use the same for extraction / interview / report unless you've deployed others) |
| Deepgram key | Deepgram console → API Keys |

### A7. (Optional) Find your public IP to lock down SSH
```bash
curl -s https://api.ipify.org
```
Use `<your-ip>/32` as `ALLOWED_SSH_SOURCE_IP`. **Caveat:** the GitHub-hosted runner also needs to SSH into the VM during the `deploy` job, and its IP changes every run. If you restrict SSH to your IP, the deploy job's `ssh-keyscan`/`rsync` will fail. For the first run, **leave `ALLOWED_SSH_SOURCE_IP` unset** (defaults to `*`, key-only auth), then tighten it manually afterwards in the Azure portal (NSG → `allow-ssh`) if you want.

---

## Part B — GitHub secrets

### B1. Open the secrets page
GitHub → repo **getvijayshan/VirtualInterviewer** → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

### B2. Add each secret (Name → Value)

| Secret name | Value | Required |
|---|---|---|
| `AZURE_CREDENTIALS` | Full JSON from A4 | yes |
| `VM_SSH_PUBLIC_KEY` | Contents of `ctc-deploy-key.pub` (one line, `ssh-ed25519 AAAA... azureuser`) | yes |
| `VM_SSH_PRIVATE_KEY` | Contents of `ctc-deploy-key`, **including** the `-----BEGIN/END OPENSSH PRIVATE KEY-----` lines and trailing newline | yes |
| `ALLOWED_SSH_SOURCE_IP` | See A7 — leave unset for first run | no |
| `POSTGRES_USER` | e.g. `candidate_true_companion` | yes |
| `POSTGRES_PASSWORD` | A strong new password (see note below) | yes |
| `POSTGRES_DB` | e.g. `candidate_true_companion` | yes |
| `AZURE_STORAGE_CONNECTION_STRING` | From A6 | yes |
| `AZURE_STORAGE_CONTAINER` | `resume-answer-audio` | yes |
| `AZURE_OPENAI_ENDPOINT` | From A6 | yes |
| `AZURE_OPENAI_API_KEY` | From A6 | yes |
| `AZURE_OPENAI_DEPLOYMENT_EXTRACTION` | `gpt-5-mini-1` | yes |
| `AZURE_OPENAI_DEPLOYMENT_INTERVIEW` | `gpt-5-mini-1` | yes |
| `AZURE_OPENAI_DEPLOYMENT_REPORT` | `gpt-5-mini-1` | yes |
| `DEEPGRAM_API_KEY` | From A6 | yes |
| `HELICONE_BASE_URL` | Leave unset until Helicone is deployed | no |
| `HELICONE_API_KEY` | Leave unset until Helicone is deployed | no |

**Postgres password note:** it is interpolated into `DATABASE_URL=postgresql://user:password@localhost/...`. Use only letters and digits (e.g. `openssl rand -hex 24`) to avoid characters like `@ : / # %` that break the URL.

**Paste tips for multi-line secrets:** paste the private key exactly as the file contains it. Don't wrap in quotes. Don't add extra blank lines before the BEGIN line.

### B3. Optional CLI route (faster than the web UI)
With `gh auth login` done:
```bash
gh secret set AZURE_CREDENTIALS < azure-creds.json
gh secret set VM_SSH_PUBLIC_KEY < ctc-deploy-key.pub
gh secret set VM_SSH_PRIVATE_KEY < ctc-deploy-key
gh secret set POSTGRES_USER --body "candidate_true_companion"
gh secret set POSTGRES_DB --body "candidate_true_companion"
gh secret set POSTGRES_PASSWORD --body "$(openssl rand -hex 24)"   # save it somewhere first!
```
(`openssl rand` output is never shown after this — if you need it later for `psql`, generate it into a variable and print it once before setting.)

### B4. Verify
```bash
gh secret list
```
All required names from the table should appear.

---

## Part C — Run the workflow

1. The workflow file must exist on the default branch for the **Actions** tab to show it, **or** select your branch in the "Use workflow from" dropdown (works for `workflow_dispatch` once the file is pushed on that branch).
2. GitHub → **Actions** → **Provision & Deploy Azure VM** → **Run workflow**.
3. **First run on an empty subscription:** tick `provision_infra` (VM + network + public IP) and `provision_ai_storage` (Blob account/container + AI Foundry). These scripts create everything and fail if the resources already exist, so leave both unticked for later redeploys. Accept the defaults (`resource-virtual-interviewer`, `centralindia`, `virtual-interviewer-backend-vm`, `Standard_D2ls_v6`, `azureuser`) or override.
4. Watch the two jobs: `provision` (creates RG/NSG/VNet/IP/NIC/VM, outputs the public IP) then `deploy` (rsync + `setup_vm.sh`).

### Verify after a successful run
```bash
ssh -i ./ctc-deploy-key azureuser@<VM_PUBLIC_IP>
sudo systemctl status candidate-true-companion-api
docker ps
curl -i http://<VM_PUBLIC_IP>/        # via Nginx
```

---

## Cost & safety notes
- The `Standard_D2ls_v6` VM plus its Standard static public IP (kept deliberately: new VNets have no default outbound internet, so without a public IP or a pricier NAT gateway the VM can't reach apt, Docker Hub or the Azure/Deepgram APIs, and GitHub can't SSH in) bills continuously. Stop with `az vm deallocate -g resource-virtual-interviewer -n virtual-interviewer-backend-vm` (the static IP still bills), or delete everything with `az group delete -n resource-virtual-interviewer`.
- Only ports 22/80/443 are opened. Postgres and the API port stay internal (ADR §10).
- HTTPS/TLS certificates are not covered by this setup. Port 443 is open, but you'll need a domain and a cert (e.g. Let's Encrypt) before using it.
- Rotate `AZURE_CREDENTIALS` and the deploy key if they are ever pasted into chat, logs or a commit.

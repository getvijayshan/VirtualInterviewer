#!/usr/bin/env bash
# Provisions the Azure backend VM + networking for Candidate True Companion
# (see docs/Architecture-Decisions.md §10/§11). Mirrors the resources originally
# created by hand in the portal (infra/az-resource/vm/deployment.json), so a
# fresh subscription/resource group ends up with the same shape.
#
# NOT idempotent by design: it creates everything and fails if a resource
# already exists. The workflow only runs it when "provision_infra" is ticked.
#
# Requires: az CLI logged in (CI does this via azure/login; manually `az login`).
#
# Required env vars:
#   SSH_PUBLIC_KEY         contents of an SSH public key (not a path)
# Optional (defaults match the hand-built environment):
#   RESOURCE_GROUP         resource-virtual-interviewer
#   LOCATION               centralindia
#   VM_NAME                virtual-interviewer-backend-vm
#   VM_SIZE                Standard_D2ls_v6
#   VM_ZONE                1
#   VM_IMAGE               Canonical:ubuntu-24_04-lts:server:latest (Gen2)
#   ADMIN_USERNAME         azureuser
#   VNET_NAME              vnet-centralindia-1       (172.16.0.0/16)
#   SUBNET_NAME            snet-centralindia-1       (172.16.0.0/24)
#   ALLOWED_SSH_SOURCE_IP  "*" (key-only auth); set a CIDR to lock it down

set -euo pipefail

: "${SSH_PUBLIC_KEY:?SSH_PUBLIC_KEY is required}"

RESOURCE_GROUP="${RESOURCE_GROUP:-resource-virtual-interviewer}"
LOCATION="${LOCATION:-centralindia}"
VM_NAME="${VM_NAME:-virtual-interviewer-backend-vm}"
VM_SIZE="${VM_SIZE:-Standard_D2ls_v6}"
VM_ZONE="${VM_ZONE:-1}"
VM_IMAGE="${VM_IMAGE:-Canonical:ubuntu-24_04-lts:server:latest}"
ADMIN_USERNAME="${ADMIN_USERNAME:-azureuser}"
VNET_NAME="${VNET_NAME:-vnet-centralindia-1}"
SUBNET_NAME="${SUBNET_NAME:-snet-centralindia-1}"
ALLOWED_SSH_SOURCE_IP="${ALLOWED_SSH_SOURCE_IP:-*}"

NSG_NAME="${VM_NAME}-nsg"
PUBLIC_IP_NAME="${VM_NAME}-ip"
NIC_NAME="${VM_NAME}-nic"

echo "== Resource group: ${RESOURCE_GROUP} (${LOCATION}) =="
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "== Network security group: ${NSG_NAME} =="
az network nsg create \
  --resource-group "$RESOURCE_GROUP" --name "$NSG_NAME" --location "$LOCATION" --output none

# Priorities match the hand-built NSG (HTTPS 300, SSH 320); HTTP 310 added for
# Nginx / certificate issuance. Postgres (5432) and the API's own port are
# intentionally NOT opened (ADR §10) — only Nginx on 80/443 is public.
az network nsg rule create --resource-group "$RESOURCE_GROUP" --nsg-name "$NSG_NAME" \
  --name HTTPS --priority 300 --access Allow --direction Inbound --protocol Tcp \
  --destination-port-ranges 443 --output none
az network nsg rule create --resource-group "$RESOURCE_GROUP" --nsg-name "$NSG_NAME" \
  --name HTTP --priority 310 --access Allow --direction Inbound --protocol Tcp \
  --destination-port-ranges 80 --output none
az network nsg rule create --resource-group "$RESOURCE_GROUP" --nsg-name "$NSG_NAME" \
  --name SSH --priority 320 --access Allow --direction Inbound --protocol Tcp \
  --destination-port-ranges 22 --source-address-prefixes "$ALLOWED_SSH_SOURCE_IP" --output none

echo "== Virtual network: ${VNET_NAME} / ${SUBNET_NAME} =="
az network vnet create \
  --resource-group "$RESOURCE_GROUP" --name "$VNET_NAME" --location "$LOCATION" \
  --address-prefixes 172.16.0.0/16 \
  --subnet-name "$SUBNET_NAME" --subnet-prefixes 172.16.0.0/24 --output none

# A public IP is required: new VNets no longer get default outbound internet
# access, so without one (or a NAT gateway, which costs more) the VM could not
# reach apt, Docker Hub, Azure OpenAI, Deepgram, or Blob Storage — and GitHub
# runners could not SSH in to deploy. Standard static ≈ the cheapest option.
echo "== Public IP: ${PUBLIC_IP_NAME} =="
az network public-ip create \
  --resource-group "$RESOURCE_GROUP" --name "$PUBLIC_IP_NAME" --location "$LOCATION" \
  --sku Standard --allocation-method Static --zone "$VM_ZONE" --output none

echo "== NIC: ${NIC_NAME} =="
az network nic create \
  --resource-group "$RESOURCE_GROUP" --name "$NIC_NAME" --location "$LOCATION" \
  --vnet-name "$VNET_NAME" --subnet "$SUBNET_NAME" \
  --network-security-group "$NSG_NAME" --public-ip-address "$PUBLIC_IP_NAME" \
  --accelerated-networking true --output none

echo "== Creating VM: ${VM_NAME} (${VM_SIZE}, zone ${VM_ZONE}) =="
# Trusted Launch + NVMe disk controller are required/expected for v6 sizes.
az vm create \
  --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --location "$LOCATION" \
  --zone "$VM_ZONE" --nics "$NIC_NAME" \
  --image "$VM_IMAGE" --size "$VM_SIZE" \
  --admin-username "$ADMIN_USERNAME" --ssh-key-values "$SSH_PUBLIC_KEY" \
  --authentication-type ssh \
  --storage-sku Standard_LRS --os-disk-delete-option Delete --nic-delete-option Detach \
  --security-type TrustedLaunch --enable-secure-boot true --enable-vtpm true \
  --disk-controller-type NVMe \
  --output none

VM_PUBLIC_IP=$(az network public-ip show \
  --resource-group "$RESOURCE_GROUP" --name "$PUBLIC_IP_NAME" \
  --query ipAddress --output tsv)

echo "VM_PUBLIC_IP=${VM_PUBLIC_IP}"
# GitHub Actions step consumes this to feed later steps.
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "vm_public_ip=${VM_PUBLIC_IP}" >> "$GITHUB_OUTPUT"
fi

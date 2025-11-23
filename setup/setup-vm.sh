#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# -------------------------
# CONFIGURE THESE VARIABLES
# -------------------------
VM_NAME="debianvm"
VM_MEM=2048            # MB
VM_VCPUS=1
VM_DISK_GB=10
BRIDGE_NAME="virbr1"
BRIDGE_SUBNET="192.168.200.0/24"
HOST_BRIDGE_IP="192.168.200.1/24"
VM_IP="192.168.200.10"
VM_GATEWAY="192.168.200.1"
BACKUP_DIR="/backups"
CLOUD_IMG_URL="https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2"
IMG_DIR="/var/lib/libvirt/images"
BASE_IMG_NAME="debian-13-genericcloud-amd64.qcow2"
VM_IMG_NAME="${VM_NAME}.qcow2"
CLOUD_INIT_ISO="${IMG_DIR}/${VM_NAME}-seed.iso"
SSH_PUB_KEY="ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBCYS4qhTVud0LCYdEw4PVi527xC/5BpZ+IN/J4k5/NVFGvpwpWOYyM+bpNd3AlOczZ/yFeGgvrBUF0fbRSLNBr8="   # <-- replace with your public key (id_rsa.pub content)
# -------------------------

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root."
  exit 1
fi

echo "Starting automated VM setup for $VM_NAME..."

# -------------------------
# Install dependencies
# -------------------------
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  qemu-kvm libvirt-daemon-system libvirt-clients \
  virtinst cloud-image-utils wget curl nftables rsync

# Enable & start libvirt service if not already
systemctl enable --now libvirtd || true

# -------------------------
# Create bridge if missing
# -------------------------
if ! ip link show "$BRIDGE_NAME" >/dev/null 2>&1; then
  echo "Creating bridge $BRIDGE_NAME..."
  ip link add name "$BRIDGE_NAME" type bridge
  ip addr add "$HOST_BRIDGE_IP" dev "$BRIDGE_NAME"
  ip link set "$BRIDGE_NAME" up
  # Make a simple persistence entry in /etc/network/interfaces.d (Debian)
  cat >/etc/network/interfaces.d/${BRIDGE_NAME}.cfg <<EOF
auto ${BRIDGE_NAME}
iface ${BRIDGE_NAME} inet static
    address ${HOST_BRIDGE_IP%%/*}
    netmask 255.255.255.0
    bridge_ports none
    pre-up /sbin/ip link add name ${BRIDGE_NAME} type bridge || true
    post-down /sbin/ip link delete ${BRIDGE_NAME} type bridge || true
EOF
  echo "Bridge created and configured (temporary & persisted in /etc/network/interfaces.d/${BRIDGE_NAME}.cfg)."
else
  echo "Bridge $BRIDGE_NAME already exists."
fi

# -------------------------
# Download cloud image if missing
# -------------------------
mkdir -p "$IMG_DIR"
if [ ! -f "${IMG_DIR}/${BASE_IMG_NAME}" ]; then
  echo "Downloading cloud image..."
  wget -O "${IMG_DIR}/${BASE_IMG_NAME}.partial" "$CLOUD_IMG_URL"
  mv "${IMG_DIR}/${BASE_IMG_NAME}.partial" "${IMG_DIR}/${BASE_IMG_NAME}"
else
  echo "Base cloud image already present."
fi

# -------------------------
# Create VM image copy
# -------------------------
if [ -f "${IMG_DIR}/${VM_IMG_NAME}" ]; then
  echo "VM image ${VM_IMG_NAME} already exists."
else
  echo "Creating VM qcow2 image from base..."
  qemu-img create -f qcow2 -b "${IMG_DIR}/${BASE_IMG_NAME}" "${IMG_DIR}/${VM_IMG_NAME}" "${VM_DISK_GB}G"
fi

# -------------------------
# Create cloud-init user-data & meta-data
# -------------------------
USER_DATA=$(mktemp)
META_DATA=$(mktemp)

cat >"$USER_DATA" <<EOF
#cloud-config
preserve_hostname: False
hostname: ${VM_NAME}
users:
  - name: cloudadmin
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: sudo
    shell: /bin/bash
    lock_passwd: false
    ssh_authorized_keys:
      - ${SSH_PUB_KEY}
package_update: true
packages:
  - sudo
  - nginx
  - curl
  - vim
  - net-tools
runcmd:
  - [ sh, -c, 'systemctl enable nginx || true' ]
  - [ sh, -c, 'systemctl start nginx || true' ]
  - [ sh, -c, 'echo \"Hello from ${VM_NAME} (nginx)\" > /var/www/html/index.html' ]
# Configure a static network using cloud-init 2.x format
# note: depending on cloud-init version, userdata network config may be supported differently
# we add a cloud-init network config file later via 'network-config' (see below)
EOF

cat >"$META_DATA" <<EOF
instance-id: ${VM_NAME}-$(date +%s)
local-hostname: ${VM_NAME}
EOF

# Create a network-config for cloud-init (cloud-init v2 format) to set static IP
NETWORK_CFG=$(mktemp)
cat >"$NETWORK_CFG" <<EOF
version: 2
ethernets:
  eth0:
    addresses: [ "${VM_IP}/24" ]
    gateway4: ${VM_GATEWAY}
    nameservers:
      addresses: [8.8.8.8,8.8.4.4]
EOF

# Build seed ISO using cloud-localds (includes meta-data, user-data and network-config)
echo "Creating cloud-init seed ISO..."
cloud-localds --network-config="${NETWORK_CFG}" "$CLOUD_INIT_ISO" "$USER_DATA" "$META_DATA"

# -------------------------
# Create VM with virt-install
# -------------------------
echo "Creating VM via virt-install (importing image)..."
virt-install \
  --name "$VM_NAME" \
  --memory "$VM_MEM" \
  --vcpus "$VM_VCPUS" \
  --disk "path=${IMG_DIR}/${VM_IMG_NAME},format=qcow2" \
  --disk "path=${CLOUD_INIT_ISO},device=cdrom" \
  --os-type linux \
  --os-variant debian12 \
  --import \
  --network bridge="$BRIDGE_NAME",model=virtio \
  --noautoconsole \
  --graphics none

echo "Waiting 15 seconds for cloud-init in guest to run..."
sleep 15

# -------------------------
# nftables: NAT (DNAT) and filtering rules
# -------------------------
echo "Configuring nftables rules..."

# save current nftables rules (if any)
NFT_BACKUP="/root/nftables.backup.$(date +%s)"
nft list ruleset >"$NFT_BACKUP" || true

cat >/etc/nftables.conf <<'EOF'
#!/usr/sbin/nft -f

flush ruleset

table ip nat {
  chain prerouting {
    type nat hook prerouting priority 0; policy accept;
    # DNAT TCP 22 -> VM
    tcp dport 22 dnat to 192.168.200.10:22
    # DNAT TCP 80 -> VM
    tcp dport 80 dnat to 192.168.200.10:80
  }

  chain postrouting {
    type nat hook postrouting priority 100; policy accept;
    # Masquerade traffic leaving host
    oifname != "br-vm" masquerade
  }
}

table inet filter {
  chain input {
    type filter hook input priority 0; policy accept;
    # allow established to host, loopback
    ct state established,related accept
    iif "lo" accept
    # keep ssh/http to host itself if needed (optional)
  }

  chain forward {
    type filter hook forward priority 0; policy drop;
    # Allow forwarding to VM for established/related
    ct state established,related accept

    # Allow packets to VM only to 22 and 80 (incoming)
    iifname != "br-vm" oifname "br-vm" tcp dport {22,80} accept

    # Allow host -> VM traffic (useful for management)
    iifname "br-vm" oifname != "br-vm" accept

    # Prevent VM initiating NEW connections to the world:
    # Drop new connections from VM to external interfaces (not br-vm)
    iifname "br-vm" oifname != "br-vm" ct state new drop
  }
}
EOF

# reload nftables
nft -f /etc/nftables.conf

echo "nftables configured. Existing rules backed up to: $NFT_BACKUP"

# -------------------------
# Create backup script
# -------------------------
mkdir -p "$BACKUP_DIR"
BACKUP_SCRIPT="/usr/local/bin/vm-backup-${VM_NAME}.sh"

cat >"$BACKUP_SCRIPT" <<'BKP'
#!/usr/bin/env bash
set -euo pipefail
VMNAME="${VM_NAME}"
IMGDIR="${IMG_DIR}"
BACKUPDIR="${BACKUP_DIR}"
TIMESTAMP="$(date +%F-%H%M%S)"
SNAPFILE="${IMGDIR}/${VMNAME}-snap-${TIMESTAMP}.qcow2"

# Create external disk-only snapshot (new writes will go to snap file)
echo "Creating external snapshot for $VMNAME -> ${SNAPFILE} ..."
virsh snapshot-create-as --domain "${VMNAME}" "backup-${TIMESTAMP}" --diskspec vda,file="${SNAPFILE}" --disk-only --atomic

# Give a second to flush
sleep 2

# Copy the snapshot file to backup dir
mkdir -p "${BACKUPDIR}"
echo "Copying snapshot to ${BACKUPDIR}/${VMNAME}-${TIMESTAMP}.qcow2 ..."
rsync -a --progress "${SNAPFILE}" "${BACKUPDIR}/${VMNAME}-${TIMESTAMP}.qcow2"

# Merge the snapshot back into base (blockcommit)
echo "Merging snapshot back into base image..."
virsh blockcommit "${VMNAME}" vda --active --verbose --wait

# Remove the snapshot file if it still exists
if [ -f "${SNAPFILE}" ]; then
  rm -f "${SNAPFILE}"
fi

echo "Backup completed: ${BACKUPDIR}/${VMNAME}-${TIMESTAMP}.qcow2"
BKP

# Replace placeholders in backup script with actual variables
sed -i "s|${VM_NAME}|${VM_NAME}|g" "$BACKUP_SCRIPT"
sed -i "s|${IMG_DIR}|${IMG_DIR}|g" "$BACKUP_SCRIPT"
sed -i "s|${BACKUP_DIR}|${BACKUP_DIR}|g" "$BACKUP_SCRIPT"

chmod +x "$BACKUP_SCRIPT"
echo "Backup script created at $BACKUP_SCRIPT"

# -------------------------
# Create systemd service + timer for daily backups
# -------------------------
SERVICE_PATH="/etc/systemd/system/vm-backup-${VM_NAME}.service"
TIMER_PATH="/etc/systemd/system/vm-backup-${VM_NAME}.timer"

cat >"$SERVICE_PATH" <<EOF
[Unit]
Description=Backup VM ${VM_NAME}

[Service]
Type=oneshot
ExecStart=${BACKUP_SCRIPT}
EOF

cat >"$TIMER_PATH" <<EOF
[Unit]
Description=Daily backup timer for ${VM_NAME}

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "vm-backup-${VM_NAME}.timer"

echo "systemd timer installed: vm-backup-${VM_NAME}.timer (runs daily)."

# -------------------------
# Final notes & status
# -------------------------
echo ""
echo "=========================================================="
echo "VM ${VM_NAME} should be running with IP ${VM_IP} on bridge ${BRIDGE_NAME}."
echo "Host NAT/DNAT configured so external clients can reach host:$((22)) and host:$((80)) and they will be forwarded to the VM."
echo ""
echo "Firewall behavior summary:"
echo " - Incoming new connections from outside to host:22 and host:80 are DNAT'd to the VM and replies are allowed."
echo " - VM cannot initiate NEW outbound connections to external interfaces (those will be dropped), but established replies for inbound connections are allowed."
echo ""
echo "Backups:"
echo " - Backup script: ${BACKUP_SCRIPT}"
echo " - Backups saved to: ${BACKUP_DIR}"
echo " - Daily systemd timer enabled: vm-backup-${VM_NAME}.timer"
echo ""
echo "To view nftables rules: nft list ruleset"
echo "To view VM console (if needed): virsh console ${VM_NAME}"
echo "To see VM IP from the host (ARP/bridge): ip neigh show dev ${BRIDGE_NAME}"
echo ""
echo "If something needs to be changed, edit variables at the top of the script and re-run parts manually."
echo "=========================================================="

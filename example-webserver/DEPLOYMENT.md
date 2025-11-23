# Deployment Guide - Debian VPS

## Prerequisites

- Debian VPS with root/sudo access
- Domain name (optional but recommended)
- SSH access to your server

## Step 1: Initial Server Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl git build-essential nginx
```

## Step 2: Install Node.js

```bash
# Install Node.js 20.x (LTS)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version
npm --version
```

## Step 3: Create Application User

```bash
# Create a dedicated user for the application
sudo useradd -m -s /bin/bash dashboard
sudo usermod -aG sudo dashboard

# Switch to the new user
sudo su - dashboard
```

## Step 4: Deploy Application

```bash
# Clone your repository (or upload files)
cd ~
git clone <your-repo-url> dashboard-app
cd dashboard-app

# Or if uploading manually:
# Create directory and upload files via SCP/SFTP to /home/dashboard/dashboard-app

# Install dependencies
npm install --production

# Create environment file
cp .env.example .env
nano .env
```

**Edit `.env` file:**
```bash
PORT=3000
NODE_ENV=production
SESSION_SECRET=<generate-strong-random-secret>
```

**Generate session secret:**
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

## Step 5: Initialize Database

```bash
# Initialize database structure
npm run init-db

# Create admin user
npm run create-user
# Enter username and password when prompted
```

## Step 6: Setup PM2 Process Manager

```bash
# Install PM2 globally
sudo npm install -g pm2

# Start application with PM2
pm2 start server.js --name dashboard

# Configure PM2 to start on boot
pm2 startup systemd
# Copy and run the command that PM2 outputs

# Save PM2 configuration
pm2 save

# Check status
pm2 status
pm2 logs dashboard
```

## Step 7: Configure Nginx Reverse Proxy

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/dashboard
```

**Basic configuration (HTTP only):**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

**Enable the site:**
```bash
sudo ln -s /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 8: Setup SSL/HTTPS with Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Certbot will automatically configure Nginx for HTTPS
# Certificates auto-renew, test with:
sudo certbot renew --dry-run
```

**After SSL setup, update `.env`:**
```bash
nano .env
# Ensure NODE_ENV=production so secure cookies work over HTTPS
```

**Restart application:**
```bash
pm2 restart dashboard
```

## Step 9: Configure Firewall

```bash
# Install and configure UFW
sudo apt install -y ufw

# Allow SSH (important - don't lock yourself out!)
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## Step 10: Secure the Database

```bash
# Set proper permissions on database file
cd /home/dashboard/dashboard-app
chmod 600 dashboard.db
chown dashboard:dashboard dashboard.db
```

## Management Commands

### View Application Logs
```bash
pm2 logs dashboard
pm2 logs dashboard --lines 100
```

### Restart Application
```bash
pm2 restart dashboard
```

### Stop Application
```bash
pm2 stop dashboard
```

### Update Application
```bash
cd /home/dashboard/dashboard-app
git pull
npm install --production
pm2 restart dashboard
```

### Backup Database
```bash
# Create backup
cp dashboard.db dashboard.db.backup-$(date +%Y%m%d-%H%M%S)

# Or automated backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/home/dashboard/backups
mkdir -p $BACKUP_DIR
cp /home/dashboard/dashboard-app/dashboard.db $BACKUP_DIR/dashboard-$(date +%Y%m%d-%H%M%S).db
# Keep only last 7 days of backups
find $BACKUP_DIR -name "dashboard-*.db" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab for daily backups at 2 AM
crontab -e
# Add: 0 2 * * * /home/dashboard/backup.sh
```

## Additional Security Hardening

### 1. IP Whitelisting (Optional)
If you know the IP addresses that should access the dashboard:

**Edit Nginx config:**
```nginx
server {
    # ... existing config ...
    
    # Allow specific IPs only
    allow 1.2.3.4;      # Your office IP
    allow 5.6.7.8/24;   # Your network range
    deny all;
    
    location / {
        # ... existing proxy config ...
    }
}
```

### 2. Fail2Ban for Brute Force Protection
```bash
sudo apt install -y fail2ban

# Create custom filter for the dashboard
sudo nano /etc/fail2ban/filter.d/dashboard.conf
```

**Add:**
```ini
[Definition]
failregex = ^.*Invalid credentials.*from <HOST>
ignoreregex =
```

**Configure jail:**
```bash
sudo nano /etc/fail2ban/jail.local
```

**Add:**
```ini
[dashboard]
enabled = true
port = http,https
filter = dashboard
logpath = /home/dashboard/.pm2/logs/dashboard-out.log
maxretry = 5
bantime = 3600
```

```bash
sudo systemctl restart fail2ban
```

### 3. Regular Updates
```bash
# Create update script
cat > /home/dashboard/update.sh << 'EOF'
#!/bin/bash
sudo apt update && sudo apt upgrade -y
cd /home/dashboard/dashboard-app
npm update
pm2 restart dashboard
EOF

chmod +x /home/dashboard/update.sh
```

## Monitoring

### Setup Basic Monitoring
```bash
# PM2 monitoring
pm2 monit

# Install htop for system monitoring
sudo apt install -y htop
htop

# Check disk space
df -h

# Check memory usage
free -h
```

### Setup Log Rotation
PM2 handles log rotation, but configure it:
```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

## Troubleshooting

### Application won't start
```bash
pm2 logs dashboard --err
# Check for errors in the output
```

### Database locked error
```bash
# Stop all instances
pm2 stop all
# Remove lock file if exists
rm dashboard.db-journal
# Restart
pm2 restart dashboard
```

### Nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### Permission issues
```bash
# Fix ownership
sudo chown -R dashboard:dashboard /home/dashboard/dashboard-app
# Fix permissions
chmod 755 /home/dashboard/dashboard-app
chmod 600 /home/dashboard/dashboard-app/dashboard.db
```

## Complete Nginx Configuration with SSL

After running Certbot, your Nginx config should look like:

```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = your-domain.com) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name your-domain.com;
    return 404;
}
```

## Quick Deployment Checklist

- [ ] Server updated and secured
- [ ] Node.js installed
- [ ] Application files deployed
- [ ] Dependencies installed
- [ ] `.env` configured with strong secrets
- [ ] Database initialized
- [ ] Admin user created
- [ ] PM2 configured and running
- [ ] Nginx configured as reverse proxy
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Backups configured
- [ ] Monitoring setup
- [ ] Access tested via domain/IP

## Support

For issues, check:
1. PM2 logs: `pm2 logs dashboard`
2. Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. System logs: `sudo journalctl -xe`

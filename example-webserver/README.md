# 🔒 Secure Dashboard with SQLite

A secure, lightweight dashboard application for managing SQLite database records with authentication and comprehensive security features.

## 🛡️ Security Features

This application implements multiple layers of security:

- **Authentication**: Session-based authentication with bcrypt password hashing
- **CSRF Protection**: Cross-Site Request Forgery tokens on all mutating operations
- **Rate Limiting**: 
  - General API: 100 requests per 15 minutes per IP
  - Login endpoint: 5 attempts per 15 minutes per IP
- **Security Headers**: Helmet.js for HTTP security headers
- **Input Validation**: Express-validator for sanitization and validation
- **SQL Injection Prevention**: Prepared statements with better-sqlite3
- **XSS Protection**: HTML escaping on client-side rendering
- **Secure Sessions**: HTTP-only cookies with configurable secure flag
- **Content Security Policy**: Restricts resource loading

## 📋 Prerequisites

- Node.js (v14 or higher)
- npm or yarn

## 🚀 Installation

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment variables:**
   
   Copy `.env.example` to `.env` and update the values:
   ```bash
   cp .env.example .env
   ```

   **IMPORTANT**: Generate a secure session secret:
   ```bash
   node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
   ```
   
   Then update `SESSION_SECRET` in your `.env` file.

3. **Initialize the database:**
   ```bash
   npm run init-db
   ```

   This creates the SQLite database with tables and sample data.

4. **Create your first user:**
   ```bash
   npm run create-user
   ```

   You'll be prompted to enter:
   - Username
   - Password (minimum 8 characters)
   - Password confirmation
   
   The password will be securely hashed before storage.

## 🎯 Usage

1. **Start the server:**
   ```bash
   npm start
   ```

2. **Access the dashboard:**
   
   Open your browser to `http://localhost:3000`

3. **Login with your created credentials**

## 👥 User Management

**Create additional users:**
```bash
npm run create-user
```

**Note**: There is no user management UI. To modify or delete users, use SQLite commands directly:
```bash
# View all users
sqlite3 dashboard.db "SELECT id, username, created_at FROM users;"

# Delete a user
sqlite3 dashboard.db "DELETE FROM users WHERE username='username';"
```

## 📁 Project Structure

```
.
├── server.js           # Express server with security middleware
├── initDb.js           # Database initialization script
├── createUser.js       # Interactive user creation script
├── package.json        # Dependencies and scripts
├── .env                # Environment configuration (not in git)
├── .env.example        # Environment template
├── .gitignore          # Git ignore rules
├── dashboard.db        # SQLite database (created after init)
└── public/
    └── index.html      # Dashboard frontend
```

## 🔐 Security Best Practices

### For Production Deployment:

1. **Change default credentials** immediately
2. **Use HTTPS** - Set `NODE_ENV=production` in `.env`
3. **Generate strong session secret** - Use cryptographically random values
4. **Keep dependencies updated** - Run `npm audit` regularly
5. **Use environment variables** - Never commit secrets to git
6. **Enable secure cookies** - Requires HTTPS in production
7. **Implement IP whitelisting** - If possible, restrict access by IP
8. **Regular backups** - Backup the SQLite database regularly
9. **Monitor logs** - Watch for suspicious activity
10. **Use a reverse proxy** - nginx or similar for additional security

### Additional Hardening:

- Add two-factor authentication (2FA)
- Implement account lockout after failed attempts
- Add audit logging for all database changes
- Use database encryption at rest
- Implement role-based access control (RBAC)
- Add HTTPS certificate pinning
- Configure stricter CSP policies

## 🗄️ Database Schema

### Users Table
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Items Table
```sql
CREATE TABLE items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  value REAL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 API Endpoints

### Authentication
- `POST /api/login` - Login with username/password
- `POST /api/logout` - Logout current session
- `GET /api/auth-status` - Check authentication status
- `GET /api/csrf-token` - Get CSRF token

### Items (Protected)
- `GET /api/items` - Get all items
- `GET /api/items/:id` - Get single item
- `POST /api/items` - Create new item (requires CSRF token)
- `PUT /api/items/:id` - Update item (requires CSRF token)
- `DELETE /api/items/:id` - Delete item (requires CSRF token)

## 🐛 Troubleshooting

### Cannot login
- Ensure database is initialized: `npm run init-db`
- Check credentials: default is `admin`/`admin123`
- Clear browser cookies and try again

### Database errors
- Delete `dashboard.db` and run `npm run init-db` again
- Check file permissions on the database file

### CSRF token errors
- Refresh the page to get a new token
- Ensure cookies are enabled in your browser

## 📝 Development

For development with auto-reload, you can use nodemon:

```bash
npm install -g nodemon
nodemon server.js
```

## ⚠️ Limitations

- Single-user sessions (one session per user)
- SQLite is not ideal for high-concurrency scenarios
- No password reset functionality (requires manual database update)
- No user registration UI (add users via database)

## 📄 License

ISC

## 🤝 Contributing

This is an internal application. For security issues, please report privately.

---

**Remember**: Security is a process, not a product. Regularly review and update security measures.

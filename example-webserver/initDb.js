require('dotenv').config();
const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');

const db = new Database('dashboard.db');

// Create tables
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    value REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TRIGGER IF NOT EXISTS update_items_timestamp 
  AFTER UPDATE ON items
  BEGIN
    UPDATE items SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
  END;
`);

// Check if any users exist
function checkUsersExist() {
  const userCount = db.prepare('SELECT COUNT(*) as count FROM users').get().count;
  return userCount > 0;
}

// Create sample data
function createSampleData() {
  const itemCount = db.prepare('SELECT COUNT(*) as count FROM items').get().count;

  if (itemCount === 0) {
    const stmt = db.prepare('INSERT INTO items (name, description, value) VALUES (?, ?, ?)');

    stmt.run('Sample Item 1', 'This is a sample item for demonstration', 100);
    stmt.run('Sample Item 2', 'Another example item', 250);
    stmt.run('Sample Item 3', 'Third sample entry', 75);

    console.log('✓ Sample data created');
  } else {
    console.log('✓ Database already contains items');
  }
}

// Initialize database
(async () => {
  try {
    console.log('Initializing database...');

    if (checkUsersExist()) {
      console.log('✓ Users already exist in database');
      console.log('  Run createUser.js to add additional users');
    } else {
      console.log('⚠️  No users found in database');
      console.log('  Run: node createUser.js to create your first admin user');
    }

    createSampleData();
    console.log('✓ Database initialization complete!');
    db.close();
  } catch (error) {
    console.error('Error initializing database:', error);
    process.exit(1);
  }
})();

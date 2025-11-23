require('dotenv').config();
const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const readline = require('readline');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// Promisify readline question
function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

// Hide password input (basic implementation)
function questionHidden(query) {
  return new Promise(resolve => {
    const stdin = process.stdin;
    const stdout = process.stdout;

    stdout.write(query);
    stdin.resume();
    stdin.setRawMode(true);
    stdin.setEncoding('utf8');

    let password = '';

    const onData = (char) => {
      char = char.toString('utf8');

      switch (char) {
        case '\n':
        case '\r':
        case '\u0004': // Ctrl-D
          stdin.setRawMode(false);
          stdin.pause();
          stdin.removeListener('data', onData);
          stdout.write('\n');
          resolve(password);
          break;
        case '\u0003': // Ctrl-C
          process.exit();
          break;
        case '\u007f': // Backspace
        case '\b':
          if (password.length > 0) {
            password = password.slice(0, -1);
            // Clear line and rewrite prompt with asterisks
            stdout.clearLine(0);
            stdout.cursorTo(0);
            stdout.write(query + '*'.repeat(password.length));
          }
          break;
        default:
          // Only add printable characters
          if (char.charCodeAt(0) >= 32 && char.charCodeAt(0) <= 126) {
            password += char;
            // Clear line and rewrite prompt with asterisks
            stdout.clearLine(0);
            stdout.cursorTo(0);
            stdout.write(query + '*'.repeat(password.length));
          }
          break;
      }
    };

    stdin.on('data', onData);
  });
}

async function createUser() {
  const db = new Database('dashboard.db');

  console.log('=== Create New User ===\n');

  try {
    // Get username
    const username = await question('Username: ');

    if (!username || username.trim().length === 0) {
      console.log('Error: Username cannot be empty');
      rl.close();
      db.close();
      process.exit(1);
    }

    // Check if username already exists
    const existingUser = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim());
    if (existingUser) {
      console.log(`Error: User '${username.trim()}' already exists`);
      rl.close();
      db.close();
      process.exit(1);
    }

    // Get password
    const password = await questionHidden('Password: ');

    if (!password || password.length < 6) {
      console.log('\nError: Password must be at least 6 characters long');
      rl.close();
      db.close();
      process.exit(1);
    }

    // Confirm password
    const confirmPassword = await questionHidden('Confirm password: ');

    if (password !== confirmPassword) {
      console.log('\nError: Passwords do not match');
      rl.close();
      db.close();
      process.exit(1);
    }

    // Hash password and create user
    console.log('\nCreating user...');
    const hashedPassword = await bcrypt.hash(password, 10);
    db.prepare('INSERT INTO users (username, password_hash) VALUES (?, ?)').run(username.trim(), hashedPassword);

    console.log(`✓ User '${username.trim()}' created successfully!`);

  } catch (error) {
    console.error('\nError creating user:', error.message);
    process.exit(1);
  } finally {
    rl.close();
    db.close();
  }
}

// Run
createUser();

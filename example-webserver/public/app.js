let csrfToken = '';
let isAuthenticated = false;

// Check authentication status on load
async function checkAuth() {
  try {
    const response = await fetch('/api/auth-status');
    const data = await response.json();

    if (data.authenticated) {
      isAuthenticated = true;
      document.getElementById('currentUser').textContent = data.username;
      showDashboard();
      await getCsrfToken();
      await loadItems();
    } else {
      showLogin();
    }
  } catch (error) {
    console.error('Auth check error:', error);
    showLogin();
  }
}

// Get CSRF token
async function getCsrfToken() {
  try {
    const response = await fetch('/api/csrf-token');
    const data = await response.json();
    csrfToken = data.csrfToken;
  } catch (error) {
    console.error('CSRF token error:', error);
  }
}

// Login
function initLoginForm() {
  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });

      const data = await response.json();

      if (response.ok) {
        isAuthenticated = true;
        document.getElementById('currentUser').textContent = data.username;
        showDashboard();
        await getCsrfToken();
        await loadItems();
      } else {
        errorDiv.textContent = data.error || 'Login failed';
        errorDiv.classList.remove('hidden');
      }
    } catch (error) {
      errorDiv.textContent = 'Connection error. Please try again.';
      errorDiv.classList.remove('hidden');
    }
  });
}

// Logout
async function logout() {
  try {
    await fetch('/api/logout', { method: 'POST' });
    isAuthenticated = false;
    showLogin();
  } catch (error) {
    console.error('Logout error:', error);
  }
}

// Show/hide screens
function showLogin() {
  document.getElementById('loginScreen').style.display = 'block';
  document.getElementById('dashboardScreen').classList.remove('active');
  document.getElementById('loginForm').reset();
  document.getElementById('loginError').classList.add('hidden');
}

function showDashboard() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('dashboardScreen').classList.add('active');
}

// Load items
async function loadItems() {
  try {
    const response = await fetch('/api/items');

    if (response.status === 401) {
      showLogin();
      return;
    }

    const items = await response.json();
    displayItems(items);
  } catch (error) {
    console.error('Error loading items:', error);
  }
}

// Display items
function displayItems(items) {
  const container = document.getElementById('itemsContainer');

  if (items.length === 0) {
    container.innerHTML = '<p style="text-align: center; grid-column: 1/-1;">No items found.</p>';
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="item-card">
      <h3>${escapeHtml(item.name)}</h3>
      <p>${escapeHtml(item.description || 'No description')}</p>
      <div class="item-value">$${parseFloat(item.value).toFixed(2)}</div>
      <div class="item-meta">Created: ${new Date(item.created_at).toLocaleDateString()}</div>
      <div class="item-actions">
        <button class="btn" data-action="edit" data-id="${item.id}">Edit</button>
        <button class="btn btn-danger" data-action="delete" data-id="${item.id}">Delete</button>
      </div>
    </div>
  `).join('');

  // Add event listeners for buttons
  container.querySelectorAll('[data-action="edit"]').forEach(btn => {
    btn.addEventListener('click', () => editItem(btn.dataset.id));
  });
  container.querySelectorAll('[data-action="delete"]').forEach(btn => {
    btn.addEventListener('click', () => deleteItem(btn.dataset.id));
  });
}

// Show add modal
function showAddModal() {
  document.getElementById('modalTitle').textContent = 'Add New Item';
  document.getElementById('itemForm').reset();
  document.getElementById('itemId').value = '';
  document.getElementById('modalError').classList.add('hidden');
  document.getElementById('itemModal').classList.add('active');
}

// Edit item
async function editItem(id) {
  try {
    const response = await fetch(`/api/items/${id}`);
    const item = await response.json();

    document.getElementById('modalTitle').textContent = 'Edit Item';
    document.getElementById('itemId').value = item.id;
    document.getElementById('itemName').value = item.name;
    document.getElementById('itemDescription').value = item.description || '';
    document.getElementById('itemValue').value = item.value;
    document.getElementById('modalError').classList.add('hidden');
    document.getElementById('itemModal').classList.add('active');
  } catch (error) {
    console.error('Error loading item:', error);
  }
}

// Close modal
function closeModal() {
  document.getElementById('itemModal').classList.remove('active');
}

// Save item
function initItemForm() {
  document.getElementById('itemForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const id = document.getElementById('itemId').value;
    const name = document.getElementById('itemName').value;
    const description = document.getElementById('itemDescription').value;
    const value = document.getElementById('itemValue').value;
    const errorDiv = document.getElementById('modalError');

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/items/${id}` : '/api/items';

    try {
      const response = await fetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'CSRF-Token': csrfToken
        },
        body: JSON.stringify({ name, description, value: parseFloat(value) })
      });

      if (response.ok) {
        closeModal();
        await loadItems();
      } else {
        const data = await response.json();
        errorDiv.textContent = data.error || 'Failed to save item';
        errorDiv.classList.remove('hidden');
      }
    } catch (error) {
      errorDiv.textContent = 'Connection error. Please try again.';
      errorDiv.classList.remove('hidden');
    }
  });
}

// Delete item
async function deleteItem(id) {
  if (!confirm('Are you sure you want to delete this item?')) {
    return;
  }

  try {
    const response = await fetch(`/api/items/${id}`, {
      method: 'DELETE',
      headers: {
        'CSRF-Token': csrfToken
      }
    });

    if (response.ok) {
      await loadItems();
    } else {
      alert('Failed to delete item');
    }
  } catch (error) {
    console.error('Error deleting item:', error);
    alert('Connection error');
  }
}

// HTML escape function
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initLoginForm();
  initItemForm();

  // Add event listeners for buttons
  document.getElementById('logoutBtn').addEventListener('click', logout);
  document.getElementById('addItemBtn').addEventListener('click', showAddModal);
  document.getElementById('closeModalBtn').addEventListener('click', closeModal);

  checkAuth();
});

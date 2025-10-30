// Main JavaScript for CORE Scout Flask application

// Menu functionality
function toggleMenu() {
    const dropdownMenu = document.getElementById('dropdownMenu');
    if (dropdownMenu.style.display === 'none' || dropdownMenu.style.display === '') {
        dropdownMenu.style.display = 'block';
    } else {
        dropdownMenu.style.display = 'none';
    }
}

function closeMenu() {
    const dropdownMenu = document.getElementById('dropdownMenu');
    dropdownMenu.style.display = 'none';
}

// Close menu when clicking outside
document.addEventListener('click', function (event) {
    const dropdownMenu = document.getElementById('dropdownMenu');
    const menuIcon = document.querySelector('.menu-icon');

    if (dropdownMenu && menuIcon &&
        !dropdownMenu.contains(event.target) &&
        !menuIcon.contains(event.target)) {
        dropdownMenu.style.display = 'none';
    }
});

// Auto-hide flash messages
document.addEventListener('DOMContentLoaded', function () {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function (message) {
        setTimeout(function () {
            message.style.opacity = '0';
            setTimeout(function () {
                message.remove();
            }, 300);
        }, 5000);
    });
});

// Search functionality
function performSearch() {
    const query = document.getElementById('searchQuery').value;
    const table = document.getElementById('selectedTable').value;

    if (!table) {
        alert('Please select a table to search');
        return;
    }

    // Redirect to results page (empty query is allowed for wildcard search)
    window.location.href = `/results?q=${encodeURIComponent(query)}&table=${encodeURIComponent(table)}`;
}

// Handle Enter key in search input
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchQuery');
    if (searchInput) {
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }
});

// Database creation functionality
function handleFileTypeToggle(fileType) {
    const checkbox = document.getElementById(`fileType_${fileType}`);
    if (checkbox) {
        checkbox.checked = !checkbox.checked;
    }
}

function selectAllFileTypes() {
    const checkboxes = document.querySelectorAll('input[name="file_types"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);

    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
    });

    const button = document.getElementById('selectAllButton');
    if (button) {
        button.textContent = allChecked ? '☑ Select All' : '☐ Deselect All';
    }
}

// Drag and drop functionality for file uploads
function setupDragAndDrop() {
    const dropZones = document.querySelectorAll('.upload-box, .folder-drop-zone');

    dropZones.forEach(zone => {
        zone.addEventListener('dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            zone.style.backgroundColor = '#f8f9fa';
        });

        zone.addEventListener('dragleave', function (e) {
            e.preventDefault();
            e.stopPropagation();
            zone.style.backgroundColor = '';
        });

        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            zone.style.backgroundColor = '';

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileUpload(files[0], zone);
            }
        });
    });
}

function handleFileUpload(file, dropZone) {
    // Check if it's a database file upload
    if (dropZone.classList.contains('upload-box')) {
        if (file.name.toLowerCase().endsWith('.db') ||
            file.name.toLowerCase().endsWith('.sqlite') ||
            file.name.toLowerCase().endsWith('.sqlite3')) {
            // Use FormData + fetch; FileList assignment is not allowed in browsers
            const formData = new FormData();
            formData.append('database_file', file, file.name);

            fetch('/upload_database', {
                method: 'POST',
                body: formData
            }).then(() => {
                // Navigate to settings to display flash messages and refreshed state
                window.location.href = '/settings';
            }).catch(() => {
                alert('Failed to upload database. Please try again via Settings.');
            });
        } else {
            alert('Please upload a valid database file (.db, .sqlite, or .sqlite3)');
        }
    }
    // Handle folder drop for database creation
    else if (dropZone.classList.contains('folder-drop-zone')) {
        // This would need to be implemented with a file picker API
        alert('Folder selection via drag & drop is not supported in web browsers. Please use the "Browse for Folder" button.');
    }
}

// Initialize drag and drop when page loads
document.addEventListener('DOMContentLoaded', function () {
    setupDragAndDrop();
});

// Progress bar animation
function updateProgress(current, total, currentFile) {
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');
    const currentFileText = document.querySelector('.current-file');

    if (progressFill) {
        const percentage = total > 0 ? (current / total) * 100 : 0;
        progressFill.style.width = percentage + '%';
    }

    if (progressText) {
        progressText.textContent = `${current} of ${total} files processed`;
    }

    if (currentFileText && currentFile) {
        currentFileText.textContent = `Processing: ${currentFile}`;
    }
}

// Export KML functionality
function exportKML(tableName, query, mgrsField) {
    const params = new URLSearchParams({
        q: query || '*',
        mgrs_field: mgrsField || 'MGRS',
        limit: 10000
    });

    window.location.href = `/export_kml/${tableName}?${params.toString()}`;
}

// Utility functions
function formatNumber(num) {
    return num.toLocaleString();
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        return new Date(dateString).toLocaleString();
    } catch (e) {
        return dateString;
    }
}

// API helper functions
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Health check
async function checkBackendHealth() {
    try {
        const health = await apiRequest('/api/health');
        return health.status === 'healthy';
    } catch (error) {
        return false;
    }
}

// Auto-refresh functionality for search page
function setupAutoRefresh() {
    const refreshButton = document.getElementById('refreshTables');
    if (refreshButton) {
        refreshButton.addEventListener('click', function () {
            location.reload();
        });
    }
}

// Initialize page-specific functionality
document.addEventListener('DOMContentLoaded', function () {
    setupAutoRefresh();

    // Set page class for background styling
    const path = window.location.pathname;
    const pageClass = path === '/' ? 'home' :
        path.startsWith('/about') ? 'about' :
            path.startsWith('/contact') ? 'contact' :
                path.startsWith('/results') ? 'results' :
                    path.startsWith('/settings') ? 'settings' :
                        path.startsWith('/create') ? 'create' : '';

    if (pageClass) {
        document.body.classList.add(pageClass);
    }
});

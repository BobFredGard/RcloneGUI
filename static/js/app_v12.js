const API_BASE = '/api';
let currentToken = localStorage.getItem('token');

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
    document.getElementById(screenId).classList.remove('hidden');
}

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(tabId + '-tab').classList.add('active');
    document.querySelector(`[data-tab="${tabId}"]`)?.classList.add('active');
    if (tabId === 'logs') loadLogs();
}

async function apiRequest(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (currentToken) {
        headers['Authorization'] = `Bearer ${currentToken}`;
    }

    try {
        const response = await fetch(API_BASE + endpoint, {
            ...options,
            headers: { ...headers, ...options.headers }
        });
        
        if (response.status === 401) {
            currentToken = null;
            localStorage.removeItem('token');
            showScreen('login-screen');
            return null;
        }
        
        if (!response.ok) {
            console.error('API Error:', response.status, response.statusText);
            const text = await response.text();
            console.error('Error response:', text);
            return null;
        }
        
        if (response.headers.get('content-type')?.includes('application/json')) {
            return await response.json();
        }
        return { message: 'OK' };
    } catch (e) {
        console.error('API Error:', e);
        return null;
    }
}

function showToast(message, type = 'success') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="icon">${type === 'success' ? '✓' : '✗'}</span>
        <span class="message">${message}</span>
    `;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function login(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const result = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
    });

    if (result?.token) {
        currentToken = result.token;
        localStorage.setItem('token', result.token);
        showScreen('main-screen');
        loadBackups();
        loadConnections();
    } else {
        document.getElementById('login-error').textContent = result?.error || 'Erreur de connexion';
    }
}

async function register(e) {
    e.preventDefault();
    const username = document.getElementById('reg-username').value;
    const password = document.getElementById('reg-password').value;

    const result = await apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username, password })
    });

    if (result?.message) {
        showToast('Compte créé! Connectez-vous.', 'success');
        showScreen('login-screen');
    } else {
        document.getElementById('register-error').textContent = result?.error || "Erreur d'inscription";
    }
}

function logout() {
    currentToken = null;
    localStorage.removeItem('token');
    showScreen('login-screen');
}

async function checkAuth() {
    if (!currentToken) {
        showScreen('login-screen');
        return;
    }
    const result = await apiRequest('/auth/check');
    if (!result) {
        showScreen('login-screen');
    } else {
        showScreen('main-screen');
        loadBackups();
        loadConnections();
    }
}

function formatSchedule(schedule) {
    const schedules = {
        'off': 'OFF',
        'on': 'ON'
    };
    return schedules[schedule] || schedule;
}

function destIcon(type) {
    if (type === 'local') return '💻';
    if (type === 'network') return '🌐';
    return '☁️';
}

function formatStatus(status, lastRun) {
    // If has last_status, use it
    if (status === 'success') return '✓ OK';
    if (status === 'failed') return '✗ Échec';
    if (status === 'cancelled') return '✗ Annulé';
    // If has run before but no status, show last run time
    if (lastRun) {
        try {
            const d = new Date(lastRun.replace(' ', 'T') + 'Z');
            if (!isNaN(d.getTime())) {
                return d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
            }
        } catch {}
        return '⏳ Terminé';
    }
    // Never run
    return 'Jamais';
}

async function loadBackups() {
    const backups = await apiRequest('/backups');
    if (!backups) return;
    window.currentBackups = backups;

    const container = document.getElementById('backups-list');

    if (backups.length === 0) {
        container.innerHTML = `
            <div class="backup-item" style="justify-content: center; color: var(--text-secondary);">
                Aucune sauvegarde. Créez-en une nouvelle!
            </div>
        `;
        return;
    }

    container.innerHTML = backups.map(backup => {
        const now = new Date();
        
        // Check if backup is running (by pid or started_at)
        let isRunning = backup.pid !== null && backup.pid !== undefined;
        
        // Fallback: check started_at
        if (!isRunning && backup.started_at) {
            const startedAt = new Date(backup.started_at.replace(' ', 'T') + 'Z');
            if (!isNaN(startedAt.getTime()) && (now.getTime() - startedAt.getTime()) < 120000) {
                isRunning = true;
            }
        }
        
        // Can cancel only if actually running (has PID or recent started_at)
        const canCancel = isRunning;
        
        // Also check last_run within 2 minutes
        if (!isRunning && backup.last_run) {
            const lastRunTime = new Date(backup.last_run.replace(' ', 'T') + 'Z');
            if (!isNaN(lastRunTime.getTime())) {
                const secondsAgo = Math.floor((now.getTime() - lastRunTime.getTime()) / 1000);
                // Only show "En cours" if it finished within last 2 minutes (120 seconds)
                if (secondsAgo >= 0 && secondsAgo < 120) {
                    isRunning = true;
                }
            }
        }

        let countdownText = '';
        let showCountdown = false;

        if (backup.schedule_type === 'on') {
            showCountdown = true;
            countdownText = isRunning ? 'En cours...' : 'En attente';
        }

        // Get PID from backup data
        const pid = isRunning ? backup.pid : null;
        
        let statusBadge = '';
        if (isRunning) {
            statusBadge = `<span class="status-running-badge">⚡ EN COURS</span>`;
        }
        
        const lastRunDisplay = backup.last_run ? (() => {
            try {
                const d = new Date(backup.last_run.replace(' ', 'T'));
                return isNaN(d.getTime()) ? 'Jamais' : d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
            } catch { return 'Jamais'; }
        })() : 'Jamais';
        
        return `
        <div class="backup-item ${isRunning ? 'running' : ''} ${backup.bidirectional ? 'bidirectional' : ''} ${backup.night_only ? 'night-only' : ''}" data-id="${backup.id}" data-last-run="${backup.last_run || ''}" data-schedule="${backup.schedule_type}" data-started="${backup.started_at || ''}" data-next-run="${backup.next_run || ''}" data-bidirectional="${backup.bidirectional || false}">
            <div class="backup-progress" style="width: ${isRunning ? '2%' : '0%'}"></div>
            <div class="backup-main">
                <div class="backup-info">
                    <h4>${escapeHtml(backup.name)} ${statusBadge}</h4>
                    <div class="details">
                        <span class="detail-item">📁 <strong>Source:</strong> ${escapeHtml(backup.source_path)}</span>
                        <span class="detail-item">${destIcon(backup.destination_type || 'dropbox')} <strong>Dest:</strong> ${escapeHtml(backup.destination_path || backup.dropbox_path)}</span>
                    </div>
                </div>
                <div class="backup-separator"></div>
                <div class="backup-info-right">
                    <div class="detail-item">⏱️ <strong>Planifié:</strong> ${formatSchedule(backup.schedule_type)}</div>
                    <div class="detail-item">📅 <strong>Dernière:</strong> ${lastRunDisplay}</div>
                    ${showCountdown ? `<div class="detail-item countdown">⏳ ${countdownText}</div>` : ''}
                </div>
                <div class="backup-separator"></div>
                <div class="backup-actions">
                    <span class="backup-status ${isRunning ? 'running' : (backup.last_status || 'pending')}">${isRunning ? '' : formatStatus(backup.last_status, backup.last_run)}</span>
                    ${isRunning ? `<button class="btn btn-danger btn-cancel" onclick="cancelBackup(${backup.id})">Annuler</button>` : (backup.schedule_type === 'off' ? `<button class="btn btn-secondary btn-run" onclick="runBackup(${backup.id})">Exécuter</button>` : `<button class="btn btn-secondary" disabled>Auto</button>`)}
                    <button class="btn btn-secondary btn-edit" onclick="editBackup(${backup.id})">Modifier</button>
                    <button class="btn btn-danger btn-delete" onclick="deleteBackup(${backup.id})">Supprimer</button>
                    <button class="btn btn-secondary btn-expand" onclick="toggleExpand(${backup.id})" title="Voir les fichiers">▶</button>
                </div>
            </div>
            <div class="backup-details hidden" id="details-${backup.id}">
                <div class="backup-details-content">
                    <div class="detail-current-file" id="current-file-${backup.id}"></div>
                    <div class="detail-transfer-info" id="transfer-info-${backup.id}"></div>
                    <div class="detail-categories">
                        <div class="detail-cat transferred">
                            <div class="cat-header">✓ Transférés</div>
                            <div class="cat-list" id="transferred-${backup.id}"><div class="files-placeholder">En attente...</div></div>
                        </div>
                        <div class="detail-cat skipped">
                            <div class="cat-header">⏭ Ignorés</div>
                            <div class="cat-list" id="skipped-${backup.id}"><div class="files-placeholder">En attente...</div></div>
                        </div>
                        <div class="detail-cat failed">
                            <div class="cat-header">✗ Échoués</div>
                            <div class="cat-list" id="failed-${backup.id}"><div class="files-placeholder">En attente...</div></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
    }).join('');

    // Restore expanded state after re-render
    expandedBackups.forEach(id => {
        const details = document.getElementById(`details-${id}`);
        const btn = document.querySelector(`.backup-item[data-id="${id}"] .btn-expand`);
        if (details) {
            details.classList.remove('hidden');
            if (btn) btn.textContent = '▼';
        }
        const item = document.querySelector(`.backup-item[data-id="${id}"]`);
        if (item && (item.classList.contains('running') || item.dataset.started)) {
            connectProgressSSE(id);
        }
    });

    // Poll every 5 seconds to update status
    setInterval(async () => {
        const backups = await apiRequest('/backups');
        if (!backups) return;
        
        const container = document.getElementById('backups-list');
        if (!container) return;
        
        const now = Date.now();
        
        container.querySelectorAll('.backup-item[data-id]').forEach(item => {
            const backup = backups.find(b => b.id == item.dataset.id);
            if (!backup) return;
            
            // Check if running (by pid in backup data, or fallback to started_at)
            let isRunning = backup.pid !== null && backup.pid !== undefined;
            
            // Fallback: check started_at
            if (!isRunning && backup.started_at) {
                const startedAt = new Date(backup.started_at.replace(' ', 'T') + 'Z');
                if (!isNaN(startedAt.getTime()) && (now - startedAt.getTime()) < 120000) {
                    isRunning = true;
                }
            }
            
            const pid = backup.pid;
            
            // Update badge - add when running, remove when not running
            const titleEl = item.querySelector('h4');
            if (titleEl) {
                const existingBadge = titleEl.querySelector('.status-running-badge');
                // Add badge when running
                if (isRunning && !existingBadge) {
                    const badge = document.createElement('span');
                    badge.className = 'status-running-badge';
                    badge.textContent = '⚡ EN COURS';
                    titleEl.appendChild(badge);
                }
                // Update badge with PID
                if (isRunning && existingBadge) {
                    existingBadge.textContent = '⚡ EN COURS';
                }
                // Remove badge when not running
                if (!isRunning && existingBadge) {
                    existingBadge.remove();
                }
            }
            
            // Check if ANY backup is currently running
            const anyBackupRunning = backups.some(b => b.pid !== null && b.pid !== undefined);
            
            // Check if this backup's countdown has expired (overdue)
            let isOverdue = false;
            if (backup.next_run && !isRunning) {
                const parts = backup.next_run.split('.');
                const datePart = parts[0].replace(' ', 'T') + 'Z';
                const nextRunDate = new Date(datePart);
                if (!isNaN(nextRunDate.getTime())) {
                    const diff = nextRunDate.getTime() - now;
                    if (diff <= 0) {
                        isOverdue = true;
                    }
                }
            }
            
            // Update status text
            const statusEl = item.querySelector('.backup-status');
            if (statusEl) {
                if (isRunning) {
                    statusEl.textContent = '';
                    statusEl.className = 'backup-status running';
                } else {
                    statusEl.textContent = formatStatus(backup.last_status, backup.last_run);
                    statusEl.className = 'backup-status ' + (backup.last_status || 'pending');
                }
            }
            
            // Update last run display
            if (!isRunning && backup.last_run) {
                const details = item.querySelectorAll('.backup-info-right .detail-item');
                details.forEach(el => {
                    if (el.textContent.includes('Dernière')) {
                        try {
                            const d = new Date(backup.last_run.replace(' ', 'T'));
                            if (!isNaN(d.getTime())) {
                                el.innerHTML = `📅 <strong>Dernière:</strong> ${d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}`;
                            }
                        } catch {}
                    }
                });
            }
            
            // Update countdown
            const countdown = item.querySelector('.countdown');
            if (countdown && backup.schedule_type === 'on') {
                countdown.textContent = isRunning ? '⏳ En cours...' : '⏳ En attente';
            }
            
            // Update panel border - reset properly after backup finishes
            if (isRunning) {
                item.classList.add('running');
                // Show progress bar for all running backups
                const progress = item.querySelector('.backup-progress');
                if (progress) {
                    progress.style.opacity = '1';
                    // Animate progress
                    const currentWidth = parseFloat(progress.style.width) || 0;
                    if (currentWidth < 90) {
                        progress.style.width = (currentWidth + 2) + '%';
                    }
                }
            } else {
                // Always remove manual run class
                item.classList.remove('running-manual');
                // Remove running class - use fresh data from API
                const freshBackup = backups.find(b => b.id == item.dataset.id);
                // Check if not running - either no started_at OR last_run is more than 2 min ago
                let shouldReset = false;
                if (freshBackup) {
                    if (!freshBackup.started_at) {
                        shouldReset = true;
                    } else {
                        // Check if started_at is more than 2 min ago
                        const startedAt = freshBackup.started_at ? new Date(freshBackup.started_at.replace(' ', 'T') + 'Z') : null;
                        if (startedAt && (now - startedAt.getTime()) >= 120000) {
                            shouldReset = true;
                        }
                    }
                }
                if (shouldReset) {
                    item.classList.remove('running');
                    // Hide progress bar
                    const progress = item.querySelector('.backup-progress');
                    if (progress) {
                        progress.style.width = '0%';
                        progress.style.opacity = '0';
                    }
                }
            }
            
            // Reset button when not running
            const btn = item.querySelector('.btn-run');
            const cancelBtn = item.querySelector('.btn-cancel');
            const autoBtn = item.querySelector('button.btn-secondary[disabled]');
            const canCancel = isRunning;
            
            if (canCancel && !cancelBtn) {
                // Need to replace run/auto button with cancel button
                if (btn) {
                    btn.outerHTML = `<button class="btn btn-danger btn-cancel" onclick="cancelBackup(${backup.id})">Annuler</button>`;
                } else if (autoBtn) {
                    autoBtn.outerHTML = `<button class="btn btn-danger btn-cancel" onclick="cancelBackup(${backup.id})">Annuler</button>`;
                }
            } else if (!canCancel && cancelBtn) {
                // Need to replace cancel button with run/auto button
                if (backup.schedule_type === 'off') {
                    cancelBtn.outerHTML = `<button class="btn btn-secondary btn-run" onclick="runBackup(${backup.id})">Exécuter</button>`;
                } else {
                    cancelBtn.outerHTML = `<button class="btn btn-secondary" disabled>Auto</button>`;
                }
            }
        });
    }, 5000);
}

async function createBackup(e) {
    e.preventDefault();
    const name = document.getElementById('backup-name').value;
    const source_path = document.getElementById('source-path').value;
    const dest_type = document.getElementById('dest-type').value;
    const dropbox_path = document.getElementById('dropbox-path').value;
    const dest_path = document.getElementById('dest-path').value;
    const schedule_type = document.getElementById('schedule-type').value;
    const bidirectional = document.getElementById('bidirectional').value === '1';
    const night_only = document.getElementById('night_only')?.checked || false;
    const exclusions_text = document.getElementById('exclusions').value;
    const exclusions = exclusions_text.split('\n').filter(e => e.trim());

    const result = await apiRequest('/backups', {
        method: 'POST',
        body: JSON.stringify({
            name, source_path,
            destination_type: dest_type,
            destination_path: dest_type === 'dropbox' ? dropbox_path : dest_path,
            dropbox_path,
            schedule_type, exclusions, bidirectional, night_only
        })
    });

    if (result?.id) {
        document.getElementById('backup-form').reset();
        document.getElementById('backup-form-panel').classList.add('hidden');
        loadBackups();
    }
}

async function runBackup(id) {
    const item = document.querySelector(`.backup-item[data-id="${id}"]`);
    const btn = item?.querySelector('.btn-run');
    const progress = item?.querySelector('.backup-progress');
    const statusEl = item?.querySelector('.backup-status');

    if (item) {
        item.classList.add('running', 'running-manual');
        if (progress) {
            progress.style.opacity = '1';
            progress.style.width = '2%';
        }
    }
    if (statusEl) {
        statusEl.textContent = '🔄 En cours';
        statusEl.className = 'backup-status running';
    }
    if (btn) {
        btn.textContent = '⏳...';
        btn.disabled = true;
    }

    let progressPercent = 2;
    const progressInterval = setInterval(() => {
        if (progressPercent < 90) {
            progressPercent += 1.5;
            if (progressPercent > 90) progressPercent = 90;
            if (progress) progress.style.width = progressPercent + '%';
        }
    }, 200);

    try {
        const result = await apiRequest(`/backups/${id}/run`, { method: 'POST' });
        console.log('Run backup result:', result);

        clearInterval(progressInterval);
        if (progress) progress.style.width = '100%';

        if (result) {
            if (result.success) {
                showToast('Sauvegarde terminée!', 'success');
            } else {
                showToast(result.error || 'Échec', 'error');
            }
            setTimeout(() => {
                if (item) item.classList.remove('running', 'running-manual');
                if (progress) {
                    progress.style.width = '0%';
                    progress.style.opacity = '0';
                }
                if (btn) {
                    btn.textContent = 'Exécuter';
                    btn.disabled = false;
                }
            }, 500);
        }
    } catch (e) {
        console.error(e);
        clearInterval(progressInterval);
        if (item) item.classList.remove('running', 'running-manual');
        if (progress) progress.style.width = '0%';
        if (btn) {
            btn.textContent = 'Exécuter';
            btn.disabled = false;
        }
        showToast('Erreur: ' + e.message, 'error');
    }
}

async function cancelBackup(id) {
    if (!confirm('Voulez-vous vraiment annuler cette sauvegarde ?')) {
        return;
    }
    
    try {
        const result = await apiRequest(`/backups/${id}/cancel`, { method: 'POST' });
        if (result?.success) {
            showToast('Sauvegarde annulée', 'success');
            loadBackups();
        } else {
            showToast(result?.error || 'Erreur lors de l\'annulation', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('Erreur: ' + e.message, 'error');
    }
}

async function editBackup(id) {
    const result = await apiRequest(`/backups/${id}`);
    if (!result) return;

    document.getElementById('edit-backup-id').value = id;
    document.getElementById('edit-name').value = result.name;
    document.getElementById('edit-source').value = result.source_path;
    const etype = result.destination_type || 'dropbox';
    document.getElementById('edit-dest-type').value = etype;
    document.getElementById('edit-dest').value = result.dropbox_path || '';
    document.getElementById('edit-dest-path').value = result.destination_path || result.dropbox_path || '';
    document.querySelector('.edit-dest-dropbox-group')?.classList.toggle('hidden', etype !== 'dropbox');
    document.querySelector('.edit-dest-path-group')?.classList.toggle('hidden', etype === 'dropbox');
    document.getElementById('edit-schedule').value = result.schedule_type;
    document.getElementById('edit-bidirectional').value = result.bidirectional ? '1' : '0';
    if (document.getElementById('edit-night_only')) {
        document.getElementById('edit-night_only').checked = result.night_only || false;
    }
    
    try {
        const exclusions = JSON.parse(result.exclusions || '[]');
        document.getElementById('edit-exclusions').value = exclusions.join('\n');
    } catch {
        document.getElementById('edit-exclusions').value = '';
    }

    document.getElementById('backup-modal').classList.remove('hidden');
}

async function saveBackupEdit(e) {
    e.preventDefault();
    const id = document.getElementById('edit-backup-id').value;
    const name = document.getElementById('edit-name').value;
    const source_path = document.getElementById('edit-source').value;
    const dest_type = document.getElementById('edit-dest-type').value;
    const dropbox_path = document.getElementById('edit-dest').value;
    const dest_path = document.getElementById('edit-dest-path').value;
    const schedule_type = document.getElementById('edit-schedule').value;
    const bidirectional = document.getElementById('edit-bidirectional').value === '1';
    const night_only = document.getElementById('edit-night_only')?.checked || false;
    const exclusions_text = document.getElementById('edit-exclusions').value;
    const exclusions = exclusions_text.split('\n').filter(e => e.trim());

    const result = await apiRequest(`/backups/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
            name, source_path,
            destination_type: dest_type,
            destination_path: dest_type === 'dropbox' ? dropbox_path : dest_path,
            dropbox_path,
            schedule_type, exclusions, bidirectional, night_only
        })
    });

    if (result?.id) {
        document.getElementById('backup-modal').classList.add('hidden');
        loadBackups();
    }
}

async function deleteBackup(id) {
    if (!confirm('Supprimer cette sauvegarde?')) return;

    const result = await apiRequest(`/backups/${id}`, { method: 'DELETE' });
    if (result?.message) {
        showToast('Sauvegarde supprimée', 'success');
        loadBackups();
    }
}

async function loadConnections() {
    const result = await apiRequest('/backups/connections');
    if (!result) return;

    const container = document.getElementById('connections-list');
    container.innerHTML = result.remotes.map(remote => `
        <div class="connection-item">
            <span class="name">${escapeHtml(remote)}</span>
            <span class="status">✓ Connecté</span>
        </div>
    `).join('');
}

async function loadLogs() {
    const logs = await apiRequest('/logs');
    const container = document.getElementById('logs-list');
    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="empty-state">Aucun rapport d\'erreur</div>';
        return;
    }
    container.innerHTML = logs.map(log => `
        <div class="log-item">
            <div class="log-header">
                <span class="log-backup">${escapeHtml(log.backup_name)}</span>
                <span class="log-date">${new Date(log.created_at).toLocaleString()}</span>
            </div>
            <div class="log-message">${escapeHtml(log.message)}</div>
            ${log.error_details ? `<div class="log-error">${escapeHtml(log.error_details)}</div>` : ''}
        </div>
    `).join('');
}

function selectBrowseEntry(el) {
    document.querySelectorAll('#browse-entries .selected').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
}

async function clearLogs() {
    if (!confirm('Effacer tous les logs?')) return;
    await apiRequest('/logs/clear', { method: 'POST' });
    loadLogs();
}

// Expand/collapse state tracking
const expandedBackups = new Set();
const eventSources = {};

function toggleExpand(id) {
    const details = document.getElementById(`details-${id}`);
    const btn = document.querySelector(`.backup-item[data-id="${id}"] .btn-expand`);
    if (!details) return;

    if (expandedBackups.has(id)) {
        details.classList.add('hidden');
        expandedBackups.delete(id);
        if (btn) btn.textContent = '▶';
        if (eventSources[id]) {
            eventSources[id].close();
            delete eventSources[id];
        }
    } else {
        details.classList.remove('hidden');
        expandedBackups.add(id);
        if (btn) btn.textContent = '▼';
        const item = document.querySelector(`.backup-item[data-id="${id}"]`);
        const isRunning = item && (item.classList.contains('running') || item.dataset.started);
        if (isRunning) {
            connectProgressSSE(id);
        }
    }
}

function connectProgressSSE(id) {
    if (eventSources[id]) {
        eventSources[id].close();
    }
    const fileEl = document.getElementById(`current-file-${id}`);
    const transferEl = document.getElementById(`transfer-info-${id}`);
    const transferredEl = document.getElementById(`transferred-${id}`);
    const skippedEl = document.getElementById(`skipped-${id}`);
    const failedEl = document.getElementById(`failed-${id}`);

    const cats = { transferred: transferredEl, skipped: skippedEl, failed: failedEl };
    Object.values(cats).forEach(el => { if (el) el.innerHTML = '<div class="files-placeholder">Connexion...</div>'; });

    const es = new EventSource(`/api/backups/${id}/stream`);
    eventSources[id] = es;

    es.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.done) {
                es.close();
                delete eventSources[id];
                if (fileEl) fileEl.textContent = '';
                if (transferEl) transferEl.textContent = '';
                ['transferred', 'skipped', 'failed'].forEach(k => {
                    const el = document.getElementById(`${k}-${id}`);
                    if (el) {
                        const items = data[k] || [];
                        el.innerHTML = items.length
                            ? items.map(l => `<div class="file-line">${escapeHtml(l)}</div>`).join('')
                            : '<div class="files-placeholder">Aucun</div>';
                    }
                });
                return;
            }
            if (data.current_file && fileEl) {
                fileEl.textContent = '📄 ' + data.current_file;
            }
            if (data.transfer && transferEl) {
                transferEl.textContent = data.transfer;
            }
            ['transferred', 'skipped', 'failed'].forEach(k => {
                const el = document.getElementById(`${k}-${id}`);
                if (el && data[k] && data[k].length > 0) {
                    el.innerHTML = data[k].map(l => `<div class="file-line">${escapeHtml(l)}</div>`).join('');
                    el.scrollTop = el.scrollHeight;
                }
            });
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };

    es.onerror = () => {
        es.close();
        delete eventSources[id];
        Object.entries(cats).forEach(([k, el]) => {
            if (el) el.innerHTML = '<div class="files-placeholder">Flux déconnecté</div>';
        });
    };
}

// Clean up SSE on page unload
window.addEventListener('beforeunload', () => {
    Object.values(eventSources).forEach(es => es.close());
});

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();

    // Auth forms
    document.getElementById('login-form').addEventListener('submit', login);
    document.getElementById('register-form').addEventListener('submit', register);

    // Backup forms
    document.getElementById('backup-form').addEventListener('submit', createBackup);
    document.getElementById('edit-backup-form').addEventListener('submit', saveBackupEdit);

    // Navigation
    document.querySelectorAll('.nav-item[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => showTab(btn.dataset.tab));
    });

    // New backup button
    document.getElementById('new-backup-btn').addEventListener('click', () => {
        document.getElementById('backup-form').reset();
        document.getElementById('backup-form-panel').classList.remove('hidden');
        document.getElementById('dest-type').value = 'dropbox';
        toggleDestType('dropbox');
        const exclusionsEl = document.getElementById('exclusions');
        if (!exclusionsEl.value) {
            exclusionsEl.value = '.DS_Store\nThumbs.db\n.~lock.*\n~$*\n*.tmp\n*.temp\ndesktop.ini\nDesktop.ini';
        }
    });

    // Cancel backup form
    document.getElementById('cancel-backup-form').addEventListener('click', () => {
        document.getElementById('backup-form-panel').classList.add('hidden');
    });

    // Logout
    document.getElementById('logout-btn').addEventListener('click', logout);

    // Logs
    document.getElementById('clear-logs-btn').addEventListener('click', clearLogs);

    // Modal close
    document.getElementById('modal-close').addEventListener('click', () => {
        document.getElementById('backup-modal').classList.add('hidden');
    });

    document.getElementById('backup-modal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('backup-modal')) {
            document.getElementById('backup-modal').classList.add('hidden');
        }
    });

    // Test connection
    document.getElementById('test-connection-btn').addEventListener('click', async () => {
        const status = document.getElementById('auth-status');
        status.textContent = 'Test en cours...';
        status.style.color = 'var(--text-secondary)';
        
        try {
            const result = await apiRequest('/backups/connections/check', { method: 'POST', body: JSON.stringify({ remote: 'dropbox' }) });
            console.log('Connection check result:', result);
            
            if (result?.valid) {
                status.textContent = '✓ Connecté à Dropbox';
                status.style.color = 'var(--success)';
            } else {
                status.textContent = '✗ Non connecté';
                status.style.color = 'var(--danger)';
            }
        } catch (err) {
            console.error('Connection check error:', err);
            status.textContent = '✗ Erreur: ' + err.message;
            status.style.color = 'var(--danger)';
        }
    });

    // Destination type toggle
    function toggleDestType(type) {
        document.querySelector('.dest-dropbox-group').classList.toggle('hidden', type !== 'dropbox');
        document.querySelector('.dest-path-group').classList.toggle('hidden', type === 'dropbox');
    }
    function toggleEditDestType(type) {
        document.querySelector('.edit-dest-dropbox-group').classList.toggle('hidden', type !== 'dropbox');
        document.querySelector('.edit-dest-path-group').classList.toggle('hidden', type === 'dropbox');
    }
    document.getElementById('dest-type').addEventListener('change', (e) => toggleDestType(e.target.value));
    document.getElementById('edit-dest-type').addEventListener('change', (e) => toggleEditDestType(e.target.value));
    toggleDestType('dropbox');

    // Browse functionality
    let browseTargetId = null;
    function openBrowser(targetId) {
        browseTargetId = targetId;
        document.getElementById('browse-modal').classList.remove('hidden');
        loadBrowseEntries('');
    }
    document.querySelectorAll('.browse-btn').forEach(btn => {
        btn.addEventListener('click', () => openBrowser(btn.dataset.target));
    });
    document.getElementById('browse-modal-close').addEventListener('click', () => {
        document.getElementById('browse-modal').classList.add('hidden');
    });
    document.getElementById('browse-cancel-btn').addEventListener('click', () => {
        document.getElementById('browse-modal').classList.add('hidden');
    });
    document.getElementById('browse-up-btn').addEventListener('click', () => {
        const current = document.getElementById('browse-current-path').value;
        const parent = current.substring(0, current.lastIndexOf('\\'));
        if (parent && parent.length >= 2) {
            loadBrowseEntries(parent);
        } else {
            loadBrowseEntries('');
        }
    });
    document.getElementById('browse-select-btn').addEventListener('click', () => {
        const selected = document.querySelector('#browse-entries .selected');
        if (selected) {
            document.getElementById(browseTargetId).value = selected.dataset.path;
            document.getElementById('browse-modal').classList.add('hidden');
        }
    });

    // Event delegation for browse entries
    document.getElementById('browse-entries').addEventListener('click', (e) => {
        const entry = e.target.closest('.browse-entry');
        if (!entry) return;
        if (entry.classList.contains('browse-up')) {
            loadBrowseEntries(entry.dataset.path);
        } else {
            document.querySelectorAll('#browse-entries .selected').forEach(el => el.classList.remove('selected'));
            entry.classList.add('selected');
        }
    });
    document.getElementById('browse-entries').addEventListener('dblclick', (e) => {
        const entry = e.target.closest('.browse-entry');
        if (!entry || entry.classList.contains('browse-up')) return;
        loadBrowseEntries(entry.dataset.path);
    });

    async function loadBrowseEntries(path) {
        const result = await apiRequest('/backups/browse', {
            method: 'POST',
            body: JSON.stringify({ path })
        });
        if (!result) return;
        const container = document.getElementById('browse-entries');
        const pathInput = document.getElementById('browse-current-path');
        if (result.drives) {
            pathInput.value = 'Poste de travail';
            container.innerHTML = result.drives.map(d => `
                <div class="browse-entry" data-path="${d}">
                    <span>💾 ${d}</span>
                </div>
            `).join('');
        } else {
            pathInput.value = result.current || '';
            let html = '';
            if (result.parent && result.parent !== result.current) {
                html += `<div class="browse-entry browse-up" data-path="${result.parent}">
                    <span>⬆ ..</span>
                </div>`;
            }
            html += (result.entries || []).map(e => `
                <div class="browse-entry" data-path="${e}">
                    <span>📁 ${e}</span>
                </div>
            `).join('');
            container.innerHTML = html;
        }
    }

    // Screen switching
    document.getElementById('show-register').addEventListener('click', (e) => {
        e.preventDefault();
        showScreen('register-screen');
    });

    document.getElementById('show-login').addEventListener('click', (e) => {
        e.preventDefault();
        showScreen('login-screen');
    });

    // Export backups
    document.getElementById('export-backups-btn').addEventListener('click', async () => {
        const backups = await apiRequest('/backups/export');
        if (!backups) return;
        const blob = new Blob([JSON.stringify(backups, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'rclone-backups-' + new Date().toISOString().slice(0,10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    });

    // Import backups
    let importData = [];
    document.getElementById('import-backups-btn').addEventListener('click', () => {
        importData = [];
        document.getElementById('import-file-section').classList.remove('hidden');
        document.getElementById('import-list-section').classList.add('hidden');
        document.getElementById('import-result').classList.add('hidden');
        document.getElementById('import-file-input').value = '';
        document.getElementById('import-modal').classList.remove('hidden');
    });

    document.getElementById('import-modal-close').addEventListener('click', () => {
        document.getElementById('import-modal').classList.add('hidden');
    });

    document.getElementById('import-file-input').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                importData = JSON.parse(evt.target.result);
                if (!Array.isArray(importData)) {
                    alert('Format de fichier invalide');
                    return;
                }
                showImportList();
            } catch {
                alert('Fichier JSON invalide');
            }
        };
        reader.readAsText(file);
    });

    function showImportList() {
        const container = document.getElementById('import-backups-list');
        container.innerHTML = importData.map((b, i) => `
            <label style="display: flex; align-items: center; gap: 10px; padding: 10px; border-bottom: 1px solid var(--border); cursor: pointer;">
                <input type="checkbox" class="import-check" data-index="${i}" checked style="width: 18px; height: 18px; cursor: pointer;">
                <span><strong>${escapeHtml(b.name)}</strong><br><small style="color: var(--text-secondary);">${escapeHtml(b.source_path)} → ${escapeHtml(b.dropbox_path)}</small></span>
            </label>
        `).join('');
        document.getElementById('import-file-section').classList.add('hidden');
        document.getElementById('import-list-section').classList.remove('hidden');
    }

    document.getElementById('select-all-import-btn').addEventListener('click', () => {
        const checkboxes = document.querySelectorAll('.import-check');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allChecked);
    });

    document.getElementById('cancel-import-btn').addEventListener('click', () => {
        document.getElementById('import-file-section').classList.remove('hidden');
        document.getElementById('import-list-section').classList.add('hidden');
        document.getElementById('import-result').classList.add('hidden');
        document.getElementById('import-file-input').value = '';
        importData = [];
    });

    document.getElementById('confirm-import-btn').addEventListener('click', async () => {
        const checkboxes = document.querySelectorAll('.import-check:checked');
        const selected = Array.from(checkboxes).map(cb => parseInt(cb.dataset.index));

        if (selected.length === 0) {
            alert('Sélectionnez au moins une sauvegarde');
            return;
        }

        const result = await apiRequest('/backups/import', {
            method: 'POST',
            body: JSON.stringify({ backups: importData, selected: selected })
        });

        if (result) {
            const msg = `${result.imported} importée(s), ${result.skipped} ignorée(s)` + (result.errors.length ? '<br>' + result.errors.join('<br>') : '');
            document.getElementById('import-result').innerHTML = msg;
            document.getElementById('import-result').classList.remove('hidden');
            if (result.imported > 0) {
                loadBackups();
            }
        }
    });
});
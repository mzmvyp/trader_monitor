// static/js/dashboard.js - JavaScript principal do Dashboard

// ==================== ESTADO DA APLICAÇÃO ====================
var DashboardApp = {
    charts: {},
    updateInterval: null,
    isSystemRunning: false,
    lastDataUpdate: null,
    debugMode: false,
    
    // Configurações
    config: {
        updateInterval: 5000, // 5 segundos
        debugMaxLines: 100,
        chartAnimationDuration: 300
    }
};

// ==================== FUNÇÕES DE DEBUG ====================
function debugLog(message, data) {
    var timestamp = new Date().toLocaleTimeString();
    console.log('[DASHBOARD]', timestamp, message, data || '');
    
    if (DashboardApp.debugMode) {
        var debugDiv = document.getElementById('debug-info');
        if (debugDiv) {
            var logEntry = document.createElement('div');
            logEntry.innerHTML = timestamp + ' - ' + message + 
                (data ? ': ' + JSON.stringify(data).substring(0, 100) + '...' : '');
            
            debugDiv.appendChild(logEntry);
            
            // Limitar número de linhas
            var lines = debugDiv.children;
            if (lines.length > DashboardApp.config.debugMaxLines) {
                debugDiv.removeChild(lines[0]);
            }
            
            debugDiv.scrollTop = debugDiv.scrollHeight;
        }
    }
}

function toggleDebug() {
    DashboardApp.debugMode = !DashboardApp.debugMode;
    var debugSection = document.getElementById('debug-section');
    
    if (debugSection) {
        debugSection.style.display = DashboardApp.debugMode ? 'block' : 'none';
        
        if (DashboardApp.debugMode) {
            document.getElementById('debug-info').innerHTML = 
                '<div>Debug mode ativado - ' + new Date().toLocaleTimeString() + '</div>';
            debugLog('Debug mode ativado');
        }
    }
}

// ==================== FUNÇÕES AUXILIARES ====================
function formatCurrency(amount) {
    if (!amount && amount !== 0) return '$0.00';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function formatPercentage(value, decimals) {
    decimals = decimals || 1;
    if (!value && value !== 0) return '0.0%';
    return value.toFixed(decimals) + '%';
}

function formatVolume(volume) {
    if (!volume || volume === 0) return 'N/A';
    if (volume >= 1000000000) {
        return '$' + (volume / 1000000000).toFixed(1) + 'B';
    }
    return '$' + (volume / 1000000).toFixed(1) + 'M';
}

function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    return new Date(timestamp).toLocaleString('pt-BR');
}

function formatTime(timestamp) {
    if (!timestamp) return '-';
    return new Date(timestamp).toLocaleTimeString('pt-BR');
}

function getTimeElapsed(timestamp) {
    if (!timestamp) return '-';
    var now = new Date();
    var time = new Date(timestamp);
    var diffMs = now - time;
    var diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) {
        return 'agora';
    } else if (diffMins < 60) {
        return diffMins + ' min atrás';
    } else if (diffMins < 1440) {
        return Math.floor(diffMins / 60) + 'h atrás';
    } else {
        return Math.floor(diffMins / 1440) + 'd atrás';
    }
}

// ==================== FUNÇÕES DE FORMATAÇÃO DE TRADING ====================
function formatPatternName(pattern) {
    if (!pattern) return '';
    return pattern.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, function(l) {
        return l.toUpperCase();
    });
}

function getPatternColor(pattern) {
    var colors = {
        'DOUBLE_BOTTOM': 'success',
        'HEAD_AND_SHOULDERS': 'warning',
        'TRIANGLE_BREAKOUT_UP': 'info',
        'TRIANGLE_BREAKOUT_DOWN': 'secondary',
        'INDICATORS_BUY': 'primary',
        'INDICATORS_SELL': 'danger'
    };
    return colors[pattern] || 'secondary';
}

function getStatusClass(status) {
    var classes = {
        'ACTIVE': 'status-active',
        'HIT_TARGET': 'status-target', 
        'HIT_STOP': 'status-stop',
        'EXPIRED': 'status-expired'
    };
    return classes[status] || 'status-active';
}

function getStatusText(status) {
    var texts = {
        'ACTIVE': 'Ativo',
        'HIT_TARGET': 'Target',
        'HIT_STOP': 'Stop',
        'EXPIRED': 'Expirado'
    };
    return texts[status] || status;
}

function formatIndicatorValue(key, value) {
    if (!value && value !== 0) return 'N/A';
    
    if (key.includes('SMA') || key.includes('EMA')) {
        return formatCurrency(value);
    } else {
        return value.toFixed(2);
    }
}

function getIndicatorSignal(key, value) {
    if (!value && value !== 0) return 'neutral';
    
    // RSI
    if (key === 'RSI') {
        if (value < 30) return 'bullish';
        if (value > 70) return 'bearish';
        return 'neutral';
    }
    
    // Stochastic
    if (key === 'STOCH_K') {
        if (value < 20) return 'bullish';
        if (value > 80) return 'bearish';
        return 'neutral';
    }
    
    // MACD
    if (key === 'MACD') {
        return value > 0 ? 'bullish' : 'bearish';
    }
    
    return 'neutral';
}

// ==================== API CALLS ====================
function makeAPICall(url, options) {
    debugLog('API Call', {url: url, method: options?.method || 'GET'});
    options = options || {};
    
    return fetch(url, {
        method: options.method || 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        body: options.body ? JSON.stringify(options.body) : undefined
    })
    .then(function(response) {
        debugLog('API Response', {url: url, status: response.status, ok: response.ok});
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.status);
        }
        return response.json();
    })
    .catch(function(error) {
        debugLog('API Error', {url: url, error: error.message});
        showNotification('Erro na comunicação com o servidor: ' + url, 'danger');
        throw error;
    });
}

// ==================== NOTIFICAÇÕES ====================
function showNotification(message, type, duration) {
    debugLog('Notification', {message: message, type: type});
    duration = duration || 5000;
    
    // Remove notificações existentes
    var existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }
    
    // Cria nova notificação
    var notification = document.createElement('div');
    notification.className = 'notification alert alert-' + type + ' position-fixed fade-in';
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    
    // Determina ícone
    var iconClass = 'exclamation';
    if (type === 'success') {
        iconClass = 'check';
    } else if (type === 'danger') {
        iconClass = 'times';
    } else if (type === 'info') {
        iconClass = 'info';
    }
    
    notification.innerHTML = 
        '<div class="d-flex align-items-center">' +
            '<i class="fas fa-' + iconClass + '-circle me-2"></i>' +
            '<span>' + message + '</span>' +
            '<button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>' +
        '</div>';
    
    document.body.appendChild(notification);
    
    // Remove automaticamente
    setTimeout(function() {
        if (notification.parentElement) {
            notification.style.opacity = '0';
            setTimeout(function() {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }
    }, duration);
}

// ==================== INICIALIZAÇÃO DOS GRÁFICOS ====================
function initializeCharts() {
    try {
        debugLog('Inicializando gráficos...');
        
        // Gráfico principal (overview)
        var overviewCtx = document.getElementById('overviewChart').getContext('2d');
        DashboardApp.charts.overview = new Chart(overviewCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Preço Bitcoin (USD)',
                    data: [],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#007bff',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                return 'Preço: ' + formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return formatCurrency(value);
                            }
                        },
                        grid: {
                            color: 'rgba(0,0,0,0.1)'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(0,0,0,0.1)'
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });

        // Gráfico de estatísticas de padrões
        var patternCtx = document.getElementById('patternStatsChart').getContext('2d');
        DashboardApp.charts.patterns = new Chart(patternCtx, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        '#28a745', '#dc3545', '#ffc107', 
                        '#17a2b8', '#6f42c1', '#fd7e14'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff',
                    hoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + formatPercentage(context.parsed) + ' sucesso';
                            }
                        }
                    }
                }
            }
        });

        // Gráfico de volume de sinais
        var volumeCtx = document.getElementById('volumeChart').getContext('2d');
        DashboardApp.charts.volume = new Chart(volumeCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Sinais por Padrão',
                    data: [],
                    backgroundColor: 'rgba(0, 123, 255, 0.8)',
                    borderColor: '#007bff',
                    borderWidth: 1,
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + context.parsed.y + ' sinais';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        },
                        grid: {
                            color: 'rgba(0,0,0,0.1)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        debugLog('Gráficos inicializados com sucesso');
    } catch (error) {
        debugLog('Erro ao inicializar gráficos', error);
        showNotification('Erro ao inicializar gráficos', 'danger');
    }
}

// ==================== EVENT LISTENERS ====================
function setupEventListeners() {
    try {
        // Botões de controle
        var startBtn = document.getElementById('start-bitcoin');
        var stopBtn = document.getElementById('stop-bitcoin');
        
        if (startBtn) {
            startBtn.addEventListener('click', startBitcoinStream);
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', stopBitcoinStream);
        }
        
        debugLog('Event listeners configurados');
    } catch (error) {
        debugLog('Erro ao configurar event listeners', error);
    }
}

// ==================== CONTROLES BITCOIN ====================
function startBitcoinStream() {
    debugLog('Iniciando Bitcoin stream...');
    var startBtn = document.getElementById('start-bitcoin');
    
    if (startBtn) {
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Iniciando...';
    }
    
    makeAPICall('/api/bitcoin/start-stream', { method: 'POST' })
        .then(function(data) {
            debugLog('Resposta start stream', data);
            if (data.status === 'started') {
                DashboardApp.isSystemRunning = true;
                updateSystemStatus('running');
                showNotification('Pipeline Bitcoin iniciado!', 'success');
            } else {
                showNotification('Erro: ' + (data.message || 'Status inesperado'), 'warning');
            }
        })
        .catch(function(error) {
            debugLog('Erro ao iniciar stream', error);
            showNotification('Erro ao iniciar pipeline Bitcoin', 'danger');
        })
        .finally(function() {
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.innerHTML = '<i class="fas fa-play"></i> Iniciar Bitcoin';
            }
        });
}

function stopBitcoinStream() {
    debugLog('Parando Bitcoin stream...');
    var stopBtn = document.getElementById('stop-bitcoin');
    
    if (stopBtn) {
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Parando...';
    }
    
    makeAPICall('/api/bitcoin/stop-stream', { method: 'POST' })
        .then(function(data) {
            debugLog('Resposta stop stream', data);
            if (data.status === 'stopped') {
                DashboardApp.isSystemRunning = false;
                updateSystemStatus('stopped');
                showNotification('Pipeline Bitcoin parado!', 'warning');
            } else {
                showNotification('Erro: ' + (data.message || 'Status inesperado'), 'warning');
            }
        })
        .catch(function(error) {
            debugLog('Erro ao parar stream', error);
            showNotification('Erro ao parar pipeline Bitcoin', 'danger');
        })
        .finally(function() {
            if (stopBtn) {
                stopBtn.disabled = false;
                stopBtn.innerHTML = '<i class="fas fa-stop"></i> Parar Bitcoin';
            }
        });
}

// ==================== ATUALIZAÇÃO DE STATUS ====================
function updateSystemStatus(status) {
    try {
        var statusDot = document.getElementById('system-status-dot');
        var statusText = document.getElementById('system-status-text');
        
        if (statusDot && statusText) {
            if (status === 'running') {
                statusDot.className = 'status-dot status-running';
                statusText.textContent = 'Sistema Ativo';
            } else {
                statusDot.className = 'status-dot status-stopped';
                statusText.textContent = 'Sistema Parado';
            }
        }
        
        debugLog('Status atualizado para: ' + status);
    } catch (error) {
        debugLog('Erro ao atualizar status', error);
    }
}

// ==================== ATUALIZAÇÕES EM TEMPO REAL ====================
function startRealTimeUpdates() {
    debugLog('Iniciando atualizações em tempo real...');
    
    // Primeira atualização imediata
    updateDashboardData();
    
    // Configurar intervalo de atualizações
    DashboardApp.updateInterval = setInterval(function() {
        updateDashboardData();
    }, DashboardApp.config.updateInterval);
}

function updateDashboardData() {
    debugLog('Buscando dados do dashboard...');
    
    makeAPICall('/api/integrated/dashboard-data')
        .then(function(data) {
            debugLog('Dados recebidos', {
                bitcoin_data_count: data.bitcoin?.recent_data?.length || 0,
                trading_signals_count: data.trading?.recent_signals?.length || 0,
                system_healthy: data.integrated_status?.system_healthy
            });
            
            DashboardApp.lastDataUpdate = new Date();
            
            if (data && !data.error) {
                updateQuickStats(data);
                updateOverviewChart(data.bitcoin.recent_data || []);
                updateBitcoinTab(data.bitcoin);
                updateTradingTab(data.trading);
                updateSystemInfo(data.integrated_status);
                updateLastUpdate();
                
                // Atualizar status baseado nos dados
                if (data.bitcoin.streaming) {
                    DashboardApp.isSystemRunning = true;
                    updateSystemStatus('running');
                } else {
                    DashboardApp.isSystemRunning = false;
                    updateSystemStatus('stopped');
                }
            } else {
                debugLog('Dados inválidos ou erro', data);
                if (data && data.error) {
                    showNotification('Erro nos dados: ' + data.error, 'warning');
                }
            }
        })
        .catch(function(error) {
            debugLog('Erro ao atualizar dados', error);
            // Não mostrar notificação para cada erro de conexão
            // showNotification('Erro de conexão com o servidor', 'danger');
        });
}

// ==================== INICIALIZAÇÃO ====================
document.addEventListener('DOMContentLoaded', function() {
    debugLog('Dashboard inicializando...');
    
    // Configurar tudo
    initializeCharts();
    setupEventListeners();
    startRealTimeUpdates();
    loadInitialData();
    
    debugLog('Dashboard inicializado com sucesso');
});

// ==================== CLEANUP ====================
window.addEventListener('beforeunload', function() {
    if (DashboardApp.updateInterval) {
        clearInterval(DashboardApp.updateInterval);
        debugLog('Interval de atualização limpo');
    }
});

// ==================== CARREGAMENTO INICIAL ====================
function loadInitialData() {
    debugLog('Carregando dados iniciais...');
    
    // Carregar sinais recentes
    updateRecentSignals();
    
    // Configurar atualização dos sinais recentes (mais frequente)
    setInterval(updateRecentSignals, 10000);
}
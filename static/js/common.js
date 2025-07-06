// static/js/common.js - Funções JavaScript Compartilhadas

// ==================== UTILITY FUNCTIONS ====================

// Formatação de números
function formatNumber(num, decimals) {
    decimals = decimals || 2;
    if (num === null || num === undefined) return '0.00';
    return num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// Formatação de moeda
function formatCurrency(amount) {
    if (amount === null || amount === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Formatação de porcentagem
function formatPercentage(value, decimals) {
    decimals = decimals || 1;
    if (value === null || value === undefined) return '0.0%';
    return value.toFixed(decimals) + '%';
}

// Formatação de volume (milhões)
function formatVolume(volume) {
    if (!volume || volume === 0) return 'N/A';
    return '$' + (volume / 1000000).toFixed(1) + 'M';
}

// ==================== NOTIFICATION SYSTEM ====================

function showNotification(message, type, duration) {
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

// ==================== API HELPERS ====================

function makeAPICall(url, options) {
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
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .catch(function(error) {
        console.error('API Error:', error);
        showNotification('Erro na comunicação com o servidor', 'danger');
        throw error;
    });
}

// ==================== TIME HELPERS ====================

function getTimeElapsed(timestamp) {
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

function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    return new Date(timestamp).toLocaleString('pt-BR');
}

function formatTime(timestamp) {
    if (!timestamp) return '-';
    return new Date(timestamp).toLocaleTimeString('pt-BR');
}

// ==================== PATTERN HELPERS ====================

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

// ==================== STATUS HELPERS ====================

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

function getSignalColor(signal) {
    var colors = {
        'bullish': 'success',
        'bearish': 'danger',
        'neutral': 'secondary'
    };
    return colors[signal] || 'secondary';
}

// ==================== CHART HELPERS ====================

function getChartColors() {
    return {
        primary: '#007bff',
        success: '#28a745',
        warning: '#ffc107',
        danger: '#dc3545',
        info: '#17a2b8',
        secondary: '#6c757d'
    };
}

function createGradient(ctx, color1, color2) {
    var gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2);
    return gradient;
}

// ==================== TRADING HELPERS ====================

function calculateProgress(signal) {
    if (!signal || !signal.entry_price || !signal.target_price || !signal.current_price) {
        return 0;
    }
    
    var total = signal.target_price - signal.entry_price;
    var current = signal.current_price - signal.entry_price;
    var progress = (current / total) * 100;
    
    return Math.max(0, Math.min(100, progress));
}

function calculateRiskReward(entry, target, stop) {
    if (!entry || !target || !stop) return 0;
    
    var reward = Math.abs(target - entry);
    var risk = Math.abs(entry - stop);
    
    return risk > 0 ? (reward / risk) : 0;
}

function getProfitLossClass(value) {
    if (value > 0) return 'profit-positive';
    if (value < 0) return 'profit-negative';
    return 'text-muted';
}

// ==================== INDICATOR HELPERS ====================

function formatIndicatorValue(key, value) {
    if (!value && value !== 0) return 'N/A';
    
    if (key.includes('SMA') || key.includes('EMA') || key.includes('BB_')) {
        return formatCurrency(value);
    } else if (key === 'BB_Position') {
        return formatPercentage(value * 100);
    } else if (key.includes('VOLUME')) {
        return formatVolume(value);
    } else {
        return formatNumber(value, 2);
    }
}

function getIndicatorSignal(key, value, previousValue) {
    if (!value && value !== 0) return 'neutral';
    
    // RSI
    if (key === 'RSI') {
        if (value < 30) return 'bullish';
        if (value > 70) return 'bearish';
        return 'neutral';
    }
    
    // Stochastic
    if (key === 'STOCH_K' || key === 'STOCH_D') {
        if (value < 20) return 'bullish';
        if (value > 80) return 'bearish';
        return 'neutral';
    }
    
    // MACD
    if (key === 'MACD') {
        return value > 0 ? 'bullish' : 'bearish';
    }
    
    // Trend (comparação com valor anterior)
    if (previousValue && value !== previousValue) {
        return value > previousValue ? 'bullish' : 'bearish';
    }
    
    return 'neutral';
}

// ==================== VALIDATION HELPERS ====================

function validateNumber(value, min, max) {
    var num = parseFloat(value);
    if (isNaN(num)) return false;
    if (min !== undefined && num < min) return false;
    if (max !== undefined && num > max) return false;
    return true;
}

function validatePrice(price) {
    return validateNumber(price, 0);
}

function validatePercentage(percentage) {
    return validateNumber(percentage, 0, 100);
}

// ==================== LOCAL STORAGE HELPERS ====================

function saveToStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
        return true;
    } catch (error) {
        console.error('Error saving to localStorage:', error);
        return false;
    }
}

function loadFromStorage(key, defaultValue) {
    try {
        var data = localStorage.getItem(key);
        return data ? JSON.parse(data) : defaultValue;
    } catch (error) {
        console.error('Error loading from localStorage:', error);
        return defaultValue;
    }
}

function removeFromStorage(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch (error) {
        console.error('Error removing from localStorage:', error);
        return false;
    }
}

// ==================== KEYBOARD SHORTCUTS ====================

function setupKeyboardShortcuts(shortcuts) {
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey || event.metaKey) {
            var key = event.key.toLowerCase();
            if (shortcuts[key]) {
                event.preventDefault();
                shortcuts[key]();
            }
        }
    });
}

// ==================== LOADING STATES ====================

function showLoading(elementId, message) {
    message = message || 'Carregando...';
    var element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = 
            '<div class="loading-spinner">' +
                '<i class="fas fa-spinner fa-spin"></i> ' + message +
            '</div>';
    }
}

function hideLoading(elementId) {
    var element = document.getElementById(elementId);
    if (element) {
        var spinner = element.querySelector('.loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }
}

// ==================== TABLE HELPERS ====================

function createTableRow(data, columns) {
    var row = '<tr>';
    for (var i = 0; i < columns.length; i++) {
        var column = columns[i];
        var value = data[column.key];
        
        if (column.formatter) {
            value = column.formatter(value, data);
        }
        
        var cellClass = column.class ? ' class="' + column.class + '"' : '';
        row += '<td' + cellClass + '>' + (value || '') + '</td>';
    }
    row += '</tr>';
    return row;
}

function updateTable(tableBodyId, data, columns) {
    var tbody = document.getElementById(tableBodyId);
    if (!tbody) return;
    
    if (!data || data.length === 0) {
        tbody.innerHTML = 
            '<tr><td colspan="' + columns.length + '" class="text-center text-muted">' +
                'Nenhum dado disponível' +
            '</td></tr>';
        return;
    }
    
    var html = '';
    for (var i = 0; i < data.length; i++) {
        html += createTableRow(data[i], columns);
    }
    tbody.innerHTML = html;
}

// ==================== ANIMATION HELPERS ====================

function animateValue(element, start, end, duration, formatter) {
    duration = duration || 1000;
    formatter = formatter || function(val) { return val; };
    
    var startTime = performance.now();
    var startValue = parseFloat(start) || 0;
    var endValue = parseFloat(end) || 0;
    var difference = endValue - startValue;
    
    function updateValue(currentTime) {
        var elapsed = currentTime - startTime;
        var progress = Math.min(elapsed / duration, 1);
        
        // Easing function (ease-out)
        progress = 1 - Math.pow(1 - progress, 3);
        
        var currentValue = startValue + (difference * progress);
        element.textContent = formatter(currentValue);
        
        if (progress < 1) {
            requestAnimationFrame(updateValue);
        }
    }
    
    requestAnimationFrame(updateValue);
}

// ==================== INITIALIZATION ====================

// Setup global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showNotification('Ocorreu um erro inesperado', 'danger');
});

// Setup global keyboard shortcuts
document.addEventListener('DOMContentLoaded', function() {
    setupKeyboardShortcuts({
        'r': function() {
            location.reload();
        },
        's': function() {
            showNotification('Atalho: Ctrl+S detectado', 'info');
        }
    });
});

// Export functions for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatNumber: formatNumber,
        formatCurrency: formatCurrency,
        formatPercentage: formatPercentage,
        showNotification: showNotification,
        makeAPICall: makeAPICall,
        getTimeElapsed: getTimeElapsed,
        formatPatternName: formatPatternName
    };
}
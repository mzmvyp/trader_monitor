// static/js/dashboard-updates.js - Funções de atualização do Dashboard

// ==================== ATUALIZAÇÃO DE ESTATÍSTICAS RÁPIDAS ====================
function updateQuickStats(data) {
    try {
        var currentPrice = 0;
        if (data.bitcoin && data.bitcoin.recent_data && data.bitcoin.recent_data.length > 0) {
            currentPrice = data.bitcoin.recent_data[data.bitcoin.recent_data.length - 1].price;
        }
        
        // Atualizar preço atual
        var priceElement = document.getElementById('current-price');
        if (priceElement) {
            animateValue(priceElement, parseFloat(priceElement.textContent.replace(/[$,]/g, '')) || 0, currentPrice, 1000, formatCurrency);
        }
        
        // Atualizar sinais ativos
        var signalsElement = document.getElementById('active-signals');
        if (signalsElement) {
            animateValue(signalsElement, parseInt(signalsElement.textContent) || 0, data.trading.active_signals || 0, 800);
        }
        
        // Atualizar pontos de dados
        var dataPointsElement = document.getElementById('data-points');
        if (dataPointsElement) {
            animateValue(dataPointsElement, parseInt(dataPointsElement.textContent) || 0, data.integrated_status.total_data_points || 0, 800);
        }
        
        // Calcular e atualizar taxa de sucesso
        var stats = data.trading.pattern_stats || [];
        var totalSuccessful = 0;
        var totalSignals = 0;
        
        for (var i = 0; i < stats.length; i++) {
            totalSuccessful += stats[i].successful_signals || 0;
            totalSignals += stats[i].total_signals || 0;
        }
        
        var successRate = totalSignals > 0 ? (totalSuccessful / totalSignals * 100) : 0;
        var successElement = document.getElementById('success-rate');
        if (successElement) {
            animateValue(successElement, parseFloat(successElement.textContent.replace('%', '')) || 0, successRate, 1000, formatPercentage);
        }
        
        debugLog('Stats atualizadas', {
            currentPrice: currentPrice,
            activeSignals: data.trading.active_signals,
            dataPoints: data.integrated_status.total_data_points,
            successRate: successRate
        });
    } catch (error) {
        debugLog('Erro ao atualizar stats', error);
    }
}

// ==================== ATUALIZAÇÃO DO GRÁFICO PRINCIPAL ====================
function updateOverviewChart(bitcoinData) {
    try {
        if (!bitcoinData || bitcoinData.length === 0) {
            debugLog('Sem dados para o gráfico principal');
            return;
        }
        
        var labels = [];
        var prices = [];
        
        // Pegar os últimos 20 pontos para não sobrecarregar o gráfico
        var displayData = bitcoinData.slice(-20);
        
        for (var i = 0; i < displayData.length; i++) {
            labels.push(formatTime(displayData[i].timestamp));
            prices.push(displayData[i].price);
        }
        
        if (DashboardApp.charts.overview) {
            DashboardApp.charts.overview.data.labels = labels;
            DashboardApp.charts.overview.data.datasets[0].data = prices;
            DashboardApp.charts.overview.update('none');
        }
        
        debugLog('Gráfico principal atualizado', {pontos: prices.length, ultimoPreco: prices[prices.length - 1]});
    } catch (error) {
        debugLog('Erro ao atualizar gráfico principal', error);
    }
}

// ==================== ATUALIZAÇÃO TAB BITCOIN ====================
function updateBitcoinTab(bitcoinData) {
    try {
        // Métricas
        var latestData = null;
        if (bitcoinData.recent_data && bitcoinData.recent_data.length > 0) {
            latestData = bitcoinData.recent_data[bitcoinData.recent_data.length - 1];
        }
        
        if (latestData) {
            // Preço atual
            var priceElement = document.getElementById('bitcoin-price');
            if (priceElement) {
                priceElement.textContent = formatCurrency(latestData.price);
            }
            
            // Mudança 24h
            var changeElement = document.getElementById('bitcoin-change');
            if (changeElement) {
                changeElement.textContent = formatPercentage(latestData.price_change_24h || 0);
                changeElement.className = 'metric-value ' + (latestData.price_change_24h >= 0 ? 'price-up' : 'price-down');
            }
            
            // Volume
            var volumeElement = document.getElementById('bitcoin-volume');
            if (volumeElement) {
                volumeElement.textContent = formatVolume(latestData.volume_24h);
            }
        } else {
            // Valores padrão quando não há dados
            var elements = ['bitcoin-price', 'bitcoin-change', 'bitcoin-volume'];
            var defaults = ['$0.00', '0.00%', '$0M'];
            
            for (var i = 0; i < elements.length; i++) {
                var element = document.getElementById(elements[i]);
                if (element) {
                    element.textContent = defaults[i];
                    element.className = 'metric-value';
                }
            }
        }
        
        // Pontos coletados
        var pointsElement = document.getElementById('bitcoin-points');
        if (pointsElement) {
            pointsElement.textContent = (bitcoinData.recent_data || []).length;
        }
        
        // Tabela de dados
        updateBitcoinTable(bitcoinData.recent_data || []);
        
        debugLog('Tab Bitcoin atualizada');
    } catch (error) {
        debugLog('Erro ao atualizar tab Bitcoin', error);
    }
}

// ==================== ATUALIZAÇÃO TABELA BITCOIN ====================
function updateBitcoinTable(data) {
    try {
        var tbody = document.getElementById('bitcoin-data-table');
        if (!tbody) return;
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Nenhum dado disponível</td></tr>';
            return;
        }
        
        var html = '';
        var displayData = data.slice(-10); // Últimos 10 registros
        
        for (var i = 0; i < displayData.length; i++) {
            var row = displayData[i];
            var changeClass = (row.price_change_24h || 0) >= 0 ? 'price-up' : 'price-down';
            
            html += '<tr>' +
                '<td>' + formatDateTime(row.timestamp) + '</td>' +
                '<td><strong>' + formatCurrency(row.price) + '</strong></td>' +
                '<td><span class="' + changeClass + '">' + formatPercentage(row.price_change_24h || 0) + '</span></td>' +
                '<td>' + formatVolume(row.volume_24h) + '</td>' +
                '<td><span class="badge bg-primary">' + row.source + '</span></td>' +
            '</tr>';
        }
        
        tbody.innerHTML = html;
        debugLog('Tabela Bitcoin atualizada', {registros: data.length});
    } catch (error) {
        debugLog('Erro ao atualizar tabela Bitcoin', error);
    }
}

// ==================== ATUALIZAÇÃO TAB TRADING ====================
function updateTradingTab(tradingData) {
    try {
        updateTradingSignalsTable(tradingData.recent_signals || []);
        updateIndicatorsDisplay(tradingData.indicators || {});
        updateAnalyticsTab(tradingData.pattern_stats || []);
        debugLog('Tab Trading atualizada');
    } catch (error) {
        debugLog('Erro ao atualizar tab Trading', error);
    }
}

// ==================== ATUALIZAÇÃO TABELA DE SINAIS ====================
function updateTradingSignalsTable(signals) {
    try {
        var tbody = document.getElementById('trading-signals-table');
        if (!tbody) return;
        
        if (!signals || signals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Nenhum sinal disponível</td></tr>';
            return;
        }
        
        var html = '';
        var displaySignals = signals.slice(0, 10); // Primeiros 10 sinais
        
        for (var i = 0; i < displaySignals.length; i++) {
            var signal = displaySignals[i];
            var statusClass = getStatusClass(signal.status);
            var patternClass = getPatternColor(signal.pattern_type);
            
            html += '<tr>' +
                '<td><span class="pattern-badge bg-' + patternClass + '">' + formatPatternName(signal.pattern_type) + '</span></td>' +
                '<td>' + formatCurrency(signal.entry_price) + '</td>' +
                '<td>' + formatCurrency(signal.target_price) + '</td>' +
                '<td>' + formatCurrency(signal.stop_loss) + '</td>' +
                '<td><span class="status-badge ' + statusClass + '">' + getStatusText(signal.status) + '</span></td>' +
                '<td>' + (signal.profit_loss && signal.profit_loss !== 0 ? 
                    '<span class="' + getProfitLossClass(signal.profit_loss) + '">' + formatPercentage(signal.profit_loss) + '</span>' : '-') + '</td>' +
            '</tr>';
        }
        
        tbody.innerHTML = html;
        debugLog('Tabela de sinais atualizada', {sinais: signals.length});
    } catch (error) {
        debugLog('Erro ao atualizar tabela de sinais', error);
    }
}

function getProfitLossClass(value) {
    if (value > 0) return 'profit-positive';
    if (value < 0) return 'profit-negative';
    return 'text-muted';
}

// ==================== ATUALIZAÇÃO INDICADORES ====================
function updateIndicatorsDisplay(indicators) {
    try {
        var container = document.getElementById('indicators-display');
        if (!container) return;
        
        var html = '';
        var indicatorKeys = ['RSI', 'MACD', 'SMA_12', 'SMA_30', 'STOCH_K'];
        
        for (var i = 0; i < indicatorKeys.length; i++) {
            var key = indicatorKeys[i];
            var value = indicators[key];
            
            if (value !== undefined && value !== null) {
                var signal = getIndicatorSignal(key, value);
                var signalClass = 'indicator-' + signal;
                var formattedValue = formatIndicatorValue(key, value);
                
                html += 
                    '<div class="indicator-item mb-2">' +
                        '<div class="d-flex justify-content-between align-items-center">' +
                            '<span class="fw-bold">' + key.replace('_', ' ') + '</span>' +
                            '<span class="' + signalClass + '">' + formattedValue + '</span>' +
                        '</div>' +
                        '<div class="mt-1">' +
                            '<small class="text-muted">Sinal: <span class="' + signalClass + '">' + 
                            (signal === 'bullish' ? 'Alta' : signal === 'bearish' ? 'Baixa' : 'Neutro') + '</span></small>' +
                        '</div>' +
                    '</div>';
            }
        }
        
        if (html === '') {
            html = '<div class="text-muted text-center">Coletando dados...</div>';
        }
        
        container.innerHTML = html;
        debugLog('Indicadores atualizados');
    } catch (error) {
        debugLog('Erro ao atualizar indicadores', error);
    }
}

// ==================== ATUALIZAÇÃO TAB ANALYTICS ====================
function updateAnalyticsTab(patternStats) {
    try {
        // Atualizar gráficos
        if (patternStats && patternStats.length > 0) {
            var labels = [];
            var successRates = [];
            var totals = [];
            
            for (var i = 0; i < patternStats.length; i++) {
                labels.push(formatPatternName(patternStats[i].pattern_type));
                successRates.push(patternStats[i].success_rate || 0);
                totals.push(patternStats[i].total_signals || 0);
            }
            
            // Gráfico de taxa de sucesso
            if (DashboardApp.charts.patterns) {
                DashboardApp.charts.patterns.data.labels = labels;
                DashboardApp.charts.patterns.data.datasets[0].data = successRates;
                DashboardApp.charts.patterns.update('none');
            }
            
            // Gráfico de volume
            if (DashboardApp.charts.volume) {
                DashboardApp.charts.volume.data.labels = labels;
                DashboardApp.charts.volume.data.datasets[0].data = totals;
                DashboardApp.charts.volume.update('none');
            }
        }
        
        // Atualizar tabela
        updateAnalyticsTable(patternStats);
        debugLog('Analytics atualizados');
    } catch (error) {
        debugLog('Erro ao atualizar analytics', error);
    }
}

// ==================== ATUALIZAÇÃO TABELA ANALYTICS ====================
function updateAnalyticsTable(stats) {
    try {
        var tbody = document.getElementById('analytics-table');
        if (!tbody) return;
        
        if (!stats || stats.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Nenhuma estatística disponível</td></tr>';
            return;
        }
        
        var html = '';
        for (var i = 0; i < stats.length; i++) {
            var stat = stats[i];
            var successClass = (stat.success_rate || 0) >= 60 ? 'text-success' : 'text-warning';
            
            html += '<tr>' +
                '<td><strong>' + formatPatternName(stat.pattern_type) + '</strong></td>' +
                '<td>' + (stat.total_signals || 0) + '</td>' +
                '<td class="text-success">' + (stat.successful_signals || 0) + '</td>' +
                '<td class="text-danger">' + (stat.failed_signals || 0) + '</td>' +
                '<td><span class="' + successClass + ' fw-bold">' + formatPercentage(stat.success_rate || 0) + '</span></td>' +
                '<td class="text-success">+' + formatPercentage(stat.avg_profit || 0) + '</td>' +
                '<td class="text-danger">' + formatPercentage(stat.avg_loss || 0) + '</td>' +
            '</tr>';
        }
        
        tbody.innerHTML = html;
        debugLog('Tabela de analytics atualizada');
    } catch (error) {
        debugLog('Erro ao atualizar tabela de analytics', error);
    }
}

// ==================== ATUALIZAÇÃO INFORMAÇÕES DO SISTEMA ====================
function updateSystemInfo(status) {
    try {
        var container = document.getElementById('system-info');
        if (!container) return;
        
        var healthIcon = status.system_healthy ? 
            '<i class="fas fa-check-circle text-success"></i>' : 
            '<i class="fas fa-exclamation-triangle text-warning"></i>';
        
        var analysisIcon = status.analysis_ready ? 
            '<i class="fas fa-check-circle text-success"></i>' : 
            '<i class="fas fa-clock text-warning"></i>';
        
        var html = 
            '<div class="row g-3">' +
                '<div class="col-12">' +
                    '<h6 class="mb-3"><i class="fas fa-info-circle text-primary"></i> Status Operacional</h6>' +
                '</div>' +
                '<div class="col-6">' +
                    '<div class="d-flex align-items-center">' +
                        '<strong class="me-2">Pontos de Dados:</strong>' +
                        '<span class="badge bg-primary">' + (status.total_data_points || 0) + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="col-6">' +
                    '<div class="d-flex align-items-center">' +
                        analysisIcon +
                        '<strong class="ms-2">Análise:</strong>' +
                        '<span class="ms-1">' + (status.analysis_ready ? 'Pronta' : 'Aguardando') + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="col-12">' +
                    '<div class="d-flex align-items-center">' +
                        healthIcon +
                        '<strong class="ms-2">Sistema:</strong>' +
                        '<span class="ms-1">' + (status.system_healthy ? 'Saudável' : 'Com Problemas') + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="col-12">' +
                    '<small class="text-muted">' +
                        '<i class="fas fa-clock"></i> Última atualização: ' + formatTime(status.last_update) +
                    '</small>' +
                '</div>' +
            '</div>';
        
        container.innerHTML = html;
    } catch (error) {
        debugLog('Erro ao atualizar informações do sistema', error);
    }
}

// ==================== ATUALIZAÇÃO SINAIS RECENTES ====================
function updateRecentSignals() {
    makeAPICall('/api/trading/signals?limit=5')
        .then(function(signals) {
            var container = document.getElementById('recent-signals');
            if (!container) return;
            
            var html = '';
            
            if (!signals || signals.length === 0) {
                html = '<div class="text-muted text-center"><i class="fas fa-info-circle"></i> Nenhum sinal recente</div>';
            } else {
                for (var i = 0; i < signals.length; i++) {
                    var signal = signals[i];
                    var statusClass = 'signal-' + (signal.status || 'active').toLowerCase();
                    var patternColor = getPatternColor(signal.pattern_type);
                    
                    html += 
                        '<div class="signal-card ' + statusClass + ' p-2 mb-2">' +
                            '<div class="d-flex justify-content-between align-items-center mb-1">' +
                                '<small><strong>' + formatPatternName(signal.pattern_type) + '</strong></small>' +
                                '<small class="text-muted">' + getTimeElapsed(signal.created_at) + '</small>' +
                            '</div>' +
                            '<div class="d-flex justify-content-between align-items-center">' +
                                '<small>Entry: <strong>' + formatCurrency(signal.entry_price) + '</strong></small>' +
                                '<small><span class="' + getStatusClass(signal.status) + '">' + getStatusText(signal.status) + '</span></small>' +
                            '</div>' +
                            '<div class="mt-1">' +
                                '<div class="progress" style="height: 3px;">' +
                                    '<div class="progress-bar bg-' + patternColor + '" style="width: ' + (signal.confidence || 0) + '%"></div>' +
                                '</div>' +
                                '<small class="text-muted">Confiança: ' + (signal.confidence || 0) + '%</small>' +
                            '</div>' +
                        '</div>';
                }
            }
            
            container.innerHTML = html;
        })
        .catch(function(error) {
            debugLog('Erro ao carregar sinais recentes', error);
        });
}

// ==================== ANIMAÇÃO DE VALORES ====================
function animateValue(element, start, end, duration, formatter) {
    if (!element) return;
    
    duration = duration || 1000;
    formatter = formatter || function(val) { return Math.round(val); };
    
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

// ==================== ATUALIZAÇÃO DE TIMESTAMP ====================
function updateLastUpdate() {
    try {
        var element = document.getElementById('last-update');
        if (element) {
            element.textContent = formatTime(new Date().toISOString());
        }
    } catch (error) {
        debugLog('Erro ao atualizar timestamp', error);
    }
}
/**
 * Dashboard JavaScript - Modular e Limpo
 * Gerencia o dashboard principal sem gráficos, focado em indicadores
 */

class TradingDashboard {
    constructor() {
        this.currentCrypto = 'BTC';
        this.updateInterval = null;
        this.isUpdating = false;
        
        this.cryptoConfig = {
            'BTC': {
                name: 'Bitcoin',
                symbol: 'BTCUSDT',
                color: '#f7931a',
                icon: 'fab fa-bitcoin'
            },
            'ETH': {
                name: 'Ethereum', 
                symbol: 'ETHUSDT',
                color: '#627eea',
                icon: 'fab fa-ethereum'
            },
            'SOL': {
                name: 'Solana',
                symbol: 'SOLUSDT', 
                color: '#9945ff',
                icon: 'fas fa-sun'
            }
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startUpdates();
        console.log('[DASHBOARD] Trading Dashboard inicializado');
    }
    
    setupEventListeners() {
        // Crypto tabs
        document.querySelectorAll('#crypto-tabs .nav-link').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const crypto = e.target.closest('.nav-link').dataset.crypto;
                this.switchCrypto(crypto);
            });
        });
        
        // System controls
        this.setupSystemControls();
        
        // Action buttons
        this.setupActionButtons();
    }
    
    setupSystemControls() {
        // Bitcoin controls
        document.getElementById('start-bitcoin')?.addEventListener('click', () => {
            this.controlBitcoin('start');
        });
        
        document.getElementById('stop-bitcoin')?.addEventListener('click', () => {
            this.controlBitcoin('stop');
        });
        
        // Multi-asset controls
        document.getElementById('start-multi')?.addEventListener('click', () => {
            this.controlMultiAsset('start');
        });
        
        document.getElementById('stop-multi')?.addEventListener('click', () => {
            this.controlMultiAsset('stop');
        });
    }
    
    setupActionButtons() {
        // Force signal generation
        document.getElementById('force-signal')?.addEventListener('click', () => {
            this.generateTestSignal();
        });
        
        // Refresh data
        document.getElementById('refresh-data')?.addEventListener('click', () => {
            this.forceUpdate();
        });
    }
    
    switchCrypto(crypto) {
        // Update active tab
        document.querySelectorAll('#crypto-tabs .nav-link').forEach(tab => {
            tab.classList.remove('active');
        });
        document.getElementById(`${crypto.toLowerCase()}-tab`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('show', 'active');
        });
        document.getElementById(`${crypto.toLowerCase()}-content`).classList.add('show', 'active');
        
        this.currentCrypto = crypto;
        this.updateCryptoData(crypto);
        
        console.log(`[DASHBOARD] Switched to ${crypto}`);
    }
    
    async updateCryptoData(crypto) {
        try {
            // Update price data
            await this.updatePrice(crypto);
            
            // Update indicators
            await this.updateIndicators(crypto);
            
            // Update analysis
            await this.updateAnalysis(crypto);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao atualizar dados de ${crypto}:`, error);
        }
    }
    
    async updatePrice(crypto) {
        try {
            let endpoint;
            if (crypto === 'BTC') {
                endpoint = '/api/bitcoin/current';
            } else {
                endpoint = `/multi-asset/api/asset/${crypto}`;
            }
            
            const response = await fetch(endpoint);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            let price, change, updated;
            
            if (crypto === 'BTC') {
                price = data.current_price;
                change = 0; // Bitcoin endpoint não retorna mudança
                updated = data.timestamp;
            } else {
                price = data.streaming_data?.last_price || 0;
                change = 0; // Implementar se necessário
                updated = data.streaming_data?.last_update;
            }
            
            // Update price display
            const priceElement = document.getElementById(`${crypto.toLowerCase()}-price`);
            const changeElement = document.getElementById(`${crypto.toLowerCase()}-change`);
            const updatedElement = document.getElementById(`${crypto.toLowerCase()}-updated`);
            
            if (priceElement) {
                priceElement.textContent = this.formatPrice(price);
            }
            
            if (changeElement) {
                changeElement.textContent = this.formatChange(change);
                changeElement.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;
            }
            
            if (updatedElement) {
                updatedElement.textContent = updated ? new Date(updated).toLocaleTimeString() : 'N/A';
            }
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao atualizar preço de ${crypto}:`, error);
            this.showError(`Erro ao carregar preço de ${crypto}`);
        }
    }
    
    async updateIndicators(crypto) {
        try {
            let endpoint;
            if (crypto === 'BTC') {
                endpoint = '/trading/api/analysis';
            } else {
                endpoint = `/multi-asset/api/asset/${crypto}/analysis`;
            }
            
            const response = await fetch(endpoint);
            if (!response.ok) {
                // Se multi-asset não disponível, mostrar placeholder
                if (crypto !== 'BTC') {
                    this.showIndicatorsPlaceholder(crypto);
                    return;
                }
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const indicators = data.technical_indicators || {};
            
            this.displayIndicators(crypto, indicators);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao atualizar indicadores de ${crypto}:`, error);
            this.showIndicatorsPlaceholder(crypto);
        }
    }
    
    displayIndicators(crypto, indicators) {
        const container = document.getElementById(`${crypto.toLowerCase()}-indicators`);
        if (!container) return;
        
        if (Object.keys(indicators).length === 0) {
            container.innerHTML = '<div class="text-center text-muted">Nenhum indicador disponível</div>';
            return;
        }
        
        const indicatorsList = [
            { key: 'RSI', name: 'RSI (14)', format: 'number' },
            { key: 'MACD_Histogram', name: 'MACD', format: 'number' },
            { key: 'BB_Position', name: 'Bollinger', format: 'percentage' },
            { key: 'Stoch_K', name: 'Stochastic', format: 'number' },
            { key: 'Volume_Ratio', name: 'Volume', format: 'ratio' },
            { key: 'Trend_Strength', name: 'Tendência', format: 'percentage' }
        ];
        
        let html = '';
        
        indicatorsList.forEach(indicator => {
            const value = indicators[indicator.key];
            if (value !== undefined && value !== null) {
                const formattedValue = this.formatIndicatorValue(value, indicator.format);
                const signal = this.getIndicatorSignal(indicator.key, value);
                
                html += `
                    <div class="indicator-item">
                        <div class="indicator-name">${indicator.name}</div>
                        <div class="indicator-value">${formattedValue}</div>
                        <div class="indicator-signal ${signal}">${signal}</div>
                    </div>
                `;
            }
        });
        
        container.innerHTML = html || '<div class="text-center text-muted">Carregando indicadores...</div>';
    }
    
    showIndicatorsPlaceholder(crypto) {
        const container = document.getElementById(`${crypto.toLowerCase()}-indicators`);
        if (!container) return;
        
        container.innerHTML = `
            <div class="text-center text-muted">
                <i class="fas fa-chart-bar fa-2x mb-2"></i>
                <p>Indicadores para ${crypto} não disponíveis</p>
                <small>Multi-Asset pode não estar configurado</small>
            </div>
        `;
    }
    
    async updateAnalysis(crypto) {
        try {
            let endpoint;
            if (crypto === 'BTC') {
                endpoint = '/trading/api/analysis';
            } else {
                endpoint = `/multi-asset/api/asset/${crypto}/analysis`;
            }
            
            const response = await fetch(endpoint);
            if (!response.ok) {
                if (crypto !== 'BTC') {
                    this.showAnalysisPlaceholder(crypto);
                    return;
                }
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const signalAnalysis = data.signal_analysis || {};
            
            this.displayAnalysis(crypto, signalAnalysis);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao atualizar análise de ${crypto}:`, error);
            this.showAnalysisPlaceholder(crypto);
        }
    }
    
    displayAnalysis(crypto, analysis) {
        const container = document.getElementById(`${crypto.toLowerCase()}-analysis`);
        if (!container) return;
        
        if (Object.keys(analysis).length === 0) {
            this.showAnalysisPlaceholder(crypto);
            return;
        }
        
        const recommendedAction = analysis.recommended_action || 'HOLD';
        const confidence = analysis.confidence || 0;
        const confluenceScore = analysis.confluence_score || 0;
        const volumeConfirmed = analysis.volume_confirmed || false;
        
        const html = `
            <div class="analysis-item">
                <span class="analysis-label">Ação Recomendada:</span>
                <span class="analysis-value ${recommendedAction.toLowerCase()}">${recommendedAction}</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">Confiança:</span>
                <span class="analysis-value">${Math.round(confidence)}%</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">Score de Confluência:</span>
                <span class="analysis-value">${Math.round(confluenceScore)}%</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">Volume Confirmado:</span>
                <span class="analysis-value ${volumeConfirmed ? 'buy' : 'hold'}">
                    ${volumeConfirmed ? 'Sim' : 'Não'}
                </span>
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    showAnalysisPlaceholder(crypto) {
        const container = document.getElementById(`${crypto.toLowerCase()}-analysis`);
        if (!container) return;
        
        container.innerHTML = `
            <div class="text-center text-muted">
                <i class="fas fa-brain fa-2x mb-2"></i>
                <p>Análise para ${crypto} não disponível</p>
                <small>Sistema pode estar carregando ou configurando</small>
            </div>
        `;
    }
    
    async updateSignalsTable() {
        try {
            // Tentar buscar sinais de Bitcoin primeiro
            const response = await fetch('/trading/api/signals');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            const signals = [
                ...(data.active_signals || []),
                ...(data.recent_signals || [])
            ];
            
            // Tentar buscar sinais consolidados multi-asset
            try {
                const multiResponse = await fetch('/multi-asset/api/consolidated/signals');
                if (multiResponse.ok) {
                    const multiData = await multiResponse.json();
                    signals.push(...(multiData.consolidated_signals || []));
                }
            } catch (error) {
                console.debug('[DASHBOARD] Multi-asset signals não disponível:', error);
            }
            
            this.displaySignalsTable(signals);
            this.updateSignalsCounts(signals);
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao atualizar tabela de sinais:', error);
            this.showSignalsError();
        }
    }
    
    displaySignalsTable(signals) {
        const tbody = document.getElementById('signals-table-body');
        if (!tbody) return;
        
        if (!signals || signals.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center text-muted">
                        <i class="fas fa-signal fa-2x mb-2"></i><br>
                        Nenhum sinal disponível
                    </td>
                </tr>
            `;
            return;
        }
        
        let html = '';
        
        // Ordenar sinais por data (mais recentes primeiro)
        signals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        signals.slice(0, 20).forEach(signal => {
            const crypto = signal.asset_symbol || 'BTC';
            const type = signal.type || signal.signal_type || signal.pattern_type || 'UNKNOWN';
            const entry = signal.entry || signal.entry_price || 0;
            const target = signal.targets ? signal.targets[0] : (signal.target_price || signal.target_1 || 0);
            const stopLoss = signal.stop_loss || 0;
            const confidence = signal.confidence || 0;
            const pnl = signal.current_pnl || signal.profit_loss || 0;
            const status = signal.status || 'ACTIVE';
            const created = signal.created_at ? new Date(signal.created_at).toLocaleString() : 'N/A';
            
            const pnlClass = pnl > 0 ? 'pnl-positive' : pnl < 0 ? 'pnl-negative' : 'pnl-neutral';
            const typeClass = type.toLowerCase().includes('buy') ? 'buy' : 'sell';
            
            html += `
                <tr>
                    <td>#${signal.id || 'N/A'}</td>
                    <td>
                        <span style="color: ${this.cryptoConfig[crypto]?.color || '#666'}">
                            <i class="${this.cryptoConfig[crypto]?.icon || 'fas fa-coins'}"></i>
                            ${crypto}
                        </span>
                    </td>
                    <td>
                        <span class="signal-type ${typeClass}">${type}</span>
                    </td>
                    <td>${this.formatPrice(entry)}</td>
                    <td>${this.formatPrice(target)}</td>
                    <td>${this.formatPrice(stopLoss)}</td>
                    <td>${confidence}%</td>
                    <td class="${pnlClass}">
                        ${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%
                    </td>
                    <td>
                        <span class="signal-status ${status.toLowerCase().replace('_', '-')}">${status}</span>
                    </td>
                    <td>${created}</td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    }
    
    updateSignalsCounts(signals) {
        const activeSignals = signals.filter(s => s.status === 'ACTIVE').length;
        const totalSignals = signals.length;
        
        const activeElement = document.getElementById('active-signals-count');
        const totalElement = document.getElementById('total-signals-count');
        
        if (activeElement) {
            activeElement.textContent = `${activeSignals} Ativos`;
        }
        
        if (totalElement) {
            totalElement.textContent = `${totalSignals} Total`;
        }
    }
    
    showSignalsError() {
        const tbody = document.getElementById('signals-table-body');
        if (!tbody) return;
        
        tbody.innerHTML = `
            <tr>
                <td colspan="10" class="text-center text-danger">
                    <i class="fas fa-exclamation-circle fa-2x mb-2"></i><br>
                    Erro ao carregar sinais
                </td>
            </tr>
        `;
    }
    
    async updateSystemStatus() {
        try {
            // Bitcoin status
            const bitcoinResponse = await fetch('/api/bitcoin/status');
            if (bitcoinResponse.ok) {
                const bitcoinData = await bitcoinResponse.json();
                this.updateStatusDisplay('bitcoin-status', bitcoinData.is_running);
            }
            
            // Multi-asset status
            try {
                const multiResponse = await fetch('/api/multi-asset/health');
                if (multiResponse.ok) {
                    const multiData = await multiResponse.json();
                    const isHealthy = multiData.overall_status === 'HEALTHY' || multiData.overall_status === 'PARTIAL';
                    this.updateStatusDisplay('multi-status', isHealthy);
                } else {
                    this.updateStatusDisplay('multi-status', false, 'Não disponível');
                }
            } catch (error) {
                this.updateStatusDisplay('multi-status', false, 'Não configurado');
            }
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao atualizar status do sistema:', error);
        }
    }
    
    updateStatusDisplay(elementId, isOnline, customText = null) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        if (customText) {
            element.textContent = `Status: ${customText}`;
            element.className = 'status-text';
        } else {
            element.textContent = `Status: ${isOnline ? 'Online' : 'Offline'}`;
            element.className = `status-text ${isOnline ? 'online' : 'offline'}`;
        }
    }
    
    // Control Methods
    async controlBitcoin(action) {
        try {
            const endpoint = action === 'start' ? '/api/bitcoin/start-stream' : '/api/bitcoin/stop-stream';
            const response = await fetch(endpoint, { method: 'POST' });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.showNotification(data.message, 'success');
            
            // Update status immediately
            setTimeout(() => this.updateSystemStatus(), 1000);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao ${action} Bitcoin:`, error);
            this.showNotification(`Erro ao ${action === 'start' ? 'iniciar' : 'parar'} Bitcoin`, 'error');
        }
    }
    
    async controlMultiAsset(action) {
        try {
            const endpoint = action === 'start' ? '/api/multi-asset/start' : '/api/multi-asset/stop';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assets: ['BTC', 'ETH', 'SOL'] })
            });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.showNotification(data.message, 'success');
            
            // Update status immediately
            setTimeout(() => this.updateSystemStatus(), 1000);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao ${action} Multi-Asset:`, error);
            this.showNotification(`Multi-Asset pode não estar disponível`, 'warning');
        }
    }
    
    async generateTestSignal() {
        try {
            const response = await fetch('/api/trading/generate-test-signal', { method: 'POST' });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.showNotification('Sinal de teste gerado com sucesso!', 'success');
            
            // Update signals table immediately
            setTimeout(() => this.updateSignalsTable(), 1000);
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao gerar sinal de teste:', error);
            this.showNotification('Erro ao gerar sinal de teste', 'error');
        }
    }
    
    // Update Methods
    async updateAll() {
        if (this.isUpdating) return;
        this.isUpdating = true;
        
        try {
            await Promise.all([
                this.updateCryptoData(this.currentCrypto),
                this.updateSignalsTable(),
                this.updateSystemStatus()
            ]);
        } catch (error) {
            console.error('[DASHBOARD] Erro na atualização geral:', error);
        } finally {
            this.isUpdating = false;
        }
    }
    
    forceUpdate() {
        this.showNotification('Atualizando dados...', 'info');
        this.updateAll();
    }
    
    startUpdates() {
        // Initial update
        this.updateAll();
        
        // Set up interval updates
        this.updateInterval = setInterval(() => {
            this.updateAll();
        }, 10000); // Update every 10 seconds
        
        console.log('[DASHBOARD] Updates iniciados (10s interval)');
    }
    
    stopUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
            console.log('[DASHBOARD] Updates parados');
        }
    }
    
    // Utility Methods
    formatPrice(price) {
        if (!price || price === 0) return '$0.00';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 8
        }).format(price);
    }
    
    formatChange(change) {
        if (!change) return '0.00%';
        return `${change > 0 ? '+' : ''}${change.toFixed(2)}%`;
    }
    
    formatIndicatorValue(value, format) {
        if (value === null || value === undefined) return 'N/A';
        
        switch (format) {
            case 'percentage':
                return `${(value * 100).toFixed(1)}%`;
            case 'ratio':
                return `${value.toFixed(2)}x`;
            case 'number':
            default:
                return value.toFixed(2);
        }
    }
    
    getIndicatorSignal(key, value) {
        if (typeof value !== 'number') return 'neutral';
        
        const signals = {
            'RSI': (v) => v < 30 ? 'bullish' : v > 70 ? 'bearish' : 'neutral',
            'MACD_Histogram': (v) => v > 0 ? 'bullish' : 'bearish',
            'BB_Position': (v) => v < 0.2 ? 'bullish' : v > 0.8 ? 'bearish' : 'neutral',
            'Stoch_K': (v) => v < 20 ? 'bullish' : v > 80 ? 'bearish' : 'neutral',
            'Volume_Ratio': (v) => v > 1.5 ? 'bullish' : v < 0.7 ? 'bearish' : 'neutral',
            'Trend_Strength': (v) => v > 0.7 ? 'bullish' : v < 0.3 ? 'bearish' : 'neutral'
        };
        
        return signals[key] ? signals[key](value) : 'neutral';
    }
    
    showNotification(message, type = 'info') {
        const toast = document.getElementById('notification-toast');
        const messageElement = document.getElementById('toast-message');
        
        if (!toast || !messageElement) return;
        
        messageElement.textContent = message;
        toast.className = `toast ${type}`;
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        console.log(`[NOTIFICATION] ${type.toUpperCase()}: ${message}`);
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('[DASHBOARD] Inicializando Trading Dashboard...');
    window.tradingDashboard = new TradingDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.tradingDashboard) {
        window.tradingDashboard.stopUpdates();
    }
});

// Global functions for debugging
window.debugDashboard = function() {
    console.log('[DEBUG] Dashboard State:', {
        currentCrypto: window.tradingDashboard?.currentCrypto,
        isUpdating: window.tradingDashboard?.isUpdating,
        updateInterval: !!window.tradingDashboard?.updateInterval
    });
};

window.forceUpdate = function() {
    window.tradingDashboard?.forceUpdate();
};

window.generateTestSignal = function() {
    window.tradingDashboard?.generateTestSignal();
};
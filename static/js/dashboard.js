/**
 * Trading Dashboard - Modular e Organizado
 * Versão limpa e estruturada para máxima harmonia e eficiência
 */

class TradingDashboard {
    constructor() {
        this.currentCrypto = 'BTC';
        this.updateInterval = null;
        this.monitorCheckInterval = null;
        this.isUpdating = false;
        
        // Configurações das criptomoedas
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
        
        // Signal Monitor
        this.signalMonitorEnabled = true;
        this.lastSignalMonitorCheck = 0;
        this.signalCheckInterval = 30000;
        this.lastSignalsCount = 0;
        this.duplicateAlertShown = false;
        
        this.init();
    }
    
    // ===== INICIALIZAÇÃO =====
    
    init() {
        this.setupEventListeners();
        this.setupActionButtons();
        this.startUpdates();
        console.log('[DASHBOARD] Trading Dashboard inicializado ✅');
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
        
        // ===== NOVOS BOTÕES PARA SIGNAL MONITOR =====
        this.createSignalMonitorButtons();
    }
    
    createSignalMonitorButtons() {
        const controlsContainer = document.querySelector('.signals-controls') || 
                                 document.querySelector('.card-header .d-flex') ||
                                 document.querySelector('.card-header');
        
        if (!controlsContainer) return;
        
        // Verificar se já existem para evitar duplicação
        if (document.getElementById('force-signal-check-btn')) return;
        
        // Botão para forçar verificação de sinais
        const forceCheckBtn = document.createElement('button');
        forceCheckBtn.id = 'force-signal-check-btn';
        forceCheckBtn.innerHTML = '<i class="fas fa-search"></i> Verificar';
        forceCheckBtn.className = 'btn btn-outline-primary btn-sm me-2';
        forceCheckBtn.onclick = () => this.forceSignalCheck();
        
        // Botão para limpar duplicados
        const cleanupBtn = document.createElement('button');
        cleanupBtn.id = 'cleanup-duplicates-btn';
        cleanupBtn.innerHTML = '<i class="fas fa-broom"></i> Limpar';
        cleanupBtn.className = 'btn btn-outline-warning btn-sm me-2';
        cleanupBtn.onclick = () => this.cleanupDuplicateSignals();
        
        // Adicionar botões
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'btn-group btn-group-sm ms-auto';
        buttonGroup.appendChild(forceCheckBtn);
        buttonGroup.appendChild(cleanupBtn);
        controlsContainer.appendChild(buttonGroup);
    }
    
    // ===== NAVEGAÇÃO ENTRE CRYPTOS =====
    
    switchCrypto(crypto) {
        // Update active tab
        document.querySelectorAll('#crypto-tabs .nav-link').forEach(tab => {
            tab.classList.remove('active');
        });
        document.getElementById(`${crypto.toLowerCase()}-tab`)?.classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('show', 'active');
        });
        document.getElementById(`${crypto.toLowerCase()}-content`)?.classList.add('show', 'active');
        
        this.currentCrypto = crypto;
        this.updateCryptoData(crypto);
        
        console.log(`[DASHBOARD] Switched to ${crypto}`);
    }
    
    // ===== ATUALIZAÇÃO DE DADOS =====
    
    async updateCryptoData(crypto) {
        try {
            await Promise.all([
                this.updatePrice(crypto),
                this.updateIndicators(crypto),
                this.updateAnalysis(crypto)
            ]);
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
                change = 0;
                updated = data.timestamp;
            } else {
                price = data.streaming_data?.last_price || 0;
                change = 0;
                updated = data.streaming_data?.last_update;
            }
            
            this.updatePriceDisplay(crypto, price, change, updated);
            
        } catch (error) {
            console.error(`[DASHBOARD] Erro ao atualizar preço de ${crypto}:`, error);
            this.showError(`Erro ao carregar preço de ${crypto}`);
        }
    }
    
    updatePriceDisplay(crypto, price, change, updated) {
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
    
    // ===== ATUALIZAÇÃO DE SINAIS =====
    
    async updateSignalsTable() {
        try {
            const response = await fetch('/api/signals/dashboard-data');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Erro desconhecido');
            }
            
            const data = result.data;
            const signals = data.active_signals || [];
            
            // Verificar duplicação e status do monitor
            this.checkForDuplicateSignals(signals);
            if (this.signalMonitorEnabled) {
                this.checkSignalMonitorStatus(data.monitor_status);
            }
            
            // Exibir dados
            this.displaySignalsTable(signals);
            this.updateSignalsCounts(signals);
            this.updateMonitorInfo(data.monitor_status);
            
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
                        Nenhum sinal ativo no momento
                        <br><small>O monitor está verificando continuamente...</small>
                    </td>
                </tr>
            `;
            return;
        }
        
        // Remover duplicados e ordenar
        const uniqueSignals = this.removeDuplicateSignals(signals);
        uniqueSignals.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        let html = '';
        
        uniqueSignals.slice(0, 20).forEach(signal => {
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
            const statusDisplay = this.getStatusDisplay(status, pnl);
            
            html += `
                <tr data-signal-id="${signal.id}">
                    <td>
                        <strong>#${signal.id || 'N/A'}</strong>
                        ${this.getSignalHealthIndicator(signal)}
                    </td>
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
                    <td>
                        <span class="confidence-badge">${confidence}%</span>
                    </td>
                    <td class="${pnlClass}">
                        ${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%
                    </td>
                    <td>${statusDisplay}</td>
                    <td><small>${created}</small></td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
        this.addUpdateIndicator();
    }
    
    removeDuplicateSignals(signals) {
        return signals.filter((signal, index, self) => 
            index === self.findIndex(s => s.id === signal.id)
        );
    }
    
    getSignalHealthIndicator(signal) {
        const confidence = signal.confidence || 0;
        const pnl = signal.current_pnl || 0;
        
        let indicator = '🟡'; // Default
        
        if (pnl > 2) {
            indicator = '🟢'; // Muito positivo
        } else if (pnl > 0) {
            indicator = '🔵'; // Positivo
        } else if (pnl < -1) {
            indicator = '🔴'; // Negativo
        }
        
        return `<small>${indicator}</small>`;
    }
    
    getStatusDisplay(status, pnl) {
        let statusClass = 'signal-status active';
        let statusText = 'ATIVO';
        let statusIcon = '🔄';
        
        if (pnl > 1) {
            statusClass += ' profit';
            statusText = 'LUCRO';
            statusIcon = '📈';
        } else if (pnl < -0.5) {
            statusClass += ' loss';
            statusText = 'PERDA';
            statusIcon = '📉';
        }
        
        return `<span class="${statusClass}">${statusIcon} ${statusText}</span>`;
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
    
    // ===== SISTEMA DE SAÚDE =====
    
    async updateSystemStatus() {
        try {
            const bitcoinResponse = await fetch('/api/bitcoin/status');
            if (bitcoinResponse.ok) {
                const bitcoinData = await bitcoinResponse.json();
                this.updateStatusDisplay('bitcoin-status', bitcoinData.is_running);
            }
            
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
    
    async checkSystemHealth() {
        try {
            const response = await fetch('/api/system/health');
            if (response.ok) {
                const health = await response.json();
                
                const signalMonitor = health.components?.signal_monitor;
                const tradingAnalyzer = health.components?.trading_analyzer;
                
                if (signalMonitor && signalMonitor.status !== 'running') {
                    console.warn('[DASHBOARD] Signal Monitor não está rodando');
                }
                
                if (tradingAnalyzer && !tradingAnalyzer.signal_monitor_active) {
                    console.warn('[DASHBOARD] Signal Monitor não está ativo no Trading Analyzer');
                }
            }
        } catch (error) {
            console.error('[DASHBOARD] Erro ao verificar saúde do sistema:', error);
        }
    }
    
    // ===== SIGNAL MONITOR =====
    
    checkForDuplicateSignals(signals) {
        const uniqueIds = new Set();
        const duplicates = [];
        
        signals.forEach(signal => {
            if (uniqueIds.has(signal.id)) {
                duplicates.push(signal.id);
            } else {
                uniqueIds.add(signal.id);
            }
        });
        
        if (duplicates.length > 0 && !this.duplicateAlertShown) {
            console.warn(`[DASHBOARD] ${duplicates.length} sinais duplicados detectados`);
            this.duplicateAlertShown = true;
        }
    }
    
    checkSignalMonitorStatus(monitorStatus) {
        if (!monitorStatus) return;
        
        const now = Date.now();
        if (now - this.lastSignalMonitorCheck > this.signalCheckInterval) {
            this.lastSignalMonitorCheck = now;
            
            if (!monitorStatus.is_running) {
                console.warn('[DASHBOARD] Signal Monitor não está rodando');
            }
        }
    }
    
    updateMonitorInfo(monitorStatus) {
        try {
            let monitorInfo = document.getElementById('signal-monitor-info');
            
            if (!monitorInfo) {
                const container = document.querySelector('.card-header');
                if (container) {
                    monitorInfo = document.createElement('small');
                    monitorInfo.id = 'signal-monitor-info';
                    monitorInfo.className = 'text-muted ms-2';
                    container.appendChild(monitorInfo);
                }
            }
            
            if (monitorInfo && monitorStatus) {
                const isRunning = monitorStatus.is_running;
                const trackedCount = monitorStatus.tracked_signals_count || 0;
                
                monitorInfo.innerHTML = `
                    <i class="fas fa-robot"></i> 
                    Monitor: ${isRunning ? '🟢 Online' : '🔴 Offline'} 
                    (${trackedCount} tracking)
                `;
                
                monitorInfo.className = `text-muted ms-2 ${isRunning ? '' : 'text-warning'}`;
            }
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao atualizar info do monitor:', error);
        }
    }
    
    addUpdateIndicator() {
        const container = document.querySelector('.signals-table-container') || 
                         document.querySelector('.table-responsive');
        
        if (!container) return;
        
        let indicator = document.getElementById('signals-update-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'signals-update-indicator';
            indicator.className = 'update-indicator';
            container.appendChild(indicator);
        }
        
        const now = new Date();
        indicator.innerHTML = `
            <small class="text-muted">
                <i class="fas fa-sync-alt"></i> 
                Última atualização: ${now.toLocaleTimeString()}
            </small>
        `;
        
        indicator.style.opacity = '0.5';
        setTimeout(() => {
            indicator.style.opacity = '1';
        }, 200);
    }
    
    // ===== CONTROLES DO SISTEMA =====
    
    async controlBitcoin(action) {
        try {
            const endpoint = action === 'start' ? '/api/bitcoin/start-stream' : '/api/bitcoin/stop-stream';
            const response = await fetch(endpoint, { method: 'POST' });
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.showNotification(data.message, 'success');
            
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
            
            setTimeout(() => this.updateSignalsTable(), 1000);
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao gerar sinal de teste:', error);
            this.showNotification('Erro ao gerar sinal de teste', 'error');
        }
    }
    
    async cleanupDuplicateSignals() {
        try {
            const response = await fetch('/api/signals/cleanup-duplicates', {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.showNotification('✅ Sinais duplicados removidos', 'success');
                    setTimeout(() => this.updateSignalsTable(), 2000);
                }
            }
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao limpar duplicados:', error);
        }
    }
    
    async forceSignalCheck() {
        try {
            this.showNotification('🔄 Verificando sinais...', 'info');
            
            const response = await fetch('/api/signals/force-check', {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.showNotification('✅ Verificação de sinais concluída', 'success');
                    setTimeout(() => this.updateSignalsTable(), 1000);
                } else {
                    this.showNotification(`❌ ${result.error}`, 'error');
                }
            }
            
        } catch (error) {
            console.error('[DASHBOARD] Erro ao forçar verificação:', error);
            this.showNotification('❌ Erro ao verificar sinais', 'error');
        }
    }
    
    // ===== ATUALIZAÇÃO GERAL =====
    
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
        this.updateAll();
        
        this.updateInterval = setInterval(() => {
            this.updateAll();
        }, 10000);
        
        this.monitorCheckInterval = setInterval(() => {
            this.checkSystemHealth();
        }, 30000);
        
        console.log('[DASHBOARD] Updates e monitoramento iniciados (10s/30s intervals)');
    }
    
    stopUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        if (this.monitorCheckInterval) {
            clearInterval(this.monitorCheckInterval);
            this.monitorCheckInterval = null;
        }
        
        console.log('[DASHBOARD] Updates e monitoramento parados');
    }
    
    // ===== UTILITÁRIOS =====
    
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
        
        if (!toast || !messageElement) {
            console.log(`[NOTIFICATION] ${type.toUpperCase()}: ${message}`);
            return;
        }
        
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

// ===== INICIALIZAÇÃO =====

document.addEventListener('DOMContentLoaded', function() {
    console.log('[DASHBOARD] Inicializando Trading Dashboard...');
    window.tradingDashboard = new TradingDashboard();
});

window.addEventListener('beforeunload', function() {
    if (window.tradingDashboard) {
        window.tradingDashboard.stopUpdates();
    }
});

// ===== FUNÇÕES GLOBAIS PARA DEBUG =====

window.debugDashboard = function() {
    console.log('[DEBUG] Dashboard State:', {
        currentCrypto: window.tradingDashboard?.currentCrypto,
        isUpdating: window.tradingDashboard?.isUpdating,
        updateInterval: !!window.tradingDashboard?.updateInterval,
        monitorCheckInterval: !!window.tradingDashboard?.monitorCheckInterval,
        signalMonitorEnabled: window.tradingDashboard?.signalMonitorEnabled,
        lastSignalsCount: window.tradingDashboard?.lastSignalsCount
    });
};

window.forceUpdate = function() {
    window.tradingDashboard?.forceUpdate();
};

window.generateTestSignal = function() {
    window.tradingDashboard?.generateTestSignal();
};

window.forceSignalCheck = function() {
    window.tradingDashboard?.forceSignalCheck();
};

window.cleanupDuplicates = function() {
    window.tradingDashboard?.cleanupDuplicateSignals();
};

window.checkSignalMonitorStatus = async function() {
    try {
        const response = await fetch('/api/signals/monitor/status');
        const result = await response.json();
        console.log('[DEBUG] Signal Monitor Status:', result);
        return result;
    } catch (error) {
        console.error('[DEBUG] Erro ao verificar status do monitor:', error);
    }
};

// ===== CSS ADICIONAL =====

const additionalCSS = `
.update-indicator {
    position: absolute;
    bottom: 10px;
    right: 10px;
    background: rgba(255, 255, 255, 0.9);
    padding: 5px 10px;
    border-radius: 15px;
    border: 1px solid #ddd;
    font-size: 0.8em;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.targets-display {
    line-height: 1.2;
}

.targets-display small {
    display: block;
    color: #666;
}

.confidence-badge {
    background: linear-gradient(45deg, #007bff, #0056b3);
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
}

.signal-status.profit {
    background-color: rgba(25, 135, 84, 0.1);
    color: #198754;
    border: 1px solid rgba(25, 135, 84, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
}

.signal-status.loss {
    background-color: rgba(220, 53, 69, 0.1);
    color: #dc3545;
    border: 1px solid rgba(220, 53, 69, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
}

.signal-status.active {
    background-color: rgba(13, 110, 253, 0.1);
    color: #0d6efd;
    border: 1px solid rgba(13, 110, 253, 0.2);
    padding: 2px 6px;
    border-radius: 4px;
}

.btn-group-sm .btn {
    font-size: 0.8em;
    padding: 0.25rem 0.5rem;
}

.indicator-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #eee;
}

.indicator-item:last-child {
    border-bottom: none;
}

.analysis-item {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
}

.pnl-positive {
    color: #28a745;
    font-weight: 600;
}

.pnl-negative {
    color: #dc3545;
    font-weight: 600;
}

.pnl-neutral {
    color: #6c757d;
}

.signal-type.buy {
    background-color: #d4edda;
    color: #155724;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
}

.signal-type.sell {
    background-color: #f8d7da;
    color: #721c24;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.85em;
}
`;

// Adicionar CSS dinamicamente
if (typeof document !== 'undefined') {
    const style = document.createElement('style');
    style.textContent = additionalCSS;
    document.head.appendChild(style);
}
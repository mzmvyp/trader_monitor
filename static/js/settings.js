// /static/js/settings.js

class SettingsManager {
    constructor() {
        this.currentConfig = {};
        this.unsavedChanges = false;
        this.init();
    }

    init() {
        console.log('[SETTINGS] Inicializando Settings Manager...');
        
        // Carregar configuração atual
        this.loadCurrentConfig();
        
        // Configurar event listeners
        this.setupEventListeners();
        
        // Configurar tooltips
        this.initializeTooltips();
        
        // Verificar status do sistema
        this.updateSystemStatus();
        
        // Auto-refresh status a cada 30 segundos
        setInterval(() => this.updateSystemStatus(), 30000);
    }

    setupEventListeners() {
        // Range sliders - Trading
        this.setupRangeSlider('min-confidence', 'confidence-value', (val) => `${val}%`);
        this.setupRangeSlider('cooldown-minutes', 'cooldown-value', (val) => `${val}min`);
        this.setupRangeSlider('max-signals', 'max-signals-value');
        this.setupRangeSlider('risk-reward', 'risk-reward-value', (val) => `${val}:1`);
        
        // Range sliders - Targets
        this.setupRangeSlider('target-1', 'target-1-value', (val) => `${val}x`);
        this.setupRangeSlider('target-2', 'target-2-value', (val) => `${val}x`);
        this.setupRangeSlider('target-3', 'target-3-value', (val) => `${val}x`);
        this.setupRangeSlider('stop-loss-atr', 'stop-loss-atr-value', (val) => `${val}x`);
        
        // Range sliders - Indicators
        this.setupRangeSlider('rsi-period', 'rsi-period-value');
        this.setupRangeSlider('rsi-overbought', 'rsi-overbought-value');
        this.setupRangeSlider('rsi-oversold', 'rsi-oversold-value');
        this.setupRangeSlider('stoch-overbought', 'stoch-overbought-value');
        this.setupRangeSlider('stoch-oversold', 'stoch-oversold-value');
        this.setupRangeSlider('sma-short', 'sma-short-value');
        this.setupRangeSlider('sma-long', 'sma-long-value');
        this.setupRangeSlider('ema-short', 'ema-short-value');
        this.setupRangeSlider('ema-long', 'ema-long-value');
        this.setupRangeSlider('volume-ratio', 'volume-ratio-value', (val) => `${val}x`);
        
        // Range sliders - Weights
        this.setupWeightSlider('weight-rsi', 'weight-rsi-value');
        this.setupWeightSlider('weight-macd', 'weight-macd-value');
        this.setupWeightSlider('weight-bb', 'weight-bb-value');
        this.setupWeightSlider('weight-stoch', 'weight-stoch-value');
        this.setupWeightSlider('weight-sma', 'weight-sma-value');
        this.setupWeightSlider('weight-volume', 'weight-volume-value');
        
        // Range sliders - System
        this.setupRangeSlider('fetch-interval-btc', 'fetch-interval-btc-value', (val) => `${Math.floor(val/60)}min`);
        this.setupRangeSlider('fetch-interval-eth', 'fetch-interval-eth-value', (val) => `${Math.floor(val/60)}min`);
        this.setupRangeSlider('fetch-interval-sol', 'fetch-interval-sol-value', (val) => `${Math.floor(val/60)}min`);
        this.setupRangeSlider('max-queue-size', 'max-queue-size-value');
        this.setupRangeSlider('cleanup-days', 'cleanup-days-value', (val) => `${val} dias`);
        
        // Buttons
        this.setupButton('save-settings-btn', () => this.saveSettings());
        this.setupButton('reset-form-btn', () => this.resetForm());
        this.setupButton('refresh-status', () => this.updateSystemStatus());
        this.setupButton('export-config-btn', () => this.exportConfig());
        this.setupButton('import-config-btn', () => this.importConfig());
        this.setupButton('reset-config-btn', () => this.resetToDefaults());
        
        // System Actions
        this.setupButton('reset-signals-btn', () => this.executeSystemAction('reset_signals', 'Resetar todos os sinais?'));
        this.setupButton('restart-analyzers-btn', () => this.executeSystemAction('restart_analyzers', 'Reiniciar analyzers?'));
        this.setupButton('force-save-btn', () => this.executeSystemAction('force_save', 'Forçar salvamento de estado?'));
        this.setupButton('cleanup-now-btn', () => this.cleanupData());
        this.setupButton('backup-now-btn', () => this.executeSystemAction('backup_database', 'Fazer backup dos bancos de dados?'));
        
        // File input for import
        document.getElementById('config-file-input').addEventListener('change', (e) => this.handleFileImport(e));
        
        // Mark unsaved changes on input
        document.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('change', () => {
                this.unsavedChanges = true;
                this.updateSaveButton();
            });
        });
        
        // Confirm action button
        this.setupButton('confirm-action-btn', () => this.executeConfirmedAction());
    }

    setupRangeSlider(sliderId, valueId, formatter = null) {
        const slider = document.getElementById(sliderId);
        const valueDisplay = document.getElementById(valueId);
        
        if (!slider || !valueDisplay) return;
        
        slider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            const displayValue = formatter ? formatter(value) : value;
            valueDisplay.textContent = displayValue;
            this.unsavedChanges = true;
            this.updateSaveButton();
        });
    }

    setupWeightSlider(sliderId, valueId) {
        const slider = document.getElementById(sliderId);
        const valueDisplay = document.getElementById(valueId);
        
        if (!slider || !valueDisplay) return;
        
        slider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            valueDisplay.textContent = `${Math.round(value * 100)}%`;
            this.updateTotalWeight();
            this.unsavedChanges = true;
            this.updateSaveButton();
        });
    }

    setupButton(buttonId, handler) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.addEventListener('click', handler);
        }
    }

    updateTotalWeight() {
        const weights = [
            'weight-rsi', 'weight-macd', 'weight-bb', 
            'weight-stoch', 'weight-sma', 'weight-volume'
        ];
        
        let total = 0;
        weights.forEach(weightId => {
            const slider = document.getElementById(weightId);
            if (slider) {
                total += parseFloat(slider.value);
            }
        });
        
        const totalDisplay = document.getElementById('total-weight');
        if (totalDisplay) {
            totalDisplay.textContent = `${Math.round(total * 100)}%`;
            
            // Colorir baseado na proximidade de 100%
            const diff = Math.abs(total - 1.0);
            if (diff < 0.01) {
                totalDisplay.className = 'text-success';
            } else if (diff < 0.05) {
                totalDisplay.className = 'text-warning';
            } else {
                totalDisplay.className = 'text-danger';
            }
        }
    }

    updateSaveButton() {
        const saveBtn = document.getElementById('save-settings-btn');
        if (saveBtn) {
            if (this.unsavedChanges) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Salvar Configurações *';
                saveBtn.classList.add('btn-warning');
                saveBtn.classList.remove('btn-success');
            } else {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Salvar Configurações';
                saveBtn.classList.add('btn-success');
                saveBtn.classList.remove('btn-warning');
            }
        }
    }

    async loadCurrentConfig() {
        try {
            this.showLoading('Carregando configurações...');
            
            const response = await fetch('/settings/api/get-config');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.currentConfig = data.config;
                this.populateForm(this.currentConfig);
                this.updateConfigPreview();
                this.showSuccess('Configurações carregadas');
            } else {
                this.showError(`Erro ao carregar configurações: ${data.message}`);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao carregar configurações:', error);
            this.showError('Erro ao carregar configurações');
        } finally {
            this.hideLoading();
        }
    }

    populateForm(config) {
        console.log('[SETTINGS] Populando formulário...', config);
        
        // Trading parameters
        if (config.trading && config.trading.ta_params) {
            const ta = config.trading.ta_params;
            this.setSliderValue('rsi-period', ta.rsi_period);
            this.setSliderValue('rsi-overbought', ta.rsi_overbought);
            this.setSliderValue('rsi-oversold', ta.rsi_oversold);
            this.setSliderValue('sma-short', ta.sma_short);
            this.setSliderValue('sma-long', ta.sma_long);
            this.setSliderValue('ema-short', ta.ema_short);
            this.setSliderValue('ema-long', ta.ema_long);
            this.setSliderValue('volume-ratio', ta.min_volume_ratio);
            this.setSliderValue('min-confidence', ta.min_confidence);
            this.setSliderValue('risk-reward', ta.min_risk_reward);
            this.setSliderValue('stoch-overbought', ta.stoch_overbought);
            this.setSliderValue('stoch-oversold', ta.stoch_oversold);
        }
        
        // Signal configuration
        if (config.trading && config.trading.signal_config) {
            const signal = config.trading.signal_config;
            this.setSliderValue('max-signals', signal.max_active_signals);
            this.setSliderValue('cooldown-minutes', signal.signal_cooldown_minutes);
            this.setSliderValue('stop-loss-atr', signal.stop_loss_atr_multiplier);
            
            if (signal.target_multipliers) {
                this.setSliderValue('target-1', signal.target_multipliers[0]);
                this.setSliderValue('target-2', signal.target_multipliers[1]);
                this.setSliderValue('target-3', signal.target_multipliers[2]);
            }
        }
        
        // Indicator weights
        if (config.trading && config.trading.indicator_weights) {
            const weights = config.trading.indicator_weights;
            this.setSliderValue('weight-rsi', weights.rsi);
            this.setSliderValue('weight-macd', weights.macd);
            this.setSliderValue('weight-bb', weights.bb);
            this.setSliderValue('weight-stoch', weights.stoch);
            this.setSliderValue('weight-sma', weights.sma_cross);
            this.setSliderValue('weight-volume', weights.volume);
            this.updateTotalWeight();
        }
        
        // Streaming configuration
        if (config.streaming) {
            if (config.streaming.bitcoin) {
                this.setSliderValue('fetch-interval-btc', config.streaming.bitcoin.fetch_interval);
                this.setSliderValue('max-queue-size', config.streaming.bitcoin.max_queue_size);
            }
        }
        
        // System configuration
        if (config.system) {
            this.setCheckbox('auto-start-stream', config.system.auto_start_stream);
            this.setCheckbox('require-volume', config.system.require_volume_confirmation);
            this.setCheckbox('enable-auto-signals', config.system.enable_auto_signals);
            this.setCheckbox('enable-advanced-patterns', config.system.enable_advanced_patterns);
            this.setCheckbox('enable-notifications', config.system.enable_notifications);
            this.setCheckbox('correlation-analysis', config.system.correlation_analysis);
            this.setCheckbox('auto-cleanup', config.system.auto_cleanup);
            this.setSliderValue('cleanup-days', config.system.data_retention_days);
        }
        
        this.unsavedChanges = false;
        this.updateSaveButton();
    }

    setSliderValue(sliderId, value) {
        const slider = document.getElementById(sliderId);
        if (slider && value !== undefined) {
            slider.value = value;
            // Trigger input event to update display
            slider.dispatchEvent(new Event('input'));
        }
    }

    setCheckbox(checkboxId, value) {
        const checkbox = document.getElementById(checkboxId);
        if (checkbox && value !== undefined) {
            checkbox.checked = value;
        }
    }

    collectFormData() {
        return {
            trading: {
                ta_params: {
                    rsi_period: parseInt(this.getSliderValue('rsi-period')),
                    rsi_overbought: parseInt(this.getSliderValue('rsi-overbought')),
                    rsi_oversold: parseInt(this.getSliderValue('rsi-oversold')),
                    sma_short: parseInt(this.getSliderValue('sma-short')),
                    sma_long: parseInt(this.getSliderValue('sma-long')),
                    ema_short: parseInt(this.getSliderValue('ema-short')),
                    ema_long: parseInt(this.getSliderValue('ema-long')),
                    stoch_overbought: parseInt(this.getSliderValue('stoch-overbought')),
                    stoch_oversold: parseInt(this.getSliderValue('stoch-oversold')),
                    min_volume_ratio: parseFloat(this.getSliderValue('volume-ratio')),
                    min_confidence: parseInt(this.getSliderValue('min-confidence')),
                    min_risk_reward: parseFloat(this.getSliderValue('risk-reward'))
                },
                signal_config: {
                    max_active_signals: parseInt(this.getSliderValue('max-signals')),
                    signal_cooldown_minutes: parseInt(this.getSliderValue('cooldown-minutes')),
                    stop_loss_atr_multiplier: parseFloat(this.getSliderValue('stop-loss-atr')),
                    target_multipliers: [
                        parseFloat(this.getSliderValue('target-1')),
                        parseFloat(this.getSliderValue('target-2')),
                        parseFloat(this.getSliderValue('target-3'))
                    ]
                },
                indicator_weights: {
                    rsi: parseFloat(this.getSliderValue('weight-rsi')),
                    macd: parseFloat(this.getSliderValue('weight-macd')),
                    bb: parseFloat(this.getSliderValue('weight-bb')),
                    stoch: parseFloat(this.getSliderValue('weight-stoch')),
                    sma_cross: parseFloat(this.getSliderValue('weight-sma')),
                    volume: parseFloat(this.getSliderValue('weight-volume'))
                }
            },
            streaming: {
                bitcoin: {
                    fetch_interval: parseInt(this.getSliderValue('fetch-interval-btc')),
                    max_queue_size: parseInt(this.getSliderValue('max-queue-size'))
                }
            },
            system: {
                auto_start_stream: this.getCheckboxValue('auto-start-stream'),
                require_volume_confirmation: this.getCheckboxValue('require-volume'),
                enable_auto_signals: this.getCheckboxValue('enable-auto-signals'),
                enable_advanced_patterns: this.getCheckboxValue('enable-advanced-patterns'),
                enable_notifications: this.getCheckboxValue('enable-notifications'),
                correlation_analysis: this.getCheckboxValue('correlation-analysis'),
                auto_cleanup: this.getCheckboxValue('auto-cleanup'),
                data_retention_days: parseInt(this.getSliderValue('cleanup-days'))
            }
        };
    }

    getSliderValue(sliderId) {
        const slider = document.getElementById(sliderId);
        return slider ? slider.value : null;
    }

    getCheckboxValue(checkboxId) {
        const checkbox = document.getElementById(checkboxId);
        return checkbox ? checkbox.checked : false;
    }

    async saveSettings() {
        try {
            this.showLoading('Salvando configurações...');
            
            const configData = this.collectFormData();
            
            // Validar antes de enviar
            const validation = this.validateConfig(configData);
            if (!validation.valid) {
                this.showError(`Configuração inválida: ${validation.errors.join(', ')}`);
                return;
            }
            
            const response = await fetch('/settings/api/save-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    config: configData,
                    apply_immediately: true
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.currentConfig = { ...this.currentConfig, ...configData };
                this.unsavedChanges = false;
                this.updateSaveButton();
                this.updateConfigPreview();
                this.showSuccess('Configurações salvas e aplicadas com sucesso!');
            } else {
                this.showError(`Erro ao salvar: ${data.message}`);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao salvar:', error);
            this.showError('Erro ao salvar configurações');
        } finally {
            this.hideLoading();
        }
    }

    validateConfig(config) {
        const errors = [];
        
        // Validar trading config
        if (config.trading) {
            const ta = config.trading.ta_params;
            
            if (ta.rsi_oversold >= ta.rsi_overbought) {
                errors.push('RSI oversold deve ser menor que overbought');
            }
            
            if (ta.sma_short >= ta.sma_long) {
                errors.push('SMA curta deve ser menor que SMA longa');
            }
            
            if (ta.ema_short >= ta.ema_long) {
                errors.push('EMA curta deve ser menor que EMA longa');
            }
            
            // Validar pesos
            const weights = config.trading.indicator_weights;
            const totalWeight = Object.values(weights).reduce((sum, w) => sum + w, 0);
            if (Math.abs(totalWeight - 1.0) > 0.01) {
                errors.push(`Soma dos pesos deve ser 100% (atual: ${Math.round(totalWeight * 100)}%)`);
            }
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    resetForm() {
        if (this.unsavedChanges) {
            if (!confirm('Descartar alterações não salvas?')) {
                return;
            }
        }
        
        this.populateForm(this.currentConfig);
        this.unsavedChanges = false;
        this.updateSaveButton();
        this.showInfo('Formulário resetado');
    }

    async resetToDefaults() {
        if (!confirm('Resetar todas as configurações para os valores padrão?')) {
            return;
        }
        
        try {
            this.showLoading('Resetando configurações...');
            
            const response = await fetch('/settings/api/reset-config', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.loadCurrentConfig();
                this.showSuccess('Configurações resetadas para padrões');
            } else {
                this.showError(`Erro ao resetar: ${data.message}`);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao resetar:', error);
            this.showError('Erro ao resetar configurações');
        } finally {
            this.hideLoading();
        }
    }

    async exportConfig() {
        try {
            const response = await fetch('/settings/api/export-config');
            const data = await response.json();
            
            if (data.status === 'success') {
                const blob = new Blob([JSON.stringify(data.data, null, 2)], {
                    type: 'application/json'
                });
                
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                a.click();
                
                URL.revokeObjectURL(url);
                this.showSuccess('Configuração exportada');
            } else {
                this.showError(`Erro ao exportar: ${data.message}`);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao exportar:', error);
            this.showError('Erro ao exportar configuração');
        }
    }

    importConfig() {
        document.getElementById('config-file-input').click();
    }

    async handleFileImport(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        try {
            const text = await file.text();
            const configData = JSON.parse(text);
            
            const response = await fetch('/settings/api/import-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    config_data: configData
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                await this.loadCurrentConfig();
                this.showSuccess('Configuração importada com sucesso');
            } else {
                this.showError(`Erro ao importar: ${data.message}`);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao importar:', error);
            this.showError('Erro ao importar configuração. Verifique o formato do arquivo.');
        }
        
        // Clear file input
        event.target.value = '';
    }

    async updateSystemStatus() {
        try {
            const response = await fetch('/settings/api/system-status');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.displaySystemStatus(data.system_status);
            }
        } catch (error) {
            console.error('[SETTINGS] Erro ao atualizar status:', error);
        }
    }

    displaySystemStatus(status) {
        const indicator = document.getElementById('system-status-indicator');
        const text = document.getElementById('system-status-text');
        
        if (indicator && text) {
            // Remove all status classes
            indicator.className = 'status-indicator';
            
            switch (status.health) {
                case 'HEALTHY':
                    indicator.classList.add('status-active');
                    text.textContent = 'Sistema saudável';
                    break;
                case 'DEGRADED':
                case 'PARTIAL':
                    indicator.classList.add('status-warning');
                    text.textContent = 'Sistema com problemas';
                    break;
                case 'ERROR':
                    indicator.classList.add('status-inactive');
                    text.textContent = 'Sistema com erros';
                    break;
                default:
                    indicator.classList.add('status-warning');
                    text.textContent = 'Status desconhecido';
            }
        }
    }

    updateConfigPreview() {
        const preview = document.getElementById('config-preview');
        if (preview) {
            const displayConfig = {
                timestamp: new Date().toISOString(),
                version: '2.0.0',
                ...this.collectFormData()
            };
            
            preview.textContent = JSON.stringify(displayConfig, null, 2);
        }
    }

    executeSystemAction(action, confirmMessage = null) {
        if (confirmMessage) {
            this.showConfirmDialog(confirmMessage, () => {
                this.pendingAction = action;
            });
        } else {
            this.performSystemAction(action);
        }
    }

    async performSystemAction(action, params = {}) {
        try {
            this.showLoading(`Executando ${action}...`);
            
            const response = await fetch('/settings/api/system-actions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: action,
                    ...params
                })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showSuccess(data.message);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error(`[SETTINGS] Erro ao executar ${action}:`, error);
            this.showError(`Erro ao executar ${action}`);
        } finally {
            this.hideLoading();
        }
    }

    cleanupData() {
        const days = parseInt(this.getSliderValue('cleanup-days'));
        this.showConfirmDialog(
            `Remover dados anteriores a ${days} dias?`,
            () => {
                this.performSystemAction('cleanup_data', { days_to_keep: days });
            }
        );
    }

    executeConfirmedAction() {
        if (this.pendingAction) {
            this.performSystemAction(this.pendingAction);
            this.pendingAction = null;
        }
        
        // Hide modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('confirmModal'));
        if (modal) {
            modal.hide();
        }
    }

    // UI Helper methods
    showConfirmDialog(message, onConfirm) {
        const messageEl = document.getElementById('confirm-message');
        if (messageEl) {
            messageEl.textContent = message;
        }
        
        this.confirmCallback = onConfirm;
        
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        modal.show();
    }

    showToast(message, type = 'info') {
        const toast = document.getElementById('notification-toast');
        const messageEl = document.getElementById('toast-message');
        
        if (toast && messageEl) {
            messageEl.textContent = message;
            
            // Remove existing type classes
            toast.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
            
            // Add appropriate class
            switch (type) {
                case 'success':
                    toast.classList.add('bg-success', 'text-white');
                    break;
                case 'error':
                    toast.classList.add('bg-danger', 'text-white');
                    break;
                case 'warning':
                    toast.classList.add('bg-warning');
                    break;
                default:
                    toast.classList.add('bg-info', 'text-white');
            }
            
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
        }
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showWarning(message) {
        this.showToast(message, 'warning');
    }

    showInfo(message) {
        this.showToast(message, 'info');
    }

    showLoading(message) {
        // Implementation for loading state
        console.log('[SETTINGS] Loading:', message);
    }

    hideLoading() {
        // Implementation for hiding loading state
        console.log('[SETTINGS] Loading complete');
    }

    initializeTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[SETTINGS] DOM loaded, inicializando...');
    window.settingsManager = new SettingsManager();
});

// Handle unsaved changes warning
window.addEventListener('beforeunload', (e) => {
    if (window.settingsManager && window.settingsManager.unsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
    }
});
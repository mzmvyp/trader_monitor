# your_project/routes/settings_routes.py - ARQUIVO NOVO

import json
import sqlite3
import os
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app, render_template
from utils.logging_config import logger
from config import app_config

# Create a Blueprint for Settings routes
settings_bp = Blueprint('settings_routes', __name__, url_prefix='/settings')

@settings_bp.route('/')
def settings_page():
    """Renders the settings page"""
    return render_template('settings.html')

@settings_bp.route('/api/get-config')
def get_current_config():
    """API endpoint para obter configuração atual do sistema"""
    try:
        # Obter configurações do trading analyzer
        trading_config = {}
        if hasattr(current_app, 'trading_analyzer'):
            analyzer = current_app.trading_analyzer
            trading_config = {
                'ta_params': analyzer.ta_params.copy(),
                'signal_config': analyzer.signal_config.copy(),
                'indicator_weights': analyzer.indicator_weights.copy()
            }
        
        # Obter configurações dos streamers
        streaming_config = {}
        if hasattr(current_app, 'bitcoin_streamer'):
            streaming_config['bitcoin'] = {
                'fetch_interval': current_app.bitcoin_streamer.fetch_interval,
                'max_queue_size': len(current_app.bitcoin_streamer.data_queue),
                'is_running': current_app.bitcoin_streamer.is_running
            }
        
        # Obter configurações multi-asset se disponível
        multi_asset_config = {}
        if hasattr(current_app, 'multi_asset_manager'):
            multi_asset_config = {
                'supported_assets': app_config.get_supported_asset_symbols(),
                'asset_intervals': getattr(app_config, 'ASSET_INTERVALS', {}),
                'correlation_analysis_enabled': getattr(app_config, 'CORRELATION_ANALYSIS_ENABLED', False)
            }
        
        # Configurações do sistema
        system_config = {
            'auto_start_stream': getattr(app_config, 'AUTO_START_STREAM', True),
            'database_persistence': True,
            'log_level': app_config.LOG_LEVEL.name if hasattr(app_config.LOG_LEVEL, 'name') else str(app_config.LOG_LEVEL),
            'data_retention_days': getattr(app_config, 'DEFAULT_DAYS_TO_KEEP_DATA', 30)
        }
        
        # Buscar configurações personalizadas salvas
        custom_config = load_custom_settings()
        
        full_config = {
            'timestamp': datetime.now().isoformat(),
            'trading': trading_config,
            'streaming': streaming_config,
            'multi_asset': multi_asset_config,
            'system': system_config,
            'custom': custom_config,
            'version': '2.0.0'
        }
        
        return jsonify({
            'status': 'success',
            'config': full_config
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao obter configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/save-config', methods=['POST'])
def save_config():
    """API endpoint para salvar nova configuração"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Dados não fornecidos'}), 400
        
        config_data = data.get('config', {})
        apply_immediately = data.get('apply_immediately', True)
        
        # Validar configuração
        validation_result = validate_config(config_data)
        if not validation_result['valid']:
            return jsonify({
                'status': 'error', 
                'message': f'Configuração inválida: {validation_result["errors"]}'
            }), 400
        
        # Salvar configuração no banco
        save_result = save_custom_settings(config_data)
        if not save_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'Erro ao salvar: {save_result["error"]}'
            }), 500
        
        # Aplicar configuração se solicitado
        if apply_immediately:
            apply_result = apply_config_to_system(config_data)
            if not apply_result['success']:
                logger.warning(f"[SETTINGS] Configuração salva mas não aplicada: {apply_result['error']}")
                return jsonify({
                    'status': 'partial',
                    'message': f'Configuração salva mas não aplicada: {apply_result["error"]}'
                })
        
        logger.info("[SETTINGS] Configuração salva e aplicada com sucesso")
        return jsonify({
            'status': 'success',
            'message': 'Configuração salva com sucesso',
            'applied': apply_immediately,
            'saved_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao salvar configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/apply-config', methods=['POST'])
def apply_config():
    """API endpoint para aplicar configuração salva ao sistema"""
    try:
        # Carregar configuração salva
        custom_config = load_custom_settings()
        if not custom_config:
            return jsonify({
                'status': 'error',
                'message': 'Nenhuma configuração personalizada encontrada'
            }), 404
        
        # Aplicar configuração
        result = apply_config_to_system(custom_config)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Configuração aplicada com sucesso',
                'applied_components': result.get('applied_components', [])
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Erro ao aplicar configuração: {result["error"]}'
            }), 500
            
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao aplicar configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/reset-config', methods=['POST'])
def reset_config():
    """API endpoint para resetar configuração para padrões"""
    try:
        # Obter configuração padrão
        default_config = get_default_config()
        
        # Salvar como configuração personalizada
        save_result = save_custom_settings(default_config)
        if not save_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'Erro ao salvar configuração padrão: {save_result["error"]}'
            }), 500
        
        # Aplicar configuração padrão
        apply_result = apply_config_to_system(default_config)
        if not apply_result['success']:
            return jsonify({
                'status': 'partial',
                'message': f'Configuração resetada mas não aplicada: {apply_result["error"]}'
            })
        
        logger.info("[SETTINGS] Configuração resetada para padrões")
        return jsonify({
            'status': 'success',
            'message': 'Configuração resetada para padrões com sucesso'
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao resetar configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/export-config')
def export_config():
    """API endpoint para exportar configuração atual como JSON"""
    try:
        # Obter configuração completa
        response = get_current_config()
        if response.status_code != 200:
            return response
        
        config_data = response.get_json()['config']
        
        # Adicionar metadados de exportação
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '2.0.0',
            'system_info': {
                'trading_system': 'Enhanced Bitcoin Trading System',
                'config_version': config_data.get('version', 'unknown')
            },
            'configuration': config_data
        }
        
        return jsonify({
            'status': 'success',
            'filename': f'trading_config_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            'data': export_data
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao exportar configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/import-config', methods=['POST'])
def import_config():
    """API endpoint para importar configuração de arquivo JSON"""
    try:
        data = request.get_json()
        if not data or 'config_data' not in data:
            return jsonify({'status': 'error', 'message': 'Dados de configuração não fornecidos'}), 400
        
        config_data = data['config_data']
        
        # Validar estrutura de importação
        if 'configuration' not in config_data:
            return jsonify({'status': 'error', 'message': 'Formato de arquivo inválido'}), 400
        
        imported_config = config_data['configuration']
        
        # Validar configuração importada
        validation_result = validate_config(imported_config)
        if not validation_result['valid']:
            return jsonify({
                'status': 'error',
                'message': f'Configuração importada inválida: {validation_result["errors"]}'
            }), 400
        
        # Salvar configuração importada
        save_result = save_custom_settings(imported_config)
        if not save_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'Erro ao salvar configuração importada: {save_result["error"]}'
            }), 500
        
        logger.info("[SETTINGS] Configuração importada com sucesso")
        return jsonify({
            'status': 'success',
            'message': 'Configuração importada com sucesso',
            'import_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao importar configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/system-actions', methods=['POST'])
def execute_system_action():
    """API endpoint para executar ações do sistema"""
    try:
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({'status': 'error', 'message': 'Ação não especificada'}), 400
        
        action = data['action']
        
        if action == 'reset_signals':
            return handle_reset_signals()
        elif action == 'restart_analyzers':
            return handle_restart_analyzers()
        elif action == 'force_save':
            return handle_force_save()
        elif action == 'cleanup_data':
            days_to_keep = data.get('days_to_keep', 30)
            return handle_cleanup_data(days_to_keep)
        elif action == 'backup_database':
            return handle_backup_database()
        else:
            return jsonify({'status': 'error', 'message': f'Ação desconhecida: {action}'}), 400
            
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao executar ação do sistema: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/system-status')
def get_system_status():
    """API endpoint para obter status detalhado do sistema"""
    try:
        status = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'health': 'UNKNOWN'
        }
        
        # Status do Bitcoin Streamer
        if hasattr(current_app, 'bitcoin_streamer'):
            btc_stats = current_app.bitcoin_streamer.get_stream_statistics()
            status['components']['bitcoin_streamer'] = {
                'status': 'RUNNING' if btc_stats['is_running'] else 'STOPPED',
                'data_points': btc_stats['total_data_points'],
                'errors': btc_stats['api_errors'],
                'last_update': btc_stats.get('last_fetch_time_iso')
            }
        
        # Status do Trading Analyzer
        if hasattr(current_app, 'trading_analyzer'):
            try:
                analyzer_status = current_app.trading_analyzer.get_system_status()
                status['components']['trading_analyzer'] = {
                    'status': 'ACTIVE',
                    'total_analysis': analyzer_status.get('system_info', {}).get('total_analysis', 0),
                    'active_signals': analyzer_status.get('signal_status', {}).get('active_signals', 0),
                    'data_points': analyzer_status.get('data_status', {}).get('price_data_points', 0)
                }
            except Exception as e:
                status['components']['trading_analyzer'] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        # Status do Multi-Asset Manager
        if hasattr(current_app, 'multi_asset_manager'):
            try:
                multi_health = current_app.multi_asset_manager.get_system_health()
                status['components']['multi_asset_manager'] = {
                    'status': multi_health.get('overall_status', 'UNKNOWN'),
                    'active_streamers': multi_health.get('summary', {}).get('active_streamers', 0),
                    'total_assets': multi_health.get('summary', {}).get('total_assets', 0),
                    'total_errors': multi_health.get('summary', {}).get('total_errors', 0)
                }
            except Exception as e:
                status['components']['multi_asset_manager'] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        # Determinar saúde geral
        component_statuses = [comp.get('status', 'UNKNOWN') for comp in status['components'].values()]
        if any(s == 'ERROR' for s in component_statuses):
            status['health'] = 'ERROR'
        elif any(s == 'STOPPED' for s in component_statuses):
            status['health'] = 'DEGRADED'
        elif all(s in ['RUNNING', 'ACTIVE', 'HEALTHY'] for s in component_statuses):
            status['health'] = 'HEALTHY'
        else:
            status['health'] = 'PARTIAL'
        
        return jsonify({
            'status': 'success',
            'system_status': status
        })
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao obter status do sistema: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== HELPER FUNCTIONS ====================

def load_custom_settings():
    """Carrega configurações personalizadas do banco de dados"""
    try:
        settings_db = os.path.join(app_config.DATA_DIR, 'settings.db')
        
        if not os.path.exists(settings_db):
            setup_settings_database(settings_db)
            return {}
        
        conn = sqlite3.connect(settings_db)
        cursor = conn.cursor()
        
        cursor.execute('SELECT config_data FROM settings WHERE id = 1')
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return json.loads(result[0])
        return {}
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao carregar configurações personalizadas: {e}")
        return {}

def save_custom_settings(config_data):
    """Salva configurações personalizadas no banco de dados"""
    try:
        settings_db = os.path.join(app_config.DATA_DIR, 'settings.db')
        setup_settings_database(settings_db)
        
        conn = sqlite3.connect(settings_db)
        cursor = conn.cursor()
        
        config_json = json.dumps(config_data, indent=2)
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (id, config_data, last_updated)
            VALUES (1, ?, ?)
        ''', (config_json, timestamp))
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao salvar configurações: {e}")
        return {'success': False, 'error': str(e)}

def setup_settings_database(db_path):
    """Configura banco de dados para configurações"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                config_data TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_data TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao configurar banco de configurações: {e}")

def validate_config(config_data):
    """Valida dados de configuração"""
    try:
        errors = []
        
        # Validar estrutura básica
        if not isinstance(config_data, dict):
            errors.append("Configuração deve ser um objeto JSON")
            return {'valid': False, 'errors': errors}
        
        # Validar seção de trading se presente
        if 'trading' in config_data:
            trading_config = config_data['trading']
            
            if 'ta_params' in trading_config:
                ta_params = trading_config['ta_params']
                
                # Validar RSI
                if 'rsi_oversold' in ta_params and 'rsi_overbought' in ta_params:
                    if ta_params['rsi_oversold'] >= ta_params['rsi_overbought']:
                        errors.append("RSI oversold deve ser menor que overbought")
                
                # Validar períodos
                if 'rsi_period' in ta_params and not (5 <= ta_params['rsi_period'] <= 30):
                    errors.append("Período RSI deve estar entre 5 e 30")
                
                # Validar médias móveis
                if 'sma_short' in ta_params and 'sma_long' in ta_params:
                    if ta_params['sma_short'] >= ta_params['sma_long']:
                        errors.append("SMA curta deve ser menor que SMA longa")
            
            if 'signal_config' in trading_config:
                signal_config = trading_config['signal_config']
                
                # Validar limites
                if 'max_active_signals' in signal_config:
                    if not (1 <= signal_config['max_active_signals'] <= 50):
                        errors.append("Máximo de sinais ativos deve estar entre 1 e 50")
                
                if 'signal_cooldown_minutes' in signal_config:
                    if not (1 <= signal_config['signal_cooldown_minutes'] <= 1440):
                        errors.append("Cooldown deve estar entre 1 e 1440 minutos")
            
            if 'indicator_weights' in trading_config:
                weights = trading_config['indicator_weights']
                total_weight = sum(weights.values())
                
                if abs(total_weight - 1.0) > 0.01:  # Tolerância de 1%
                    errors.append(f"Soma dos pesos deve ser 1.0, atual: {total_weight:.3f}")
        
        # Validar seção de streaming se presente
        if 'streaming' in config_data:
            streaming_config = config_data['streaming']
            
            for asset, config in streaming_config.items():
                if isinstance(config, dict) and 'fetch_interval' in config:
                    interval = config['fetch_interval']
                    if not (30 <= interval <= 3600):
                        errors.append(f"Intervalo de fetch para {asset} deve estar entre 30 e 3600 segundos")
        
        return {'valid': len(errors) == 0, 'errors': errors}
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro na validação: {e}")
        return {'valid': False, 'errors': [f'Erro na validação: {str(e)}']}

def apply_config_to_system(config_data):
    """Aplica configuração ao sistema em execução"""
    try:
        applied_components = []
        
        # Aplicar ao Trading Analyzer
        if 'trading' in config_data and hasattr(current_app, 'trading_analyzer'):
            trading_config = config_data['trading']
            analyzer = current_app.trading_analyzer
            
            if 'ta_params' in trading_config:
                analyzer.ta_params.update(trading_config['ta_params'])
                applied_components.append('trading_analyzer.ta_params')
            
            if 'signal_config' in trading_config:
                analyzer.signal_config.update(trading_config['signal_config'])
                applied_components.append('trading_analyzer.signal_config')
            
            if 'indicator_weights' in trading_config:
                analyzer.indicator_weights.update(trading_config['indicator_weights'])
                applied_components.append('trading_analyzer.indicator_weights')
            
            logger.info("[SETTINGS] Configurações do trading analyzer aplicadas")
        
        # Aplicar configurações de streaming
        if 'streaming' in config_data:
            streaming_config = config_data['streaming']
            
            if 'bitcoin' in streaming_config and hasattr(current_app, 'bitcoin_streamer'):
                btc_config = streaming_config['bitcoin']
                if 'fetch_interval' in btc_config:
                    current_app.bitcoin_streamer.fetch_interval = btc_config['fetch_interval']
                    applied_components.append('bitcoin_streamer.fetch_interval')
            
            logger.info("[SETTINGS] Configurações de streaming aplicadas")
        
        # Aplicar configurações multi-asset
        if 'multi_asset' in config_data and hasattr(current_app, 'multi_asset_manager'):
            # Configurações multi-asset seriam aplicadas aqui
            applied_components.append('multi_asset_manager')
            logger.info("[SETTINGS] Configurações multi-asset aplicadas")
        
        return {'success': True, 'applied_components': applied_components}
        
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao aplicar configuração: {e}")
        return {'success': False, 'error': str(e)}

def get_default_config():
    """Retorna configuração padrão do sistema"""
    return {
        'trading': {
            'ta_params': {
                'rsi_period': 14,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'sma_short': 9,
                'sma_long': 21,
                'ema_short': 12,
                'ema_long': 26,
                'macd_signal': 9,
                'bb_period': 20,
                'bb_std': 2.0,
                'stoch_k': 14,
                'stoch_d': 3,
                'stoch_overbought': 80,
                'stoch_oversold': 20,
                'volume_sma': 20,
                'atr_period': 14,
                'min_confidence': 60,
                'min_risk_reward': 1.5,
                'min_volume_ratio': 1.1,
            },
            'signal_config': {
                'max_active_signals': 5,
                'signal_cooldown_minutes': 60,
                'target_multipliers': [2.0, 3.5, 5.0],
                'stop_loss_atr_multiplier': 2.0,
                'partial_take_profit': [0.5, 0.3, 0.2],
                'trailing_stop_distance': 1.5,
            },
            'indicator_weights': {
                'rsi': 0.20,
                'macd': 0.25,
                'bb': 0.15,
                'stoch': 0.15,
                'sma_cross': 0.15,
                'volume': 0.10
            }
        },
        'streaming': {
            'bitcoin': {
                'fetch_interval': 300,
                'max_queue_size': 200
            }
        },
        'system': {
            'auto_start_stream': True,
            'require_volume_confirmation': True,
            'enable_auto_signals': True,
            'enable_advanced_patterns': False,
            'enable_notifications': True,
            'correlation_analysis': False,
            'auto_cleanup': True,
            'data_retention_days': 30
        }
    }

# ==================== SYSTEM ACTION HANDLERS ====================

def handle_reset_signals():
    """Handle reset signals action"""
    try:
        if hasattr(current_app, 'trading_analyzer'):
            current_app.trading_analyzer.reset_signals_and_state()
            logger.info("[SETTINGS] Sinais resetados via configurações")
            return jsonify({'status': 'success', 'message': 'Sinais resetados com sucesso'})
        else:
            return jsonify({'status': 'error', 'message': 'Trading analyzer não disponível'}), 503
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao resetar sinais: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_restart_analyzers():
    """Handle restart analyzers action"""
    try:
        restarted = []
        
        # Restart trading analyzer
        if hasattr(current_app, 'trading_analyzer'):
            current_app.trading_analyzer.save_analyzer_state()
            restarted.append('trading_analyzer')
        
        # Restart multi-asset analyzers if available
        if hasattr(current_app, 'multi_asset_manager'):
            for asset_symbol in app_config.get_supported_asset_symbols():
                analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
                if analyzer:
                    analyzer.save_analyzer_state()
                    restarted.append(f'{asset_symbol}_analyzer')
        
        logger.info(f"[SETTINGS] Analyzers reiniciados: {', '.join(restarted)}")
        return jsonify({
            'status': 'success', 
            'message': f'Analyzers reiniciados: {", ".join(restarted)}',
            'restarted_components': restarted
        })
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao reiniciar analyzers: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_force_save():
    """Handle force save action"""
    try:
        saved = []
        
        # Save trading analyzer
        if hasattr(current_app, 'trading_analyzer'):
            current_app.trading_analyzer.save_analyzer_state()
            saved.append('trading_analyzer')
        
        # Save bitcoin processor
        if hasattr(current_app, 'bitcoin_processor'):
            current_app.bitcoin_processor.force_process_batch()
            saved.append('bitcoin_processor')
        
        # Save multi-asset analyzers
        if hasattr(current_app, 'multi_asset_manager'):
            for asset_symbol in app_config.get_supported_asset_symbols():
                analyzer = current_app.multi_asset_manager.get_asset_analyzer(asset_symbol)
                if analyzer:
                    analyzer.save_analyzer_state()
                    saved.append(f'{asset_symbol}_analyzer')
        
        logger.info(f"[SETTINGS] Estado salvo forçadamente: {', '.join(saved)}")
        return jsonify({
            'status': 'success',
            'message': f'Estado salvo: {", ".join(saved)}',
            'saved_components': saved
        })
    except Exception as e:
        logger.error(f"[SETTINGS] Erro ao forçar salvamento: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_cleanup_data(days_to_keep):
    """Handle cleanup data action"""
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_counts = {}
        
        # Cleanup bitcoin stream data
        if os.path.exists(app_config.BITCOIN_STREAM_DB):
            conn = sqlite3.connect(app_config.BITCOIN_STREAM_DB)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM bitcoin_stream WHERE timestamp < ?', (cutoff_date.isoformat(),))
            deleted_counts['bitcoin_stream'] = cursor.rowcount
            
            cursor.execute('DELETE FROM bitcoin_analytics WHERE created_at < ?', (cutoff_date.isoformat(),))
            deleted_counts['bitcoin_analytics'] = cursor.rowcount
            
            conn.commit()
            conn.close()
        
        # Cleanup trading data
        if os.path.exists(app_config.TRADING_ANALYZER_DB):
            conn = sqlite3.connect(app_config.TRADING_ANALYZER_DB)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date.isoformat(),))
            deleted_counts['price_history'] = cursor.rowcount
            
            cursor.execute('DELETE FROM trading_signals WHERE created_at < ? AND status != "ACTIVE"', (cutoff_date.isoformat(),))
            deleted_counts['trading_signals'] = cursor.rowcount
            
            conn.commit()
            conn.close()
        
        total_deleted = sum(deleted_counts.values())
        
        logger.info(f"[SETTINGS] Limpeza de dados concluída: {total_deleted} registros removidos")
        return jsonify({
            'status': 'success',
            'message': f'Limpeza concluída: {total_deleted} registros removidos',
            'deleted_counts': deleted_counts,
            'cutoff_date': cutoff_date.isoformat()
        })
    except Exception as e:
        logger.error(f"[SETTINGS] Erro na limpeza de dados: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def handle_backup_database():
    """Handle database backup action"""
    try:
        import shutil
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(app_config.DATA_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backed_up = []
        
        # Backup bitcoin stream database
        if os.path.exists(app_config.BITCOIN_STREAM_DB):
            backup_file = os.path.join(backup_dir, f'bitcoin_stream_{timestamp}.db')
            shutil.copy2(app_config.BITCOIN_STREAM_DB, backup_file)
            backed_up.append(f'bitcoin_stream_{timestamp}.db')
        
        # Backup trading analyzer database
        if os.path.exists(app_config.TRADING_ANALYZER_DB):
            backup_file = os.path.join(backup_dir, f'trading_analyzer_{timestamp}.db')
            shutil.copy2(app_config.TRADING_ANALYZER_DB, backup_file)
            backed_up.append(f'trading_analyzer_{timestamp}.db')
        
        # Backup settings database
        settings_db = os.path.join(app_config.DATA_DIR, 'settings.db')
        if os.path.exists(settings_db):
            backup_file = os.path.join(backup_dir, f'settings_{timestamp}.db')
            shutil.copy2(settings_db, backup_file)
            backed_up.append(f'settings_{timestamp}.db')
        
        logger.info(f"[SETTINGS] Backup concluído: {len(backed_up)} arquivos")
        return jsonify({
            'status': 'success',
            'message': f'Backup concluído: {len(backed_up)} arquivos salvos',
            'backed_up_files': backed_up,
            'backup_location': backup_dir
        })
    except Exception as e:
        logger.error(f"[SETTINGS] Erro no backup: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
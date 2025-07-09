# your_project/routes/main_routes.py - ADICIONAR estas modificações ao arquivo existente

from typing import List
from flask import Blueprint, render_template, jsonify, current_app, request
from datetime import datetime
from utils.logging_config import logger
from typing import List, Dict

# Create a Blueprint for main routes
main_bp = Blueprint('main_routes', __name__)

@main_bp.route('/')
def dashboard():
    """
    Renders the main integrated dashboard HTML page.
    This is the entry point for the web interface.
    === MANTIDO: Função original inalterada ===
    """
    return render_template('integrated_dashboard.html')

@main_bp.route('/bitcoin/')
def bitcoin_dashboard():
    """
    Renders the Bitcoin-specific dashboard HTML page.
    === MANTIDO: Função original inalterada ===
    """
    return render_template('bitcoin_dashboard.html')
        
@main_bp.route('/trading/')
def trading_dashboard():
    """
    Renders the trading-specific dashboard HTML page.
    === MANTIDO: Função original inalterada ===
    """
    return render_template('trading_dashboard.html')

# === NOVO: Multi-Asset Dashboard Route ===
@main_bp.route('/multi-asset/')
def multi_asset_dashboard():
    """
    Renders the multi-asset dashboard HTML page.
    """
    return render_template('multi_asset_dashboard.html')

@main_bp.route('/api/integrated/status')
def get_integrated_status():
    """
    Fornece uma visão geral do status de alto nível de todo o sistema integrado.
    === MODIFICADO: Adicionar dados multi-asset ===
    """
    try:
        # === MANTIDO: Obter estatísticas do streaming de Bitcoin original ===
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        
        # === MANTIDO: Obter saúde do analisador de trading ===
        trading_health = current_app.trading_analyzer.get_system_status()
        
        # === MANTIDO: Obter o preço mais recente dos dados recentes ===
        recent_bitcoin_data = current_app.bitcoin_streamer.get_recent_data(1)
        latest_price = recent_bitcoin_data[0].price if recent_bitcoin_data else 0

        # === MANTIDO: Determinar se a análise está pronta ===
        analysis_ready = trading_health.get('indicator_status') == 'ACTIVE'

        # === MANTIDO: Somar o total de pontos de dados do streamer e do analisador ===
        total_system_data_points = bitcoin_stats.get('total_data_points', 0) + \
                                   trading_health.get('total_analysis_performed', 0)
        
        # === NOVO: Obter dados multi-asset ===
        multi_asset_overview = {}
        multi_asset_health = {}
        try:
            multi_asset_overview = current_app.multi_asset_manager.get_overview_data()
            multi_asset_health = current_app.multi_asset_manager.get_system_health()
            
            # Somar pontos de dados de todos os assets
            for asset_data in multi_asset_overview.get('assets', {}).values():
                if 'error' not in asset_data:
                    streaming_data = asset_data.get('streaming', {})
                    total_system_data_points += streaming_data.get('data_points', 0)
                    
        except Exception as e:
            logger.warning(f"[INTEGRATED] Erro ao obter dados multi-asset: {e}")
            multi_asset_overview = {'error': str(e)}
            multi_asset_health = {'error': str(e)}
        
        response_data = {
            # === MANTIDO: Dados Bitcoin originais ===
            'bitcoin': {
                'metrics': {
                    'min_price': bitcoin_stats.get('min_price', 0),
                    'max_price': bitcoin_stats.get('max_price', 0),
                    'avg_change_24h': bitcoin_stats.get('avg_change_24h', 0),
                    'price_range': bitcoin_stats.get('price_range', 0),
                    'last_update': bitcoin_stats.get('last_fetch_time_iso', datetime.now().isoformat()),
                    'total_records': bitcoin_stats.get('total_data_points', 0)
                },
                'recent_data': [data.to_dict() for data in current_app.bitcoin_streamer.get_recent_data(10)],
                'streaming': bitcoin_stats.get('is_running', False),
                'stats': {
                    'is_running': bitcoin_stats.get('is_running', False),
                    'total_data_points': bitcoin_stats.get('total_data_points', 0),
                    'api_errors': bitcoin_stats.get('api_errors', 0),
                    'last_fetch_time': bitcoin_stats.get('last_fetch_time_iso', None),
                    'last_price': latest_price,
                    'queue_size': bitcoin_stats.get('queue_size', 0),
                    'subscribers_count': bitcoin_stats.get('subscribers_count', 0),
                    'source': bitcoin_stats.get('source', 'binance'),
                    'fetch_interval_minutes': bitcoin_stats.get('fetch_interval_minutes', 5)
                }
            },
            # === MANTIDO: Dados trading originais ===
            'trading': {
                'current_price': latest_price,
                'indicators': {},
                'active_signals': len(current_app.trading_analyzer.signals) if hasattr(current_app.trading_analyzer, 'signals') else 0,
                'recent_signals': [s.to_dict() for s in current_app.trading_analyzer.signals[-5:]] if hasattr(current_app.trading_analyzer, 'signals') and len(current_app.trading_analyzer.signals) > 0 else [],
                'pattern_stats': [],
                'system_info': {
                    'analysis_count': trading_health.get('total_analysis_performed', 0),
                    'data_points': trading_health.get('total_analysis_performed', 0),
                    'last_analysis': trading_health.get('last_analysis_time', None)
                }
            },
            # === MODIFICADO: Status integrado com dados multi-asset ===
            'integrated_status': {
                'total_data_points': total_system_data_points,
                'analysis_ready': analysis_ready,
                'last_update': datetime.now().isoformat(),
                'system_healthy': bitcoin_stats.get('is_running', False) and analysis_ready,
                'persistence_enabled': current_app.config.get('DATABASE_PERSISTENCE', False),
                # === NOVO: Dados multi-asset no status integrado ===
                'multi_asset_enabled': True,
                'total_assets_supported': len(current_app.config.get('SUPPORTED_ASSETS', {})),
                'multi_asset_healthy': multi_asset_health.get('overall_status', 'UNKNOWN') in ['HEALTHY', 'PARTIAL']
            },
            # === NOVO: Seção dedicada ao multi-asset ===
            'multi_asset': {
                'overview': multi_asset_overview,
                'health': multi_asset_health,
                'supported_assets': current_app.config.get('SUPPORTED_ASSETS', {}),
                'total_active_streamers': multi_asset_health.get('summary', {}).get('active_streamers', 0)
            },
            'system_info': {
                'app_version': '2.0.0-multi-asset',  # === MODIFICADO: Versão atualizada ===
                'environment': 'development'
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[API] Erro ao obter status integrado: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@main_bp.route('/api/integrated/dashboard-data')
def get_dashboard_data():
    """
    Provides a comprehensive set of data for the integrated dashboard.
    === MODIFICADO: Adicionar dados multi-asset ===
    """
    try:
        # === MANTIDO: Get Bitcoin metrics and data ===
        bitcoin_metrics = current_app.bitcoin_analytics.get_real_time_metrics()
        recent_bitcoin = current_app.bitcoin_streamer.get_recent_data(20)
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        
        # === MANTIDO: Get trading analysis ===
        trading_analysis = current_app.trading_analyzer.get_current_analysis()
        
        # === MANTIDO: Get system health ===
        trading_health = current_app.trading_analyzer.get_system_status()
        
        # === NOVO: Get multi-asset data ===
        multi_asset_data = {}
        try:
            multi_asset_data = {
                'overview': current_app.multi_asset_manager.get_overview_data(),
                'health': current_app.multi_asset_manager.get_system_health(),
                'consolidated_signals': current_app.multi_asset_manager.get_consolidated_signals(10)
            }
        except Exception as e:
            logger.warning(f"[DASHBOARD] Erro ao obter dados multi-asset: {e}")
            multi_asset_data = {'error': str(e)}
        
        return jsonify({
            # === MANTIDO: Dados Bitcoin originais ===
            'bitcoin': {
                'metrics': bitcoin_metrics,
                'recent_data': [data.to_dict() for data in recent_bitcoin],
                'streaming': bitcoin_stats['is_running'],
                'stats': bitcoin_stats
            },
            # === MANTIDO: Dados trading originais ===
            'trading': trading_analysis,
            # === MODIFICADO: Status integrado com multi-asset ===
            'integrated_status': {
                'total_data_points': bitcoin_stats['total_data_points'],
                'analysis_ready': len(current_app.trading_analyzer.price_history) >= 30,
                'last_update': datetime.now().isoformat(),
                'system_healthy': bitcoin_stats['is_running'] and len(current_app.trading_analyzer.price_history) > 0,
                'persistence_enabled': True,
                # === NOVO: Dados multi-asset ===
                'multi_asset_enabled': True,
                'multi_asset_healthy': multi_asset_data.get('health', {}).get('overall_status', 'UNKNOWN') in ['HEALTHY', 'PARTIAL'],
                'total_assets_supported': len(current_app.config.get('SUPPORTED_ASSETS', {}))
            },
            # === NOVO: Dados multi-asset ===
            'multi_asset': multi_asset_data
        })
        
    except Exception as e:
        logger.error(f"[API] Erro ao obter dados do dashboard: {e}")
        return jsonify({
            # === MANTIDO: Dados de fallback originais ===
            'bitcoin': {
                'metrics': {
                    'data_points': 0,
                    'avg_price': 0,
                    'min_price': 0,
                    'max_price': 0,
                    'avg_change_24h': 0,
                    'price_range': 0,
                    'last_update': datetime.now().isoformat(),
                    'total_records': 0
                },
                'recent_data': [],
                'streaming': False,
                'stats': {
                    'is_running': False,
                    'total_data_points': 0,
                    'api_errors': 0,
                    'last_fetch_time': 0,
                    'last_price': 0,
                    'queue_size': 0,
                    'subscribers_count': 0,
                    'source': 'binance',
                    'fetch_interval_minutes': 5
                }
            },
            'trading': {
                'current_price': 0,
                'indicators': {},
                'active_signals': 0,
                'recent_signals': [],
                'pattern_stats': [],
                'system_info': {
                    'analysis_count': 0,
                    'data_points': 0,
                    'last_analysis': None
                }
            },
            'integrated_status': {
                'total_data_points': 0,
                'analysis_ready': False,
                'last_update': datetime.now().isoformat(),
                'system_healthy': False,
                'persistence_enabled': True,
                # === NOVO: Fallback multi-asset ===
                'multi_asset_enabled': True,
                'multi_asset_healthy': False,
                'total_assets_supported': 0
            },
            # === NOVO: Multi-asset fallback ===
            'multi_asset': {
                'error': str(e),
                'overview': {},
                'health': {'overall_status': 'ERROR'},
                'consolidated_signals': []
            },
            'error': str(e)
        }), 500

# === NOVO: API Routes específicas para compatibilidade multi-asset ===

@main_bp.route('/api/assets/list')
def get_assets_list():
    """API endpoint para lista simples de assets suportados"""
    try:
        from config import app_config
        assets = []
        for symbol in app_config.get_supported_asset_symbols():
            config = app_config.get_asset_config(symbol)
            assets.append({
                'symbol': symbol,
                'name': config['name'],
                'color': config['color'],
                'icon': config['icon']
            })
        
        return jsonify({
            'assets': assets,
            'count': len(assets),
            'default': app_config.DEFAULT_ASSET
        })
    except Exception as e:
        logger.error(f"[API] Erro ao obter lista de assets: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/quick-overview')
def get_quick_overview():
    """API endpoint para overview rápido (dados essenciais para header/navbar)"""
    try:
        # Dados Bitcoin originais
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        recent_bitcoin = current_app.bitcoin_streamer.get_recent_data(1)
        btc_price = recent_bitcoin[0].price if recent_bitcoin else 0
        
        # Multi-asset summary
        multi_asset_summary = {
            'total_assets': 0,
            'active_streamers': 0,
            'total_signals': 0,
            'prices': {}
        }
        
        try:
            multi_health = current_app.multi_asset_manager.get_system_health()
            multi_overview = current_app.multi_asset_manager.get_overview_data()
            
            multi_asset_summary.update({
                'total_assets': multi_health.get('summary', {}).get('total_assets', 0),
                'active_streamers': multi_health.get('summary', {}).get('active_streamers', 0),
                'total_signals': multi_overview.get('totals', {}).get('total_signals', 0)
            })
            
            # Preços atuais de todos os assets
            for asset_symbol, asset_data in multi_overview.get('assets', {}).items():
                if 'error' not in asset_data:
                    price = asset_data.get('streaming', {}).get('current_price', 0)
                    if price > 0:
                        multi_asset_summary['prices'][asset_symbol] = price
                        
        except Exception as e:
            logger.debug(f"[QUICK] Multi-asset não disponível: {e}")
        
        return jsonify({
            'bitcoin': {
                'price': btc_price,
                'streaming': bitcoin_stats.get('is_running', False),
                'data_points': bitcoin_stats.get('total_data_points', 0)
            },
            'multi_asset': multi_asset_summary,
            'system': {
                'healthy': bitcoin_stats.get('is_running', False),
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"[API] Erro ao obter overview rápido: {e}")
        return jsonify({'error': str(e)}), 500
    
    # routes/main_routes.py - ADIÇÕES para mostrar dados de configuração no dashboard

# Adicionar estas rotas ao arquivo main_routes.py existente

@main_bp.route('/api/integrated/config-status')
def get_config_status():
    """API endpoint para status das configurações no dashboard principal"""
    try:
        from config_manager import dynamic_config_manager
        from middleware.config_middleware import config_middleware
        
        # Obter configuração atual
        current_config = dynamic_config_manager.current_config
        
        # Obter status do middleware
        middleware_status = config_middleware.get_middleware_status()
        
        # Obter histórico recente de mudanças
        recent_history = config_middleware.get_application_history(limit=5)
        
        # Validar configuração atual
        validation = dynamic_config_manager.validate_config(current_config)
        
        # Estatísticas de configuração
        config_stats = {
            'total_settings': len(dynamic_config_manager._flatten_config(current_config)),
            'last_updated': middleware_status.get('last_apply_time'),
            'auto_refresh_enabled': middleware_status.get('auto_refresh_enabled', False),
            'unsaved_changes': len(config_middleware.config_cache) > 0,
            'validation_status': 'valid' if validation['valid'] else 'invalid',
            'validation_errors': len(validation.get('errors', [])),
            'validation_warnings': len(validation.get('warnings', []))
        }
        
        # Resumo por categoria
        category_summary = {}
        if 'trading' in current_config:
            category_summary['trading'] = {
                'ta_params_count': len(current_config['trading'].get('ta_params', {})),
                'signal_config_count': len(current_config['trading'].get('signal_config', {})),
                'weights_configured': 'indicator_weights' in current_config['trading']
            }
        
        if 'streaming' in current_config:
            category_summary['streaming'] = {
                'assets_configured': len(current_config['streaming']),
                'intervals_set': sum(1 for asset in current_config['streaming'].values() 
                                   if isinstance(asset, dict) and 'fetch_interval' in asset)
            }
        
        if 'system' in current_config:
            system_config = current_config['system']
            category_summary['system'] = {
                'features_enabled': sum(1 for v in system_config.values() if v is True),
                'total_features': len(system_config)
            }
        
        return jsonify({
            'status': 'success',
            'config_status': {
                'stats': config_stats,
                'middleware_status': middleware_status,
                'category_summary': category_summary,
                'recent_changes': recent_history,
                'validation': validation,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"[DASHBOARD] Erro ao obter status de configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main_bp.route('/api/integrated/config-alerts')
def get_config_alerts():
    """API endpoint para alertas de configuração"""
    try:
        from config_manager import dynamic_config_manager
        from middleware.config_middleware import config_middleware
        
        alerts = []
        current_config = dynamic_config_manager.current_config
        
        # Verificar validação
        validation = dynamic_config_manager.validate_config(current_config)
        if not validation['valid']:
            alerts.append({
                'type': 'error',
                'title': 'Configuração Inválida',
                'message': f"Encontrados {len(validation['errors'])} erros de configuração",
                'details': validation['errors'][:3],  # Primeiros 3 erros
                'action': 'settings',
                'priority': 'high'
            })
        
        if validation.get('warnings'):
            alerts.append({
                'type': 'warning',
                'title': 'Avisos de Configuração',
                'message': f"Encontrados {len(validation['warnings'])} avisos",
                'details': validation['warnings'][:3],
                'action': 'review',
                'priority': 'medium'
            })
        
        # Verificar se middleware está funcionando
        middleware_status = config_middleware.get_middleware_status()
        if not middleware_status.get('auto_refresh_enabled', False):
            alerts.append({
                'type': 'info',
                'title': 'Auto-refresh Desabilitado',
                'message': 'Mudanças automáticas de configuração não serão detectadas',
                'action': 'enable_refresh',
                'priority': 'low'
            })
        
        # Verificar configurações críticas
        critical_checks = _perform_critical_config_checks(current_config)
        alerts.extend(critical_checks)
        
        # Verificar histórico recente por problemas
        recent_history = config_middleware.get_application_history(limit=10)
        failed_applications = [h for h in recent_history if not h.get('success', True)]
        
        if failed_applications:
            alerts.append({
                'type': 'error',
                'title': 'Falhas na Aplicação',
                'message': f"{len(failed_applications)} tentativas de aplicação falharam recentemente",
                'details': [f["error"] for f in failed_applications[:3] if 'error' in f],
                'action': 'check_logs',
                'priority': 'high'
            })
        
        # Ordenar por prioridade
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        alerts.sort(key=lambda x: priority_order.get(x['priority'], 2))
        
        return jsonify({
            'status': 'success',
            'alerts': alerts,
            'alert_count': len(alerts),
            'high_priority_count': len([a for a in alerts if a['priority'] == 'high']),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"[DASHBOARD] Erro ao obter alertas de configuração: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _perform_critical_config_checks(config: Dict) -> List[Dict]:
    """Realiza verificações críticas na configuração"""
    alerts = []
    
    try:
        # Verificar se pesos dos indicadores somam 1.0
        if 'trading' in config and 'indicator_weights' in config['trading']:
            weights = config['trading']['indicator_weights']
            total_weight = sum(weights.values()) if weights else 0
            
            if abs(total_weight - 1.0) > 0.01:
                alerts.append({
                    'type': 'error',
                    'title': 'Pesos dos Indicadores Incorretos',
                    'message': f'Soma dos pesos é {total_weight:.3f}, deveria ser 1.000',
                    'action': 'fix_weights',
                    'priority': 'high'
                })
        
        # Verificar intervalos de streaming muito baixos
        if 'streaming' in config:
            for asset, asset_config in config['streaming'].items():
                if isinstance(asset_config, dict):
                    interval = asset_config.get('fetch_interval', 300)
                    if interval < 60:
                        alerts.append({
                            'type': 'warning',
                            'title': 'Intervalo de Streaming Muito Baixo',
                            'message': f'{asset}: {interval}s pode causar rate limiting',
                            'action': 'increase_interval',
                            'priority': 'medium'
                        })
        
        # Verificar configurações de confiança muito baixas
        if 'trading' in config and 'ta_params' in config['trading']:
            min_confidence = config['trading']['ta_params'].get('min_confidence', 60)
            if min_confidence < 50:
                alerts.append({
                    'type': 'warning',
                    'title': 'Confiança Mínima Muito Baixa',
                    'message': f'Confiança de {min_confidence}% pode gerar muitos sinais falsos',
                    'action': 'increase_confidence',
                    'priority': 'medium'
                })
        
        # Verificar muitos sinais ativos simultâneos
        if 'trading' in config and 'signal_config' in config['trading']:
            max_signals = config['trading']['signal_config'].get('max_active_signals', 5)
            if max_signals > 20:
                alerts.append({
                    'type': 'warning',
                    'title': 'Muitos Sinais Ativos',
                    'message': f'{max_signals} sinais simultâneos podem impactar performance',
                    'action': 'reduce_signals',
                    'priority': 'medium'
                })
        
    except Exception as e:
        logger.error(f"[DASHBOARD] Erro nas verificações críticas: {e}")
    
    return alerts

@main_bp.route('/api/integrated/config-quick-actions', methods=['POST'])
def execute_config_quick_action():
    """API endpoint para ações rápidas de configuração"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        from config_manager import dynamic_config_manager
        from middleware.config_middleware import config_middleware
        
        if action == 'fix_weights':
            # Corrigir pesos dos indicadores para somar 1.0
            current_config = dynamic_config_manager.current_config.copy()
            
            if 'trading' in current_config and 'indicator_weights' in current_config['trading']:
                weights = current_config['trading']['indicator_weights']
                total = sum(weights.values())
                
                if total > 0:
                    # Normalizar pesos
                    for key in weights:
                        weights[key] = weights[key] / total
                    
                    # Aplicar configuração corrigida
                    result = config_middleware.intercept_config_change(
                        current_config, 
                        'dashboard_fix_weights', 
                        apply_immediately=True
                    )
                    
                    if result['success']:
                        return jsonify({
                            'status': 'success',
                            'message': 'Pesos dos indicadores corrigidos e aplicados',
                            'new_weights': weights
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': f"Erro ao aplicar correção: {result.get('error', 'Desconhecido')}"
                        }), 500
            
            return jsonify({
                'status': 'error',
                'message': 'Configuração de pesos não encontrada'
            }), 400
        
        elif action == 'enable_refresh':
            # Habilitar auto-refresh do middleware
            config_middleware.auto_refresh_enabled = True
            config_middleware.start_auto_refresh()
            
            return jsonify({
                'status': 'success',
                'message': 'Auto-refresh habilitado'
            })
        
        elif action == 'reset_middleware':
            # Resetar estado do middleware
            config_middleware.clear_history()
            config_middleware.force_config_sync()
            
            return jsonify({
                'status': 'success',
                'message': 'Middleware resetado e sincronizado'
            })
        
        elif action == 'validate_and_fix':
            # Validar e tentar corrigir automaticamente problemas comuns
            current_config = dynamic_config_manager.current_config.copy()
            validation = dynamic_config_manager.validate_config(current_config)
            
            fixes_applied = []
            
            if not validation['valid']:
                # Tentar corrigir automaticamente alguns problemas
                if 'trading' in current_config:
                    trading_config = current_config['trading']
                    
                    # Corrigir RSI oversold >= overbought
                    if 'ta_params' in trading_config:
                        ta_params = trading_config['ta_params']
                        if (ta_params.get('rsi_oversold', 30) >= ta_params.get('rsi_overbought', 70)):
                            ta_params['rsi_oversold'] = 30
                            ta_params['rsi_overbought'] = 70
                            fixes_applied.append('Corrigido RSI oversold/overbought')
                        
                        # Corrigir SMA curta >= longa
                        if (ta_params.get('sma_short', 9) >= ta_params.get('sma_long', 21)):
                            ta_params['sma_short'] = 9
                            ta_params['sma_long'] = 21
                            fixes_applied.append('Corrigido períodos SMA')
                        
                        # Corrigir EMA curta >= longa
                        if (ta_params.get('ema_short', 12) >= ta_params.get('ema_long', 26)):
                            ta_params['ema_short'] = 12
                            ta_params['ema_long'] = 26
                            fixes_applied.append('Corrigido períodos EMA')
                
                # Aplicar correções se houver
                if fixes_applied:
                    result = config_middleware.intercept_config_change(
                        current_config,
                        'dashboard_auto_fix',
                        apply_immediately=True
                    )
                    
                    if result['success']:
                        return jsonify({
                            'status': 'success',
                            'message': f'{len(fixes_applied)} problemas corrigidos automaticamente',
                            'fixes_applied': fixes_applied
                        })
                    else:
                        return jsonify({
                            'status': 'partial',
                            'message': 'Correções identificadas mas não foi possível aplicar',
                            'fixes_identified': fixes_applied,
                            'error': result.get('error')
                        })
                else:
                    return jsonify({
                        'status': 'info',
                        'message': 'Problemas encontrados mas correção automática não disponível',
                        'validation_errors': validation['errors']
                    })
            else:
                return jsonify({
                    'status': 'success',
                    'message': 'Configuração já está válida'
                })
        
        else:
            return jsonify({
                'status': 'error',
                'message': f'Ação desconhecida: {action}'
            }), 400
        
    except Exception as e:
        logger.error(f"[DASHBOARD] Erro na ação rápida: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== COMPONENT PARA O FRONTEND ====================

def get_config_dashboard_data():
    """
    Função utilitária para obter todos os dados de configuração para o dashboard.
    Esta função pode ser usada pelo frontend para obter um resumo completo.
    """
    try:
        from config_manager import dynamic_config_manager
        from middleware.config_middleware import config_middleware
        
        # Compilar todos os dados
        dashboard_data = {
            'config_status': {},
            'alerts': [],
            'quick_actions': [],
            'statistics': {},
            'health_score': 0
        }
        
        # Status da configuração
        current_config = dynamic_config_manager.current_config
        validation = dynamic_config_manager.validate_config(current_config)
        middleware_status = config_middleware.get_middleware_status()
        
        dashboard_data['config_status'] = {
            'is_valid': validation['valid'],
            'error_count': len(validation.get('errors', [])),
            'warning_count': len(validation.get('warnings', [])),
            'last_applied': middleware_status.get('last_apply_time'),
            'auto_refresh': middleware_status.get('auto_refresh_enabled', False),
            'total_settings': len(dynamic_config_manager._flatten_config(current_config))
        }
        
        # Calcular score de saúde (0-100)
        health_score = 100
        if not validation['valid']:
            health_score -= len(validation['errors']) * 10
        health_score -= len(validation.get('warnings', [])) * 5
        if not middleware_status.get('auto_refresh_enabled', False):
            health_score -= 5
        
        dashboard_data['health_score'] = max(0, min(100, health_score))
        
        # Ações rápidas disponíveis
        quick_actions = []
        
        if not validation['valid']:
            quick_actions.append({
                'id': 'validate_and_fix',
                'label': 'Corrigir Automaticamente',
                'icon': 'fas fa-magic',
                'type': 'primary'
            })
        
        # Verificar pesos dos indicadores
        if 'trading' in current_config and 'indicator_weights' in current_config['trading']:
            weights = current_config['trading']['indicator_weights']
            total_weight = sum(weights.values()) if weights else 0
            if abs(total_weight - 1.0) > 0.01:
                quick_actions.append({
                    'id': 'fix_weights',
                    'label': 'Corrigir Pesos',
                    'icon': 'fas fa-balance-scale',
                    'type': 'warning'
                })
        
        if not middleware_status.get('auto_refresh_enabled', False):
            quick_actions.append({
                'id': 'enable_refresh',
                'label': 'Habilitar Auto-refresh',
                'icon': 'fas fa-sync',
                'type': 'info'
            })
        
        dashboard_data['quick_actions'] = quick_actions
        
        # Estatísticas
        recent_history = config_middleware.get_application_history(limit=20)
        successful_applications = len([h for h in recent_history if h.get('success', True)])
        
        dashboard_data['statistics'] = {
            'total_applications': len(recent_history),
            'successful_applications': successful_applications,
            'success_rate': (successful_applications / len(recent_history) * 100) if recent_history else 100,
            'callbacks_registered': middleware_status.get('callbacks_registered', 0),
            'cache_size': len(config_middleware.config_cache)
        }
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"[DASHBOARD] Erro ao compilar dados: {e}")
        return {
            'config_status': {'is_valid': False, 'error_count': 1},
            'alerts': [{'type': 'error', 'message': f'Erro ao carregar dados: {str(e)}'}],
            'quick_actions': [],
            'statistics': {},
            'health_score': 0
        }
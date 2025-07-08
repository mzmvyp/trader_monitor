# your_project/routes/main_routes.py - ADICIONAR estas modificações ao arquivo existente

from flask import Blueprint, render_template, jsonify, current_app
from datetime import datetime
from utils.logging_config import logger

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
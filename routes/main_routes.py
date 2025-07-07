# your_project/routes/main_routes.py

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
    """
    return render_template('integrated_dashboard.html')

@main_bp.route('/bitcoin/')
def bitcoin_dashboard():
    """
    Renders the Bitcoin-specific dashboard HTML page.
    """
    return render_template('bitcoin_dashboard.html')
        
@main_bp.route('/trading/')
def trading_dashboard():
    """
    Renders the trading-specific dashboard HTML page.
    """
    return render_template('trading_dashboard.html')

@main_bp.route('/api/integrated/status')
def get_integrated_status():
    """
    Fornece uma visão geral do status de alto nível de todo o sistema integrado.
    """
    try:
        # Obter estatísticas do streaming de Bitcoin
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        
        # Obter saúde do analisador de trading
        trading_health = current_app.trading_analyzer.get_system_status()
        
        # Obter o preço mais recente dos dados recentes
        recent_bitcoin_data = current_app.bitcoin_streamer.get_recent_data(1)
        latest_price = recent_bitcoin_data[0].price if recent_bitcoin_data else 0

        # Determinar se a análise está pronta com base no status do analisador
        analysis_ready = trading_health.get('indicator_status') == 'ACTIVE'

        # Somar o total de pontos de dados do streamer e do analisador
        total_system_data_points = bitcoin_stats.get('total_data_points', 0) + \
                                   trading_health.get('total_analysis_performed', 0) # Use a nova chave aqui!
        
        response_data = {
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
            'trading': {
                'current_price': latest_price,
                'indicators': {}, # Geralmente populado por /trading/api/analysis
                'active_signals': len(current_app.trading_analyzer.signals) if hasattr(current_app.trading_analyzer, 'signals') else 0,
                'recent_signals': [s.to_dict() for s in current_app.trading_analyzer.signals[-5:]] if hasattr(current_app.trading_analyzer, 'signals') and len(current_app.trading_analyzer.signals) > 0 else [],
                'pattern_stats': [], # Se você tiver isso do analisador
                'system_info': {
                    'analysis_count': trading_health.get('total_analysis_performed', 0), # Usar a nova chave
                    'data_points': trading_health.get('total_analysis_performed', 0), # Mapear para data_points aqui
                    'last_analysis': trading_health.get('last_analysis_time', None)
                }
            },
            'integrated_status': {
                'total_data_points': total_system_data_points,
                'analysis_ready': analysis_ready,
                'last_update': datetime.now().isoformat(),
                'system_healthy': bitcoin_stats.get('is_running', False) and analysis_ready,
                'persistence_enabled': current_app.config.get('DATABASE_PERSISTENCE', False)
            },
            'system_info': {
                'app_version': '1.0.0',
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
    """
    try:
        # Get Bitcoin metrics and data
        bitcoin_metrics = current_app.bitcoin_analytics.get_real_time_metrics()
        recent_bitcoin = current_app.bitcoin_streamer.get_recent_data(20)
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        
        # Get trading analysis
        trading_analysis = current_app.trading_analyzer.get_current_analysis()
        
        # Get system health
        trading_health = current_app.trading_analyzer.get_system_status()
        
        return jsonify({
            'bitcoin': {
                'metrics': bitcoin_metrics,
                'recent_data': [data.to_dict() for data in recent_bitcoin],
                'streaming': bitcoin_stats['is_running'],
                'stats': bitcoin_stats
            },
            'trading': trading_analysis,
            'integrated_status': {
                'total_data_points': bitcoin_stats['total_data_points'],
                'analysis_ready': len(current_app.trading_analyzer.price_history) >= 30,
                'last_update': datetime.now().isoformat(),
                'system_healthy': bitcoin_stats['is_running'] and len(current_app.trading_analyzer.price_history) > 0,
                'persistence_enabled': True
            }
        })
        
    except Exception as e:
        logger.error(f"[API] Erro ao obter dados do dashboard: {e}")
        return jsonify({
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
                'persistence_enabled': True
            },
            'error': str(e)
        }), 500
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
    Provides a high-level status overview of the entire integrated system.
    """
    try:
        # Get Bitcoin streaming stats
        bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
        
        # Get trading analyzer health
        trading_health = current_app.trading_analyzer.get_system_status()
        
        # Get latest price from recent data
        recent_bitcoin = current_app.bitcoin_streamer.get_recent_data(1)
        last_price = recent_bitcoin[0].price if recent_bitcoin else 0
        
        return jsonify({
            'bitcoin_streaming': bitcoin_stats['is_running'],
            'bitcoin_data_points': bitcoin_stats['total_data_points'],
            'bitcoin_last_price': last_price,
            'trading_data_points': trading_health['data_points'],
            'trading_active_signals': trading_health['active_signals'],
            'trading_analysis_count': trading_health['total_analysis'],
            'system_status': 'running' if bitcoin_stats['is_running'] else 'stopped',
            'fetch_interval_minutes': bitcoin_stats['fetch_interval_minutes'],
            'last_update': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"[API] Erro ao obter status integrado: {e}")
        return jsonify({
            'bitcoin_streaming': False,
            'bitcoin_data_points': 0,
            'bitcoin_last_price': 0,
            'trading_data_points': 0,
            'trading_active_signals': 0,
            'trading_analysis_count': 0,
            'system_status': 'error',
            'fetch_interval_minutes': 5,
            'last_update': datetime.now().isoformat(),
            'error': str(e)
        }), 500

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
        trading_analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        
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
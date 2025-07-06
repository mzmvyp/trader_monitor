# your_project/routes/main_routes.py

from flask import Blueprint, render_template, jsonify
from datetime import datetime

# Create a Blueprint for main routes
main_bp = Blueprint('main_routes', __name__)

@main_bp.route('/')
def dashboard():
    """
    Renders the main integrated dashboard HTML page.
    This is the entry point for the web interface.
    """
    return render_template('integrated_dashboard.html')

@main_bp.route('/bitcoin')
def bitcoin_dashboard():
    """
    Renders the Bitcoin-specific dashboard HTML page.
    """
    return render_template('bitcoin_dashboard.html')
        
@main_bp.route('/trading')
def trading_dashboard():
    """
    Renders the trading-specific dashboard HTML page.
    """
    return render_template('trading_dashboard.html')

@main_bp.route('/api/integrated/status')
def get_integrated_status():
    """
    Provides a high-level status overview of the entire integrated system.
    This endpoint is designed to quickly check the health and operational state
    of both the Bitcoin streaming and trading analysis components.
    
    It requires access to the streamer and analyzer instances, which will be
    passed to the blueprint or accessed via a global app context in the main app.
    For now, it's a placeholder.
    """
    # In a real application, you would access the streamer and analyzer instances
    # from the current_app context or by passing them during blueprint registration.
    # For demonstration, we'll return dummy data or expect these to be
    # available via the main app instance.
    
    # Placeholder for actual logic:
    # bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
    # trading_health = current_app.trading_analyzer.get_system_health()
    
    # For now, return a basic placeholder. The actual controller will populate this.
    return jsonify({
        'bitcoin_streaming': False,
        'bitcoin_data_points': 0,
        'bitcoin_last_price': 0,
        'trading_data_points': 0,
        'trading_active_signals': 0,
        'trading_analysis_count': 0,
        'system_status': 'initializing',
        'fetch_interval_minutes': 5,
        'last_update': datetime.now().isoformat()
    })

@main_bp.route('/api/integrated/dashboard-data')
def get_dashboard_data():
    """
    Provides a comprehensive set of data for the integrated dashboard.
    This endpoint aggregates metrics from Bitcoin streaming, trading analysis,
    and system status into a single response to minimize API calls from the frontend.
    
    It requires access to the streamer, processor, and analyzer instances, which will be
    passed to the blueprint or accessed via a global app context in the main app.
    For now, it's a placeholder.
    """
    # Placeholder for actual logic:
    # try:
    #     bitcoin_metrics = current_app.bitcoin_analytics.get_real_time_metrics()
    #     recent_bitcoin = current_app.bitcoin_streamer.get_recent_data(20)
    #     bitcoin_stats = current_app.bitcoin_streamer.get_stream_statistics()
    #     trading_analysis = current_app.trading_analyzer.get_current_analysis()
        
    #     return jsonify({
    #         'bitcoin': {
    #             'metrics': bitcoin_metrics,
    #             'recent_data': [data.to_dict() for data in recent_bitcoin],
    #             'streaming': bitcoin_stats['is_running'],
    #             'stats': bitcoin_stats
    #         },
    #         'trading': trading_analysis,
    #         'integrated_status': {
    #             'total_data_points': bitcoin_stats['total_data_points'],
    #             'analysis_ready': len(current_app.trading_analyzer.price_history) >= 30,
    #             'last_update': datetime.now().isoformat(),
    #             'system_healthy': bitcoin_stats['is_running'] and len(current_app.trading_analyzer.price_history) > 0,
    #             'persistence_enabled': True
    #         }
    #     })
        
    # except Exception as e:
    #     current_app.logger.error(f"Erro ao obter dados do dashboard: {e}")
    #     return jsonify({
    #         'error': 'Erro interno do servidor',
    #         'message': str(e)
    #     }), 500
    
    # For now, return a basic placeholder. The actual controller will populate this.
    return jsonify({
        'bitcoin': {
            'metrics': {},
            'recent_data': [],
            'streaming': False,
            'stats': {}
        },
        'trading': {
            'current_price': 0,
            'indicators': {},
            'active_signals': 0,
            'recent_signals': [],
            'pattern_stats': [],
            'system_info': {}
        },
        'integrated_status': {
            'total_data_points': 0,
            'analysis_ready': False,
            'last_update': datetime.now().isoformat(),
            'system_healthy': False,
            'persistence_enabled': True
        }
    })


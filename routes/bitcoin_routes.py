# your_project/routes/bitcoin_routes.py

from flask import Blueprint, jsonify, request, current_app, render_template
from utils.logging_config import logger

# Create a Blueprint for Bitcoin-related routes
bitcoin_bp = Blueprint('bitcoin_routes', __name__, url_prefix='/bitcoin')

@bitcoin_bp.route('/')
def bitcoin_dashboard():
    """
    Renders the Bitcoin dashboard page.
    """
    return render_template('bitcoin_dashboard.html')

@bitcoin_bp.route('/api/start-stream', methods=['POST'])
def start_bitcoin_stream():
    """
    API endpoint to start the Bitcoin data streaming process.
    """
    try:
        current_app.bitcoin_streamer.start_streaming()
        logger.info("[OK] Bitcoin streaming iniciado via API.")
        return jsonify({'status': 'started', 'message': 'Bitcoin streaming iniciado (5 min intervals)'})
    except Exception as e:
        logger.error(f"Erro ao iniciar streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bitcoin_bp.route('/api/stop-stream', methods=['POST'])
def stop_bitcoin_stream():
    """
    API endpoint to stop the Bitcoin data streaming process.
    """
    try:
        current_app.bitcoin_streamer.stop_streaming()
        logger.info("[STOP] Bitcoin streaming parado via API.")
        return jsonify({'status': 'stopped', 'message': 'Bitcoin streaming parado'})
    except Exception as e:
        logger.error(f"Erro ao parar streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bitcoin_bp.route('/api/stream-status')
def get_bitcoin_status():
    """
    API endpoint to get the current status and statistics of the Bitcoin streamer.
    """
    try:
        stats = current_app.bitcoin_streamer.get_stream_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Erro ao obter status: {e}")
        return jsonify({'error': str(e)}), 500

@bitcoin_bp.route('/api/metrics')
def get_bitcoin_metrics():
    """
    API endpoint to get real-time Bitcoin analytics metrics.
    """
    try:
        time_window_minutes = request.args.get('time_window_minutes', 30, type=int)
        metrics = current_app.bitcoin_analytics.get_real_time_metrics(time_window_minutes)
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Erro ao obter métricas: {e}")
        return jsonify({'error': str(e)}), 500

@bitcoin_bp.route('/api/recent-data')
def get_bitcoin_recent_data():
    """
    API endpoint to get a list of recent Bitcoin data points.
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 1000)  # Cap the limit
        
        recent_data = current_app.bitcoin_streamer.get_recent_data(limit)
        return jsonify([data.to_dict() for data in recent_data])
    except Exception as e:
        logger.error(f"Erro ao obter dados recentes: {e}")
        return jsonify({'error': str(e)}), 500

# Global API routes (without /bitcoin prefix)
@bitcoin_bp.route('/api/bitcoin/start-stream', methods=['POST'])
def start_bitcoin_stream_global():
    """Global API endpoint for starting Bitcoin stream"""
    return start_bitcoin_stream()

@bitcoin_bp.route('/api/bitcoin/stop-stream', methods=['POST'])
def stop_bitcoin_stream_global():
    """Global API endpoint for stopping Bitcoin stream"""
    return stop_bitcoin_stream()

@bitcoin_bp.route('/api/bitcoin/status')
def get_bitcoin_status_global():
    """Global API endpoint for Bitcoin status"""
    return get_bitcoin_status()

@bitcoin_bp.route('/api/bitcoin/metrics')
def get_bitcoin_metrics_global():
    """Global API endpoint for Bitcoin metrics"""
    return get_bitcoin_metrics()

@bitcoin_bp.route('/api/bitcoin/recent-data')
def get_bitcoin_recent_data_global():
    """Global API endpoint for recent Bitcoin data"""
    return get_bitcoin_recent_data()
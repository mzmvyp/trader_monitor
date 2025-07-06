# your_project/routes/bitcoin_routes.py

from flask import Blueprint, jsonify, request, current_app
from utils.logging_config import logger

# Create a Blueprint for Bitcoin-related routes
bitcoin_bp = Blueprint('bitcoin_routes', __name__)

@bitcoin_bp.route('/api/bitcoin/start-stream', methods=['POST'])
def start_bitcoin_stream():
    """
    API endpoint to start the Bitcoin data streaming process.
    """
    try:
        # Access the BitcoinDataStreamer instance from the Flask app context
        current_app.bitcoin_streamer.start_streaming()
        logger.info("[OK] Bitcoin streaming iniciado via API.")
        return jsonify({'status': 'started', 'message': 'Bitcoin streaming iniciado (5 min intervals)'})
    except Exception as e:
        logger.error(f"Erro ao iniciar streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bitcoin_bp.route('/api/bitcoin/stop-stream', methods=['POST'])
def stop_bitcoin_stream():
    """
    API endpoint to stop the Bitcoin data streaming process.
    """
    try:
        # Access the BitcoinDataStreamer instance from the Flask app context
        current_app.bitcoin_streamer.stop_streaming()
        logger.info("[STOP] Bitcoin streaming parado via API.")
        return jsonify({'status': 'stopped', 'message': 'Bitcoin streaming parado'})
    except Exception as e:
        logger.error(f"Erro ao parar streaming: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bitcoin_bp.route('/api/bitcoin/status')
def get_bitcoin_status():
    """
    API endpoint to get the current status and statistics of the Bitcoin streamer.
    """
    # Access the BitcoinDataStreamer instance from the Flask app context
    stats = current_app.bitcoin_streamer.get_stream_statistics()
    return jsonify(stats)

@bitcoin_bp.route('/api/bitcoin/metrics')
def get_bitcoin_metrics():
    """
    API endpoint to get real-time Bitcoin analytics metrics.
    """
    # Access the BitcoinAnalyticsEngine instance from the Flask app context
    metrics = current_app.bitcoin_analytics.get_real_time_metrics()
    return jsonify(metrics)

@bitcoin_bp.route('/api/bitcoin/recent-data')
def get_bitcoin_recent_data():
    """
    API endpoint to get a list of recent Bitcoin data points.
    Accepts an optional 'limit' query parameter to control the number of records.
    """
    limit = request.args.get('limit', 50, type=int)
    limit = min(limit, 1000) # Cap the limit to prevent excessively large responses
    
    # Access the BitcoinDataStreamer instance from the Flask app context
    recent_data = current_app.bitcoin_streamer.get_recent_data(limit)
    
    # Convert BitcoinData objects to dictionaries for JSON serialization
    return jsonify([data.to_dict() for data in recent_data])


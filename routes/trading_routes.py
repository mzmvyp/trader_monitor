# your_project/routes/trading_routes.py

import sqlite3
from flask import Blueprint, jsonify, request, current_app
from utils.logging_config import logger

# Create a Blueprint for Trading-related routes
trading_bp = Blueprint('trading_routes', __name__)

@trading_bp.route('/api/trading/analysis')
def get_trading_analysis():
    """
    API endpoint to get the current comprehensive trading analysis.
    This includes indicators, active signals, recent signals, and pattern statistics.
    """
    # Access the SimpleTradingAnalyzer instance from the Flask app context
    analysis = current_app.trading_analyzer.get_current_analysis()
    return jsonify(analysis)

@trading_bp.route('/api/trading/signals')
def get_trading_signals():
    """
    API endpoint to get a list of recent trading signals.
    Accepts an optional 'limit' query parameter.
    """
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100) # Cap the limit
    
    # Access the SimpleTradingAnalyzer instance and get recent signals
    analysis = current_app.trading_analyzer.get_current_analysis()
    signals = analysis.get('recent_signals', [])
    
    # Return the most recent signals up to the specified limit
    return jsonify(signals[-limit:] if signals else [])

@trading_bp.route('/api/trading/active-signals')
def get_active_signals():
    """
    API endpoint to get a list of currently active trading signals.
    Includes the current Bitcoin price for context if available.
    """
    analysis = current_app.trading_analyzer.get_current_analysis()
    signals = analysis.get('recent_signals', []) # Assuming recent_signals includes all signals
    active = [s for s in signals if s.get('status') == 'ACTIVE']
    
    current_price = 0
    # Attempt to get the very latest price from the Bitcoin streamer's data queue
    if current_app.bitcoin_streamer.data_queue:
        current_price = current_app.bitcoin_streamer.data_queue[-1].price
    
    # Add current price to each active signal for frontend display
    for signal in active:
        signal['current_price'] = current_price
            
    return jsonify(active)

@trading_bp.route('/api/trading/pattern-stats')
def get_pattern_statistics():
    """
    API endpoint to get performance statistics for different trading patterns.
    """
    analysis = current_app.trading_analyzer.get_current_analysis()
    return jsonify(analysis.get('pattern_stats', []))

@trading_bp.route('/api/trading/indicators')
def get_current_indicators():
    """
    API endpoint to get the latest calculated technical indicators.
    """
    analysis = current_app.trading_analyzer.get_current_analysis()
    return jsonify(analysis.get('indicators', {}))

@trading_bp.route('/api/control/cleanup', methods=['POST'])
def cleanup_data():
    """
    API endpoint to clean up old data from both Bitcoin stream and trading analyzer databases.
    Deletes records older than a specified number of days (default: 7 days).
    """
    try:
        # Get days_to_keep from request JSON, default to Config setting
        days_to_keep = request.json.get('days_to_keep', current_app.config.DEFAULT_DAYS_TO_KEEP_DATA) if request.json else current_app.config.DEFAULT_DAYS_TO_KEEP_DATA
        
        # Connect to Bitcoin Stream DB
        conn_bitcoin = sqlite3.connect(current_app.config.BITCOIN_STREAM_DB)
        cursor_bitcoin = conn_bitcoin.cursor()
        
        cutoff_date = (current_app.datetime.now() - current_app.timedelta(days=days_to_keep)).isoformat()
        
        # Delete old Bitcoin stream data
        cursor_bitcoin.execute('DELETE FROM bitcoin_stream WHERE timestamp < ?', (cutoff_date,))
        deleted_bitcoin = cursor_bitcoin.rowcount
        
        # Delete old Bitcoin analytics data
        cursor_bitcoin.execute('DELETE FROM bitcoin_analytics WHERE created_at < ?', (cutoff_date,))
        deleted_analytics = cursor_bitcoin.rowcount
        conn_bitcoin.commit()
        conn_bitcoin.close()
        
        # Connect to Trading Analyzer DB
        conn_trading = sqlite3.connect(current_app.config.TRADING_ANALYZER_DB)
        cursor_trading = conn_trading.cursor()
        
        # Delete old price history
        cursor_trading.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date,))
        deleted_price_history = cursor_trading.rowcount
        
        # Delete old non-active trading signals
        cursor_trading.execute('DELETE FROM trading_signals WHERE created_at < ? AND status != "ACTIVE"', (cutoff_date,))
        deleted_signals = cursor_trading.rowcount
        conn_trading.commit()
        conn_trading.close()
        
        logger.info(f"[CLEAN] Limpeza concluída: {deleted_bitcoin} bitcoin, {deleted_analytics} analytics, {deleted_price_history} preços, {deleted_signals} sinais.")
        
        return jsonify({
            'status': 'success',
            'deleted_bitcoin_records': deleted_bitcoin,
            'deleted_analytics_records': deleted_analytics,
            'deleted_price_history': deleted_price_history,
            'deleted_signals': deleted_signals,
            'message': f'Dados anteriores a {days_to_keep} dias removidos.'
        })
        
    except Exception as e:
        logger.error(f"Erro na limpeza de dados: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@trading_bp.route('/api/control/reset-signals', methods=['POST'])
def reset_signals():
    """
    API endpoint to reset all trading signals and the analyzer's state.
    This clears both in-memory and persisted signals/state.
    """
    try:
        # Access the SimpleTradingAnalyzer instance from the Flask app context
        current_app.trading_analyzer.reset_signals_and_state()
        logger.info("[FIX] Sistema de sinais resetado completamente via API.")
        return jsonify({'status': 'success', 'message': 'Sistema resetado (incluindo persistência)'})
        
    except Exception as e:
        logger.error(f"Erro ao resetar sinais: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@trading_bp.route('/api/control/force-save', methods=['POST'])
def force_save():
    """
    API endpoint to force a save of the trading analyzer's state and
    any pending Bitcoin stream data in the processor's buffer.
    """
    try:
        # Access instances from the Flask app context
        current_app.trading_analyzer.save_analyzer_state()
        current_app.bitcoin_processor.force_process_batch()
        
        logger.info("[FIX] Estado salvo manualmente via API.")
        return jsonify({'status': 'success', 'message': 'Estado atual salvo.'})
        
    except Exception as e:
        logger.error(f"Erro ao salvar estado: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


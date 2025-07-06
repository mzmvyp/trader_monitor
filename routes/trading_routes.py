# your_project/routes/trading_routes.py

import sqlite3
from flask import Blueprint, jsonify, request, current_app, render_template
from utils.logging_config import logger

# Create a Blueprint for Trading-related routes
trading_bp = Blueprint('trading_routes', __name__, url_prefix='/trading')

@trading_bp.route('/')
def trading_dashboard():
    """
    Renders the Trading dashboard page.
    """
    return render_template('trading_dashboard.html')

@trading_bp.route('/api/analysis')
def get_trading_analysis():
    """
    API endpoint to get the current comprehensive trading analysis.
    """
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Erro ao obter análise de trading: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/signals')
def get_trading_signals():
    """
    API endpoint to get a list of recent trading signals.
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # Cap the limit
        
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        signals = analysis.get('recent_signals', [])
        
        return jsonify(signals[-limit:] if signals else [])
    except Exception as e:
        logger.error(f"Erro ao obter sinais de trading: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/active-signals')
def get_active_signals():
    """
    API endpoint to get a list of currently active trading signals.
    """
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        signals = analysis.get('recent_signals', [])
        active = [s for s in signals if s.get('status') == 'ACTIVE']
        
        current_price = 0
        if current_app.bitcoin_streamer.data_queue:
            current_price = current_app.bitcoin_streamer.data_queue[-1].price
        
        for signal in active:
            signal['current_price'] = current_price
                
        return jsonify(active)
    except Exception as e:
        logger.error(f"Erro ao obter sinais ativos: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/pattern-stats')
def get_pattern_statistics():
    """
    API endpoint to get performance statistics for different trading patterns.
    """
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        return jsonify(analysis.get('pattern_stats', []))
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de padrões: {e}")
        return jsonify({'error': str(e)}), 500

@trading_bp.route('/api/indicators')
def get_current_indicators():
    """
    API endpoint to get the latest calculated technical indicators.
    """
    try:
        analysis = current_app.trading_analyzer.get_comprehensive_analysis()
        return jsonify(analysis.get('indicators', {}))
    except Exception as e:
        logger.error(f"Erro ao obter indicadores: {e}")
        return jsonify({'error': str(e)}), 500

# Global API routes (without /trading prefix)
@trading_bp.route('/api/trading/analysis')
def get_trading_analysis_global():
    """Global API endpoint for trading analysis"""
    return get_trading_analysis()

@trading_bp.route('/api/trading/signals')
def get_trading_signals_global():
    """Global API endpoint for trading signals"""
    return get_trading_signals()

@trading_bp.route('/api/trading/active-signals')
def get_active_signals_global():
    """Global API endpoint for active signals"""
    return get_active_signals()

@trading_bp.route('/api/trading/pattern-stats')
def get_pattern_statistics_global():
    """Global API endpoint for pattern statistics"""
    return get_pattern_statistics()

@trading_bp.route('/api/trading/indicators')
def get_current_indicators_global():
    """Global API endpoint for indicators"""
    return get_current_indicators()

@trading_bp.route('/api/control/cleanup', methods=['POST'])
def cleanup_data():
    """
    API endpoint to clean up old data from both Bitcoin stream and trading analyzer databases.
    """
    try:
        from config import app_config
        
        days_to_keep = request.json.get('days_to_keep', app_config.DEFAULT_DAYS_TO_KEEP_DATA) if request.json else app_config.DEFAULT_DAYS_TO_KEEP_DATA
        
        conn_bitcoin = sqlite3.connect(app_config.BITCOIN_STREAM_DB)
        cursor_bitcoin = conn_bitcoin.cursor()
        
        cutoff_date = (current_app.datetime.now() - current_app.timedelta(days=days_to_keep)).isoformat()
        
        cursor_bitcoin.execute('DELETE FROM bitcoin_stream WHERE timestamp < ?', (cutoff_date,))
        deleted_bitcoin = cursor_bitcoin.rowcount
        
        cursor_bitcoin.execute('DELETE FROM bitcoin_analytics WHERE created_at < ?', (cutoff_date,))
        deleted_analytics = cursor_bitcoin.rowcount
        conn_bitcoin.commit()
        conn_bitcoin.close()
        
        conn_trading = sqlite3.connect(app_config.TRADING_ANALYZER_DB)
        cursor_trading = conn_trading.cursor()
        
        cursor_trading.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff_date,))
        deleted_price_history = cursor_trading.rowcount
        
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
    """
    try:
        current_app.trading_analyzer.reset_signals_and_state()
        logger.info("[FIX] Sistema de sinais resetado completamente via API.")
        return jsonify({'status': 'success', 'message': 'Sistema resetado (incluindo persistência)'})
        
    except Exception as e:
        logger.error(f"Erro ao resetar sinais: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@trading_bp.route('/api/control/force-save', methods=['POST'])
def force_save():
    """
    API endpoint to force a save of the trading analyzer's state.
    """
    try:
        current_app.trading_analyzer.save_analyzer_state()
        current_app.bitcoin_processor.force_process_batch()
        
        logger.info("[FIX] Estado salvo manualmente via API.")
        return jsonify({'status': 'success', 'message': 'Estado atual salvo.'})
        
    except Exception as e:
        logger.error(f"Erro ao salvar estado: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
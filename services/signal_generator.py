# services/signal_generator.py

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import threading
import time
from dataclasses import asdict

from models.trading_signal import (
    TradingSignal, SignalType, SignalStatus, SignalSource, SignalManager
)
from config import app_config

logger = logging.getLogger(__name__)

class SignalGenerator:
    """
    Gerador de sinais de trading que evita duplicação e gerencia lifecycle
    """
    
    def __init__(self, signal_manager: SignalManager):
        self.signal_manager = signal_manager
        self.config = app_config
        self.last_signal_time = {}  # Por asset
        self.generation_lock = threading.Lock()
        self.is_running = False
        self.price_monitor_thread = None
        
        # Cache de preços para evitar requests desnecessários
        self.current_prices = {}
        self.last_price_update = {}
        
    def start_monitoring(self):
        """Inicia monitoramento contínuo de preços para atualizar sinais"""
        if self.is_running:
            return
            
        self.is_running = True
        self.price_monitor_thread = threading.Thread(target=self._price_monitoring_loop, daemon=True)
        self.price_monitor_thread.start()
        logger.info("Signal price monitoring started")
    
    def stop_monitoring(self):
        """Para monitoramento de preços"""
        self.is_running = False
        if self.price_monitor_thread:
            self.price_monitor_thread.join(timeout=5)
        logger.info("Signal price monitoring stopped")
    
    def _price_monitoring_loop(self):
        """Loop principal de monitoramento de preços"""
        while self.is_running:
            try:
                # Atualizar preços de todos os assets com sinais ativos
                active_assets = set()
                for asset in self.signal_manager.active_signals.keys():
                    if self.signal_manager.get_active_signals(asset):
                        active_assets.add(asset)
                
                for asset in active_assets:
                    self._update_asset_price(asset)
                
                time.sleep(10)  # Atualizar a cada 10 segundos
                
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {e}")
                time.sleep(30)
    
    def _update_asset_price(self, asset_symbol: str):
        """Atualiza preço de um asset e seus sinais ativos"""
        try:
            # Aqui você integraria com sua fonte de dados de preços
            # Por exemplo, via API da Binance ou seu sistema existente
            current_price = self._fetch_current_price(asset_symbol)
            
            if current_price:
                self.current_prices[asset_symbol] = current_price
                self.last_price_update[asset_symbol] = datetime.now()
                
                # Atualizar sinais ativos
                self.signal_manager.update_signals_with_price(asset_symbol, current_price)
                
        except Exception as e:
            logger.error(f"Error updating price for {asset_symbol}: {e}")
    
    def _fetch_current_price(self, asset_symbol: str) -> Optional[float]:
        """
        Busca preço atual do asset - integrar com seu sistema existente
        """
        # IMPLEMENTAR: Integração com sua fonte de preços
        # Por exemplo:
        # - API da Binance
        # - Seu sistema de streaming existente
        # - Banco de dados local
        
        # Placeholder - substituir pela implementação real
        try:
            import requests
            symbol_map = {
                'BTC': 'BTCUSDT',
                'ETH': 'ETHUSDT', 
                'SOL': 'SOLUSDT'
            }
            
            symbol = symbol_map.get(asset_symbol, f"{asset_symbol}USDT")
            response = requests.get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                timeout=5
            )
            
            if response.status_code == 200:
                return float(response.json()['price'])
                
        except Exception as e:
            logger.error(f"Error fetching price for {asset_symbol}: {e}")
        
        return None
    
    def generate_signal_from_analysis(self, 
                                    asset_symbol: str,
                                    technical_analysis: Dict,
                                    current_price: float,
                                    pattern_type: Optional[str] = None) -> Optional[TradingSignal]:
        """
        Gera sinal baseado em análise técnica com verificação de duplicação
        """
        with self.generation_lock:
            # Verificar cooldown
            if not self._check_cooldown(asset_symbol):
                logger.debug(f"Signal generation for {asset_symbol} still in cooldown")
                return None
            
            # Verificar se há sinais ativos demais
            active_count = len(self.signal_manager.get_active_signals(asset_symbol))
            max_active = getattr(self.config, 'MAX_ACTIVE_SIGNALS', 5)
            
            if active_count >= max_active:
                logger.debug(f"Maximum active signals reached for {asset_symbol}: {active_count}")
                return None
            
            # Analisar sinais dos indicadores
            signal_analysis = self._analyze_indicators(technical_analysis)
            
            if not signal_analysis:
                return None
            
            signal_type, confidence, reasons = signal_analysis
            
            # Verificar confiança mínima
            min_confidence = getattr(self.config, 'MIN_SIGNAL_CONFIDENCE', 60)
            if confidence < min_confidence:
                logger.debug(f"Signal confidence {confidence}% below minimum {min_confidence}%")
                return None
            
            # Calcular targets e stop loss
            targets, stop_loss = self._calculate_targets_and_stop(current_price, signal_type)
            
            # Verificar risk/reward
            risk_reward = self._calculate_risk_reward(current_price, targets[0], stop_loss)
            min_rr = getattr(self.config, 'MIN_RISK_REWARD', 1.5)
            
            if risk_reward < min_rr:
                logger.debug(f"Risk/reward {risk_reward:.2f} below minimum {min_rr}")
                return None
            
            # Criar sinal
            signal = TradingSignal(
                asset_symbol=asset_symbol,
                signal_type=signal_type,
                source=SignalSource.COMBINED if pattern_type else SignalSource.INDICATORS,
                pattern_type=pattern_type,
                entry_price=current_price,
                current_price=current_price,
                target_1=targets[0],
                target_2=targets[1],
                target_3=targets[2],
                stop_loss=stop_loss,
                confidence=confidence,
                reasons=reasons,
                technical_indicators=technical_analysis,
                volume_confirmation=self._check_volume_confirmation(technical_analysis),
                risk_reward_ratio=risk_reward
            )
            
            # Tentar criar sinal (com verificação de duplicação interna)
            created_signal = self.signal_manager.create_signal(signal)
            
            if created_signal:
                self.last_signal_time[asset_symbol] = datetime.now()
                logger.info(f"Generated {signal_type.value} signal for {asset_symbol} at {current_price} (confidence: {confidence}%)")
                
                return created_signal
            
            return None
    
    def _check_cooldown(self, asset_symbol: str) -> bool:
        """Verifica se passou o tempo de cooldown desde o último sinal"""
        if asset_symbol not in self.last_signal_time:
            return True
        
        cooldown_minutes = getattr(self.config, 'SIGNAL_COOLDOWN_MINUTES', 60)
        cooldown_delta = timedelta(minutes=cooldown_minutes)
        
        return datetime.now() - self.last_signal_time[asset_symbol] >= cooldown_delta
    
    def _analyze_indicators(self, technical_analysis: Dict) -> Optional[Tuple[SignalType, float, List[str]]]:
        """
        Analisa indicadores técnicos e retorna tipo de sinal, confiança e razões
        """
        if not technical_analysis:
            return None
        
        # Extrair indicadores
        rsi = technical_analysis.get('RSI', 50)
        macd = technical_analysis.get('MACD', 0)
        macd_signal = technical_analysis.get('MACD_Signal', 0)
        macd_histogram = technical_analysis.get('MACD_Histogram', 0)
        bb_position = technical_analysis.get('BB_Position', 0.5)
        stoch_k = technical_analysis.get('Stoch_K', 50)
        stoch_d = technical_analysis.get('Stoch_D', 50)
        sma_short = technical_analysis.get('SMA_9', 0)
        sma_long = technical_analysis.get('SMA_21', 0)
        volume_ratio = technical_analysis.get('Volume_Ratio', 1.0)
        
        # Pesos dos indicadores (configuráveis)
        weights = getattr(self.config, 'INDICATOR_WEIGHTS', {
            'rsi': 0.20,
            'macd': 0.25,
            'bb': 0.15,
            'stoch': 0.15,
            'sma_cross': 0.15,
            'volume': 0.10
        })
        
        buy_score = 0
        sell_score = 0
        reasons = []
        
        # RSI Analysis
        if rsi < 30:
            buy_score += weights['rsi']
            reasons.append("RSI oversold")
        elif rsi > 70:
            sell_score += weights['rsi']
            reasons.append("RSI overbought")
        
        # MACD Analysis
        if macd > macd_signal and macd_histogram > 0:
            buy_score += weights['macd']
            reasons.append("MACD bullish")
        elif macd < macd_signal and macd_histogram < 0:
            sell_score += weights['macd']
            reasons.append("MACD bearish")
        
        # Bollinger Bands
        if bb_position < 0.2:
            buy_score += weights['bb']
            reasons.append("Price near lower Bollinger Band")
        elif bb_position > 0.8:
            sell_score += weights['bb']
            reasons.append("Price near upper Bollinger Band")
        
        # Stochastic
        if stoch_k < 20 and stoch_d < 20:
            buy_score += weights['stoch']
            reasons.append("Stochastic oversold")
        elif stoch_k > 80 and stoch_d > 80:
            sell_score += weights['stoch']
            reasons.append("Stochastic overbought")
        
        # SMA Cross
        if sma_short > sma_long:
            buy_score += weights['sma_cross']
            reasons.append("Short SMA above long SMA")
        elif sma_short < sma_long:
            sell_score += weights['sma_cross']
            reasons.append("Short SMA below long SMA")
        
        # Volume confirmation
        if volume_ratio > 1.5:
            if buy_score > sell_score:
                buy_score += weights['volume']
                reasons.append("High volume confirms bullish sentiment")
            else:
                sell_score += weights['volume']
                reasons.append("High volume confirms bearish sentiment")
        
        # Determinar sinal
        total_score = buy_score + sell_score
        if total_score < 0.4:  # Sinal muito fraco
            return None
        
        if buy_score > sell_score:
            confidence = min(95, buy_score * 100)
            return SignalType.BUY, confidence, reasons
        else:
            confidence = min(95, sell_score * 100)
            return SignalType.SELL, confidence, reasons
    
    def _calculate_targets_and_stop(self, entry_price: float, signal_type: SignalType) -> Tuple[List[float], float]:
        """Calcula targets e stop loss baseado no tipo de sinal"""
        
        # Multipliers configuráveis
        target_multipliers = getattr(self.config, 'TARGET_MULTIPLIERS', [2.0, 3.5, 5.0])
        stop_multiplier = getattr(self.config, 'STOP_LOSS_ATR_MULTIPLIER', 2.0)
        
        # ATR aproximado baseado na volatilidade típica (simplificado)
        atr_estimate = entry_price * 0.02  # 2% do preço como ATR estimado
        
        if signal_type == SignalType.BUY:
            targets = [
                entry_price + (atr_estimate * mult) for mult in target_multipliers
            ]
            stop_loss = entry_price - (atr_estimate * stop_multiplier)
        else:
            targets = [
                entry_price - (atr_estimate * mult) for mult in target_multipliers
            ]
            stop_loss = entry_price + (atr_estimate * stop_multiplier)
        
        return targets, stop_loss
    
    def _calculate_risk_reward(self, entry_price: float, target_price: float, stop_loss: float) -> float:
        """Calcula relação risk/reward"""
        if stop_loss == 0:
            return 0
        
        risk = abs(entry_price - stop_loss)
        reward = abs(target_price - entry_price)
        
        return reward / risk if risk > 0 else 0
    
    def _check_volume_confirmation(self, technical_analysis: Dict) -> bool:
        """Verifica se há confirmação de volume"""
        volume_ratio = technical_analysis.get('Volume_Ratio', 1.0)
        min_volume_ratio = getattr(self.config, 'MIN_VOLUME_RATIO', 1.1)
        
        return volume_ratio >= min_volume_ratio
    
    def force_generate_test_signal(self, asset_symbol: str, signal_type: str = "BUY") -> Optional[TradingSignal]:
        """
        Gera sinal de teste para debugging (bypassa algumas verificações)
        """
        try:
            current_price = self.current_prices.get(asset_symbol)
            if not current_price:
                current_price = self._fetch_current_price(asset_symbol)
            
            if not current_price:
                logger.error(f"Could not fetch current price for {asset_symbol}")
                return None
            
            signal_type_enum = SignalType.BUY if signal_type.upper() == "BUY" else SignalType.SELL
            
            # Targets e stop simplificados
            if signal_type_enum == SignalType.BUY:
                targets = [
                    current_price * 1.02,  # 2%
                    current_price * 1.035, # 3.5%
                    current_price * 1.05   # 5%
                ]
                stop_loss = current_price * 0.98  # -2%
            else:
                targets = [
                    current_price * 0.98,  # -2%
                    current_price * 0.965, # -3.5%
                    current_price * 0.95   # -5%
                ]
                stop_loss = current_price * 1.02  # +2%
            
            signal = TradingSignal(
                asset_symbol=asset_symbol,
                signal_type=signal_type_enum,
                source=SignalSource.MANUAL,
                pattern_type="TEST_SIGNAL",
                entry_price=current_price,
                current_price=current_price,
                target_1=targets[0],
                target_2=targets[1],
                target_3=targets[2],
                stop_loss=stop_loss,
                confidence=75.0,
                reasons=["Test signal generated manually"],
                technical_indicators={"test": True},
                volume_confirmation=True,
                risk_reward_ratio=2.0
            )
            
            created_signal = self.signal_manager.create_signal(signal)
            
            if created_signal:
                logger.info(f"Generated test {signal_type} signal for {asset_symbol}")
                return created_signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating test signal: {e}")
            return None
    
    def get_signal_statistics(self, asset_symbol: str = None) -> Dict:
        """Retorna estatísticas dos sinais"""
        return self.signal_manager.get_performance_stats(asset_symbol)
    
    def get_active_signals_summary(self) -> Dict:
        """Retorna resumo dos sinais ativos"""
        summary = {}
        
        for asset_symbol in ['BTC', 'ETH', 'SOL']:
            active_signals = self.signal_manager.get_active_signals(asset_symbol)
            
            summary[asset_symbol] = {
                'count': len(active_signals),
                'buy_signals': len([s for s in active_signals if s.signal_type == SignalType.BUY]),
                'sell_signals': len([s for s in active_signals if s.signal_type == SignalType.SELL]),
                'avg_confidence': sum(s.confidence for s in active_signals) / len(active_signals) if active_signals else 0,
                'avg_pnl': sum(s.current_pnl_pct for s in active_signals) / len(active_signals) if active_signals else 0
            }
        
        return summary


# =====================================================
# API Routes para integração com o frontend
# =====================================================

from flask import Blueprint, jsonify, request
from datetime import datetime

signals_bp = Blueprint('signals_api', __name__, url_prefix='/api/signals')

# Instancia global (seria melhor usar dependency injection)
signal_manager = None
signal_generator = None

def init_signal_system(db_path: str):
    """Inicializa sistema de sinais"""
    global signal_manager, signal_generator
    
    signal_manager = SignalManager(db_path)
    signal_generator = SignalGenerator(signal_manager)
    signal_generator.start_monitoring()
    
    logger.info("Signal system initialized")

@signals_bp.route('/active', methods=['GET'])
def get_active_signals():
    """Retorna sinais ativos"""
    try:
        asset = request.args.get('asset')
        signals = signal_manager.get_active_signals(asset)
        
        return jsonify({
            'success': True,
            'data': [signal.to_dict() for signal in signals],
            'count': len(signals)
        })
    
    except Exception as e:
        logger.error(f"Error getting active signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/recent', methods=['GET'])
def get_recent_signals():
    """Retorna sinais recentes"""
    try:
        asset = request.args.get('asset')
        limit = int(request.args.get('limit', 50))
        
        signals = signal_manager.get_recent_signals(asset, limit)
        
        return jsonify({
            'success': True,
            'data': [signal.to_dict() for signal in signals],
            'count': len(signals)
        })
    
    except Exception as e:
        logger.error(f"Error getting recent signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/stats', methods=['GET'])
def get_signal_statistics():
    """Retorna estatísticas de performance"""
    try:
        asset = request.args.get('asset')
        days = int(request.args.get('days', 30))
        
        stats = signal_manager.get_performance_stats(asset, days)
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting signal statistics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/summary', methods=['GET'])
def get_signals_summary():
    """Retorna resumo de sinais ativos"""
    try:
        summary = signal_generator.get_active_signals_summary()
        
        return jsonify({
            'success': True,
            'data': summary
        })
    
    except Exception as e:
        logger.error(f"Error getting signals summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/generate-test', methods=['POST'])
def generate_test_signal():
    """Gera sinal de teste"""
    try:
        data = request.get_json() or {}
        asset = data.get('asset', 'BTC')
        signal_type = data.get('type', 'BUY')
        
        signal = signal_generator.force_generate_test_signal(asset, signal_type)
        
        if signal:
            return jsonify({
                'success': True,
                'message': f'Test {signal_type} signal generated for {asset}',
                'data': signal.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to generate test signal'
            }), 400
    
    except Exception as e:
        logger.error(f"Error generating test signal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/update-price', methods=['POST'])
def update_signal_prices():
    """Força atualização de preços para sinais ativos"""
    try:
        data = request.get_json() or {}
        asset = data.get('asset')
        
        if asset:
            signal_generator._update_asset_price(asset)
            message = f'Prices updated for {asset}'
        else:
            # Atualizar todos os assets
            for asset_symbol in ['BTC', 'ETH', 'SOL']:
                signal_generator._update_asset_price(asset_symbol)
            message = 'Prices updated for all assets'
        
        return jsonify({
            'success': True,
            'message': message
        })
    
    except Exception as e:
        logger.error(f"Error updating signal prices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@signals_bp.route('/cleanup', methods=['POST'])
def cleanup_old_signals():
    """Remove sinais antigos"""
    try:
        data = request.get_json() or {}
        days = data.get('days', 30)
        
        deleted_count = signal_manager.cleanup_old_signals(days)
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up {deleted_count} old signals',
            'deleted_count': deleted_count
        })
    
    except Exception as e:
        logger.error(f"Error cleaning up signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
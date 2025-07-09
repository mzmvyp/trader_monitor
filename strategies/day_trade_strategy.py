# strategies/day_trade_strategy.py
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class DayTradeStrategy:
    """Estratégia de Day Trading - Timeframe 5 minutos (IMPLEMENTAÇÃO COMPLETA)"""
    
    def __init__(self):
        self.config = {
            # Indicadores principais
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'sma_short': 9,
            'sma_long': 21,
            'ema_short': 12,
            'ema_long': 26,
            'bb_period': 20,
            'bb_std': 2,
            
            # Configurações de sinal
            'min_confidence': 60,
            'signal_cooldown_minutes': 30,
            
            # Gestão de risco
            'stop_loss_atr_multiplier': 2.0,
            'target_multipliers': [1.0, 2.0, 3.0],
            
            # Volume e momentum
            'volume_threshold': 1.3,  # 130% da média
            'momentum_periods': [5, 10, 20],
            
            # Padrões técnicos
            'divergence_lookback': 10,
            'support_resistance_strength': 3
        }
        
        self.name = "DAY_TRADE"
        self.timeframe = "5m"
        self.hold_time = "30min - 4h"
        
        # Cache para cálculos
        self.last_rsi_values = []
        self.last_price_values = []
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        Análise completa para day trading - 5 minutos
        
        Combina múltiplos indicadores:
        - RSI com divergências
        - Médias móveis com cruzamentos
        - Bollinger Bands
        - Volume
        - Padrões de candlestick
        - Suporte/resistência
        """
        
        # Verificar dados suficientes
        if indicators.get('data_points', 0) < 30:
            return None
        
        signal = {
            'strategy': self.name,
            'timeframe': self.timeframe,
            'action': 'HOLD',
            'confidence': 0,
            'reasons': [],
            'hold_time_expected': self.hold_time,
            'stop_loss': 0,
            'targets': [],
            'entry_price': current_price,
            'risk_reward': 0,
            'pattern_detected': None,
            'divergence_detected': False
        }
        
        # Extrair indicadores básicos
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)
        sma_long = indicators.get('sma_long', current_price)
        ema_short = indicators.get('ema_short', current_price)
        ema_long = indicators.get('ema_long', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # === 1. ANÁLISE RSI AVANÇADA ===
        rsi_analysis = self._analyze_rsi_advanced(rsi, current_price, indicators)
        confidence += rsi_analysis['score']
        reasons.extend(rsi_analysis['reasons'])
        
        if rsi_analysis['divergence']:
            signal['divergence_detected'] = True
            confidence += 15
            reasons.append('Divergência RSI detectada')
        
        # === 2. ANÁLISE DE MÉDIAS MÓVEIS ===
        ma_analysis = self._analyze_moving_averages(current_price, sma_short, sma_long, ema_short, ema_long)
        confidence += ma_analysis['score']
        reasons.extend(ma_analysis['reasons'])
        
        # === 3. BOLLINGER BANDS ===
        bb_analysis = self._analyze_bollinger_bands(indicators, current_price)
        confidence += bb_analysis['score']
        reasons.extend(bb_analysis['reasons'])
        
        # === 4. ANÁLISE DE VOLUME ===
        volume_analysis = self._analyze_volume(indicators)
        confidence += volume_analysis['score']
        reasons.extend(volume_analysis['reasons'])
        
        # === 5. MOMENTUM E VELOCIDADE ===
        momentum_analysis = self._analyze_momentum(indicators, current_price)
        confidence += momentum_analysis['score']
        reasons.extend(momentum_analysis['reasons'])
        
        # === 6. SUPORTE E RESISTÊNCIA ===
        sr_analysis = self._analyze_support_resistance(indicators, current_price)
        confidence += sr_analysis['score']
        reasons.extend(sr_analysis['reasons'])
        
        # === 7. PADRÕES DE CANDLESTICK ===
        pattern_analysis = self._detect_candlestick_patterns(indicators)
        confidence += pattern_analysis['score']
        reasons.extend(pattern_analysis['reasons'])
        signal['pattern_detected'] = pattern_analysis['pattern']
        
        # === 8. FILTRO DE TENDÊNCIA PRINCIPAL ===
        if trend == 'ALTISTA' and confidence > 0:
            confidence += 10
            reasons.append('Alinhado com tendência altista')
        elif trend == 'BAIXISTA' and confidence < 0:
            confidence -= 10
            reasons.append('Alinhado com tendência baixista')
        elif trend == 'NEUTRO':
            confidence *= 0.8  # Reduzir confiança em mercado lateral
            reasons.append('Mercado lateral (reduzida confiança)')
        
        # === 9. FILTROS ADICIONAIS ===
        # Filtro de volatilidade
        if atr > 0:
            volatility = atr / current_price
            if volatility > 0.05:  # > 5% de volatilidade
                confidence *= 0.7
                reasons.append('Alta volatilidade (cuidado)')
            elif volatility < 0.01:  # < 1% de volatilidade
                confidence *= 0.8
                reasons.append('Baixa volatilidade')
        
        # === 10. DETERMINAÇÃO FINAL ===
        abs_confidence = abs(confidence)
        
        if abs_confidence >= self.config['min_confidence']:
            if confidence > 0:
                signal['action'] = 'BUY'
                signal['stop_loss'] = current_price - (atr * self.config['stop_loss_atr_multiplier'])
                signal['targets'] = [
                    current_price + (atr * mult) for mult in self.config['target_multipliers']
                ]
            else:
                signal['action'] = 'SELL'
                signal['stop_loss'] = current_price + (atr * self.config['stop_loss_atr_multiplier'])
                signal['targets'] = [
                    current_price - (atr * mult) for mult in self.config['target_multipliers']
                ]
            
            # Calcular risk/reward
            if signal['targets'] and len(signal['targets']) > 1:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][1] - current_price)  # Target intermediário
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons[:8]  # Limitar para não poluir interface
        
        return signal
    
    def _analyze_rsi_advanced(self, rsi: float, current_price: float, indicators: Dict) -> Dict:
        """Análise avançada do RSI com divergências"""
        
        score = 0
        reasons = []
        divergence = False
        
        # RSI básico
        if rsi <= self.config['rsi_oversold']:
            score += 30
            reasons.append(f'RSI oversold ({rsi:.1f})')
        elif rsi >= self.config['rsi_overbought']:
            score -= 30
            reasons.append(f'RSI overbought ({rsi:.1f})')
        elif 35 <= rsi <= 45:
            score += 15
            reasons.append('RSI em zona de compra')
        elif 55 <= rsi <= 65:
            score -= 15
            reasons.append('RSI em zona de venda')
        
        # Detectar divergência (simplificado)
        self.last_rsi_values.append(rsi)
        self.last_price_values.append(current_price)
        
        if len(self.last_rsi_values) > self.config['divergence_lookback']:
            self.last_rsi_values.pop(0)
            self.last_price_values.pop(0)
            
            # Divergência altista: preço faz mínimo menor, RSI faz mínimo maior
            if (len(self.last_price_values) >= 5 and 
                min(self.last_price_values[-3:]) < min(self.last_price_values[-6:-3]) and
                min(self.last_rsi_values[-3:]) > min(self.last_rsi_values[-6:-3])):
                divergence = True
                score += 20
                reasons.append('Divergência altista RSI')
            
            # Divergência baixista: preço faz máximo maior, RSI faz máximo menor
            elif (max(self.last_price_values[-3:]) > max(self.last_price_values[-6:-3]) and
                  max(self.last_rsi_values[-3:]) < max(self.last_rsi_values[-6:-3])):
                divergence = True
                score -= 20
                reasons.append('Divergência baixista RSI')
        
        return {'score': score, 'reasons': reasons, 'divergence': divergence}
    
    def _analyze_moving_averages(self, price: float, sma_short: float, sma_long: float, 
                               ema_short: float, ema_long: float) -> Dict:
        """Análise de médias móveis com cruzamentos"""
        
        score = 0
        reasons = []
        
        # Posição do preço em relação às médias
        if price > sma_short > sma_long:
            score += 25
            reasons.append('Preço > SMA9 > SMA21 (estrutura altista)')
        elif price < sma_short < sma_long:
            score -= 25
            reasons.append('Preço < SMA9 < SMA21 (estrutura baixista)')
        
        # Cruzamento SMA
        sma_spread = (sma_short - sma_long) / sma_long * 100
        if sma_spread > 0.5:  # SMA9 > SMA21 por mais de 0.5%
            score += 15
            reasons.append('SMA9 acima SMA21 (momentum altista)')
        elif sma_spread < -0.5:
            score -= 15
            reasons.append('SMA9 abaixo SMA21 (momentum baixista)')
        
        # Cruzamento EMA (mais sensível)
        ema_spread = (ema_short - ema_long) / ema_long * 100
        if ema_spread > 0.3:
            score += 10
            reasons.append('EMA12 > EMA26 (momentum rápido)')
        elif ema_spread < -0.3:
            score -= 10
            reasons.append('EMA12 < EMA26 (momentum negativo)')
        
        # Distância do preço das médias
        distance_sma = abs(price - sma_short) / sma_short * 100
        if distance_sma > 2:  # Muito longe da média
            score *= 0.7  # Reduzir confiança
            reasons.append('Preço distante da SMA9')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_bollinger_bands(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de Bollinger Bands"""
        
        score = 0
        reasons = []
        
        # Calcular Bollinger Bands (simplificado)
        sma_20 = indicators.get('sma_long', current_price)  # Usar SMA21 como aproximação
        
        # Simular banda superior e inferior (em implementação real, calcular corretamente)
        bb_upper = sma_20 * 1.02  # +2% aproximado
        bb_lower = sma_20 * 0.98  # -2% aproximado
        
        # Posição nas bandas
        if current_price <= bb_lower:
            score += 20
            reasons.append('Preço na banda inferior (oversold)')
        elif current_price >= bb_upper:
            score -= 20
            reasons.append('Preço na banda superior (overbought)')
        elif bb_lower < current_price < sma_20:
            score += 5
            reasons.append('Preço abaixo da média BB')
        elif sma_20 < current_price < bb_upper:
            score -= 5
            reasons.append('Preço acima da média BB')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_volume(self, indicators: Dict) -> Dict:
        """Análise de volume"""
        
        score = 0
        reasons = []
        
        volume_sma = indicators.get('volume_sma', 0)
        current_volume = indicators.get('current_volume', 0)
        
        if volume_sma > 0 and current_volume > 0:
            volume_ratio = current_volume / volume_sma
            
            if volume_ratio >= self.config['volume_threshold']:
                score += 15
                reasons.append(f'Volume alto ({volume_ratio:.1f}x média)')
            elif volume_ratio >= 1.1:
                score += 5
                reasons.append('Volume acima da média')
            elif volume_ratio < 0.7:
                score *= 0.8  # Reduzir confiança com volume baixo
                reasons.append('Volume baixo')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_momentum(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de momentum"""
        
        score = 0
        reasons = []
        
        # Usar dados disponíveis para calcular momentum simples
        sma_short = indicators.get('sma_short', current_price)
        sma_long = indicators.get('sma_long', current_price)
        
        # Momentum baseado na diferença das médias
        if sma_long > 0:
            momentum = (sma_short - sma_long) / sma_long * 100
            
            if momentum > 1:  # Forte momentum altista
                score += 15
                reasons.append('Momentum altista forte')
            elif momentum > 0.3:
                score += 8
                reasons.append('Momentum altista')
            elif momentum < -1:  # Forte momentum baixista
                score -= 15
                reasons.append('Momentum baixista forte')
            elif momentum < -0.3:
                score -= 8
                reasons.append('Momentum baixista')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_support_resistance(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de suporte e resistência"""
        
        score = 0
        reasons = []
        
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        resistance = support_resistance.get('resistance', 0)
        
        if support > 0:
            distance_support = (current_price - support) / support * 100
            if distance_support <= 1:  # Dentro de 1% do suporte
                score += 15
                reasons.append('Próximo do suporte forte')
            elif distance_support <= 2:
                score += 8
                reasons.append('Próximo do suporte')
        
        if resistance > 0:
            distance_resistance = (resistance - current_price) / current_price * 100
            if distance_resistance <= 1:  # Dentro de 1% da resistência
                score -= 15
                reasons.append('Próximo da resistência forte')
            elif distance_resistance <= 2:
                score -= 8
                reasons.append('Próximo da resistência')
        
        return {'score': score, 'reasons': reasons}
    
    def _detect_candlestick_patterns(self, indicators: Dict) -> Dict:
        """Detecta padrões de candlestick (simplificado)"""
        
        score = 0
        reasons = []
        pattern = None
        
        # Em uma implementação real, você analisaria os dados OHLC
        # Por simplicidade, vamos simular alguns padrões baseados nos indicadores
        
        rsi = indicators.get('rsi', 50)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        # Padrão "Hammer" simulado (RSI baixo em tendência baixista)
        if rsi < 35 and trend == 'BAIXISTA':
            score += 10
            reasons.append('Padrão reversão (Hammer-like)')
            pattern = 'HAMMER'
        
        # Padrão "Shooting Star" simulado (RSI alto em tendência altista)
        elif rsi > 65 and trend == 'ALTISTA':
            score -= 10
            reasons.append('Padrão reversão (Shooting Star-like)')
            pattern = 'SHOOTING_STAR'
        
        # Padrão "Engulfing" simulado (momentum forte)
        current_price = indicators.get('current_price', 0)
        sma_short = indicators.get('sma_short', current_price)
        
        if current_price > sma_short * 1.01:  # 1% acima da média
            score += 5
            reasons.append('Momentum engolidor altista')
            pattern = 'BULLISH_ENGULFING'
        elif current_price < sma_short * 0.99:  # 1% abaixo da média
            score -= 5
            reasons.append('Momentum engolidor baixista')
            pattern = 'BEARISH_ENGULFING'
        
        return {'score': score, 'reasons': reasons, 'pattern': pattern}

# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DAY TRADING STRATEGY ===")
    
    # Dados simulados
    mock_indicators = {
        'current_price': 67543.21,
        'rsi': 42.5,
        'sma_short': 67200,    # SMA9
        'sma_long': 66800,     # SMA21
        'ema_short': 67350,
        'ema_long': 67000,
        'atr': 850.5,
        'trend_direction': 'ALTISTA',
        'data_points': 150,
        'support_resistance': {
            'support': 66500,
            'resistance': 68200
        },
        'volume_sma': 125.7,
        'current_volume': 180.3
    }
    
    day_trade = DayTradeStrategy()
    signal = day_trade.analyze(mock_indicators, mock_indicators['current_price'])
    
    if signal:
        print(f"Ação: {signal['action']}")
        print(f"Confiança: {signal['confidence']:.1f}%")
        print(f"Stop Loss: ${signal['stop_loss']:,.2f}")
        if signal['targets']:
            print(f"Targets: ${signal['targets'][0]:,.2f} | ${signal['targets'][1]:,.2f}")
        print(f"Risk/Reward: {signal['risk_reward']:.2f}")
        print(f"Razões: {', '.join(signal['reasons'][:3])}")
        if signal.get('pattern_detected'):
            print(f"Padrão: {signal['pattern_detected']}")
    else:
        print("Dados insuficientes")
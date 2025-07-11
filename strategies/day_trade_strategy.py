# strategies/day_trade_strategy.py - ADAPTADO PARA SUAS CONFIGURAÇÕES ATUAIS
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class DayTradeStrategy:
    """Estratégia Day Trading - ADAPTADA para suas configurações atuais"""
    
    def __init__(self):
        # === SUAS CONFIGURAÇÕES ATUAIS (do paste.txt) ===
        self.config = {
            'rsi_period': 14,           # ✅ Suas configs atuais
            'rsi_overbought': 70,       # ✅ Suas configs atuais  
            'rsi_oversold': 30,         # ✅ Suas configs atuais
            'sma_short': 9,             # ✅ Suas configs atuais
            'sma_long': 21,             # ✅ Suas configs atuais
            'ema_short': 12,            # Manter padrão
            'ema_long': 26,             # Manter padrão
            'min_confidence': 60,       # ✅ Suas configs atuais
            'signal_cooldown_minutes': 30,  # Melhorar dos 60min atuais
            'stop_loss_atr_multiplier': 2.0,
            'target_multipliers': [1.0, 2.0, 3.0],
            
            # Adicionar melhorias baseadas na sua análise
            'volume_threshold': 1.3,
            'divergence_lookback': 10,
            'elliott_wave_enabled': True,    # ✅ Você já tem isso
            'double_bottom_enabled': True    # ✅ Você já tem isso
        }
        
        self.name = "DAY_TRADE"
        self.timeframe = "5m"
        self.hold_time = "30min - 4h"
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        Análise Day Trading - INTEGRADA com sua lógica atual
        
        Mantém compatibilidade total com seu sistema atual
        + adiciona análises multi-timeframe
        """
        
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
            'elliott_pattern': None,
            'double_bottom_detected': False
        }
        
        # Extrair indicadores (compatível com seu sistema)
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)  # SMA9
        sma_long = indicators.get('sma_long', current_price)    # SMA21
        ema_short = indicators.get('ema_short', current_price)
        ema_long = indicators.get('ema_long', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # === 1. SUA LÓGICA RSI ATUAL (RSI 70/30) ===
        if rsi <= self.config['rsi_oversold']:
            confidence += 30
            reasons.append(f'RSI oversold ({rsi:.1f})')
        elif rsi >= self.config['rsi_overbought']:
            confidence -= 30
            reasons.append(f'RSI overbought ({rsi:.1f})')
        elif 35 <= rsi <= 45:
            confidence += 15
            reasons.append('RSI zona de compra')
        elif 55 <= rsi <= 65:
            confidence -= 15
            reasons.append('RSI zona de venda')
        
        # === 2. SUA LÓGICA SMA ATUAL (SMA9/21) ===
        if current_price > sma_short > sma_long:
            confidence += 25
            reasons.append('Preço > SMA9 > SMA21 (estrutura altista)')
        elif current_price < sma_short < sma_long:
            confidence -= 25
            reasons.append('Preço < SMA9 < SMA21 (estrutura baixista)')
        
        # Cruzamento SMA9/21 (sua configuração)
        sma_spread = (sma_short - sma_long) / sma_long * 100 if sma_long > 0 else 0
        if sma_spread > 0.5:
            confidence += 15
            reasons.append('SMA9 > SMA21 (momentum altista)')
        elif sma_spread < -0.5:
            confidence -= 15
            reasons.append('SMA9 < SMA21 (momentum baixista)')
        
        # === 3. INTEGRAR SEUS PADRÕES ATUAIS ===
        # Elliott Waves (você já tem isso implementado)
        elliott_analysis = self._check_elliott_waves(indicators)
        if elliott_analysis['detected']:
            confidence += elliott_analysis['score']
            reasons.append(f"Elliott Wave: {elliott_analysis['pattern']}")
            signal['elliott_pattern'] = elliott_analysis['pattern']
        
        # Double Bottom (você já tem isso implementado)
        double_bottom_analysis = self._check_double_bottom(indicators)
        if double_bottom_analysis['detected']:
            confidence += double_bottom_analysis['score']
            reasons.append('Double Bottom detectado')
            signal['double_bottom_detected'] = True
        
        # === 4. MELHORIAS ADICIONAIS ===
        # Volume (se disponível no seu sistema)
        volume_analysis = self._analyze_volume(indicators)
        confidence += volume_analysis['score']
        reasons.extend(volume_analysis['reasons'])
        
        # Suporte/Resistência
        sr_analysis = self._analyze_support_resistance(indicators, current_price)
        confidence += sr_analysis['score']
        reasons.extend(sr_analysis['reasons'])
        
        # === 5. SEU FILTRO DE TENDÊNCIA ===
        if trend == 'ALTISTA' and confidence > 0:
            confidence += 10
            reasons.append('Alinhado com tendência altista')
        elif trend == 'BAIXISTA' and confidence < 0:
            confidence -= 10
            reasons.append('Alinhado com tendência baixista')
        
        # === 6. APLICAR SUA CONFIANÇA MÍNIMA (60%) ===
        abs_confidence = abs(confidence)
        
        if abs_confidence >= self.config['min_confidence']:  # 60%
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
            
            # Risk/reward
            if signal['targets'] and len(signal['targets']) > 1:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][1] - current_price)
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons[:8]
        
        return signal
    
    def _check_elliott_waves(self, indicators: Dict) -> Dict:
        """
        Placeholder para sua lógica Elliott Waves atual
        SUBSTITUA por sua implementação real
        """
        # AQUI: Cole sua lógica atual de Elliott Waves
        
        # Exemplo básico (substituir pela sua lógica)
        rsi = indicators.get('rsi', 50)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        # Simular detecção Elliott Wave
        if trend == 'ALTISTA' and 30 <= rsi <= 50:
            return {
                'detected': True,
                'pattern': 'Wave 3 (impulse)',
                'score': 15
            }
        elif trend == 'BAIXISTA' and 50 <= rsi <= 70:
            return {
                'detected': True, 
                'pattern': 'Wave A (correction)',
                'score': -15
            }
        
        return {'detected': False, 'pattern': None, 'score': 0}
    
    def _check_double_bottom(self, indicators: Dict) -> Dict:
        """
        Placeholder para sua lógica Double Bottom atual
        SUBSTITUA por sua implementação real
        """
        # AQUI: Cole sua lógica atual de Double Bottom
        
        # Exemplo básico (substituir pela sua lógica)
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        current_price = indicators.get('current_price', 0)
        
        # Simular Double Bottom
        if support > 0 and current_price <= support * 1.02:  # 2% do suporte
            return {
                'detected': True,
                'score': 20
            }
        
        return {'detected': False, 'score': 0}
    
    def _analyze_volume(self, indicators: Dict) -> Dict:
        """Análise de volume"""
        score = 0
        reasons = []
        
        volume_sma = indicators.get('volume_sma', 0)
        current_volume = indicators.get('current_volume', 0)
        
        if volume_sma > 0 and current_volume > 0:
            volume_ratio = current_volume / volume_sma
            
            if volume_ratio >= self.config['volume_threshold']:
                score += 10
                reasons.append(f'Volume alto ({volume_ratio:.1f}x)')
            elif volume_ratio < 0.7:
                score *= 0.9
                reasons.append('Volume baixo')
        
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
            if distance_support <= 1:
                score += 10
                reasons.append('Próximo do suporte')
        
        if resistance > 0:
            distance_resistance = (resistance - current_price) / current_price * 100
            if distance_resistance <= 1:
                score -= 10
                reasons.append('Próximo da resistência')
        
        return {'score': score, 'reasons': reasons}

# MÉTODO PARA INTEGRAR COM SEU SISTEMA ATUAL
def integrate_with_existing_day_trading(existing_signal_method):
    """
    Wrapper para integrar com seu método atual de day trading
    
    Use assim no seu código:
    
    # Seu método atual
    def calculate_day_trading_signal(self, data):
        # Sua lógica atual...
        return signal
    
    # Integração
    integrated_method = integrate_with_existing_day_trading(calculate_day_trading_signal)
    """
    
    def enhanced_method(self, data):
        # Executar seu método atual
        original_signal = existing_signal_method(self, data)
        
        # Executar nova estratégia multi-timeframe
        day_strategy = DayTradeStrategy()
        
        # Converter seus dados para formato dos indicadores
        indicators = {
            'current_price': data.get('price', 0),
            'rsi': data.get('rsi', 50),
            'sma_short': data.get('sma_9', 0),
            'sma_long': data.get('sma_21', 0),
            'data_points': len(data.get('price_history', []))
        }
        
        multi_signal = day_strategy.analyze(indicators, data.get('price', 0))
        
        # Combinar sinais (priorizar seu sinal atual)
        if original_signal and multi_signal:
            # Se ambos concordam, aumentar confiança
            if original_signal.get('action') == multi_signal.get('action'):
                original_signal['confidence'] = min(95, original_signal.get('confidence', 0) + 10)
                original_signal['multi_timeframe_confirmed'] = True
            
        return original_signal or multi_signal
    
    return enhanced_method
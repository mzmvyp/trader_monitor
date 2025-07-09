# strategies/scalp_strategy.py
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class ScalpStrategy:
    """Estratégia de Scalping - Timeframe 1 minuto"""
    
    def __init__(self):
        self.config = {
            # Indicadores mais sensíveis
            'rsi_period': 7,
            'rsi_overbought': 75,
            'rsi_oversold': 25,
            'sma_short': 3,
            'sma_long': 8,
            'ema_period': 5,
            
            # Configurações de sinal
            'min_confidence': 75,
            'signal_cooldown_minutes': 5,
            
            # Gestão de risco
            'stop_loss_atr_multiplier': 1.0,
            'target_multipliers': [0.5, 1.0, 1.5],  # Alvos pequenos e rápidos
            
            # Volume
            'volume_threshold': 1.2,  # 120% da média
            
            # Momentum
            'momentum_periods': [3, 5]
        }
        
        self.name = "SCALP"
        self.timeframe = "1m"
        self.hold_time = "1-5 minutos"
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        Análise específica para scalping
        
        Args:
            indicators: Indicadores calculados pelo MultiTimeframeManager
            current_price: Preço atual
            
        Returns:
            Sinal de scalping ou None
        """
        
        # Verificar se temos dados suficientes
        if indicators.get('data_points', 0) < 10:
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
            'risk_reward': 0
        }
        
        # Extrair indicadores
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)
        sma_long = indicators.get('sma_long', current_price)
        ema_short = indicators.get('ema_short', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # === ANÁLISE RSI SCALPING ===
        if rsi <= self.config['rsi_oversold']:
            confidence += 35
            reasons.append(f'RSI extremamente oversold ({rsi:.1f})')
        elif rsi >= self.config['rsi_overbought']:
            confidence -= 35
            reasons.append(f'RSI extremamente overbought ({rsi:.1f})')
        elif 30 < rsi < 40:
            confidence += 15
            reasons.append('RSI em zona de compra')
        elif 60 < rsi < 70:
            confidence -= 15
            reasons.append('RSI em zona de venda')
        
        # === ANÁLISE DE MOMENTUM RÁPIDO ===
        price_vs_sma3 = (current_price - sma_short) / sma_short * 100
        sma_momentum = (sma_short - sma_long) / sma_long * 100
        
        if price_vs_sma3 > 0.1 and sma_momentum > 0.05:  # Acima das médias
            confidence += 20
            reasons.append('Momentum altista confirmado')
        elif price_vs_sma3 < -0.1 and sma_momentum < -0.05:  # Abaixo das médias
            confidence -= 20
            reasons.append('Momentum baixista confirmado')
        
        # === ANÁLISE EMA RÁPIDA ===
        if current_price > ema_short * 1.001:  # 0.1% acima
            confidence += 10
            reasons.append('Preço acima EMA5')
        elif current_price < ema_short * 0.999:  # 0.1% abaixo
            confidence -= 10
            reasons.append('Preço abaixo EMA5')
        
        # === ANÁLISE DE VOLUME (se disponível) ===
        volume_sma = indicators.get('volume_sma', 0)
        current_volume = indicators.get('current_volume', 0)
        
        if volume_sma > 0 and current_volume > volume_sma * self.config['volume_threshold']:
            confidence += 15
            reasons.append('Volume acima da média (confirmação)')
        
        # === FILTRO DE TREND GERAL ===
        if trend == 'ALTISTA' and confidence > 0:
            confidence += 10
            reasons.append('Alinhado com trend altista')
        elif trend == 'BAIXISTA' and confidence < 0:
            confidence -= 10
            reasons.append('Alinhado com trend baixista')
        
        # === ANÁLISE DE SUPORTE/RESISTÊNCIA ===
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        resistance = support_resistance.get('resistance', 0)
        
        if support > 0 and current_price <= support * 1.005:  # 0.5% do suporte
            confidence += 15
            reasons.append('Próximo do suporte')
        elif resistance > 0 and current_price >= resistance * 0.995:  # 0.5% da resistência
            confidence -= 15
            reasons.append('Próximo da resistência')
        
        # === DETERMINAÇÃO FINAL ===
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
            if signal['targets']:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][0] - current_price)
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons
        
        return signal

# strategies/swing_strategy.py
class SwingStrategy:
    """Estratégia de Swing Trading - Timeframe 1 hora"""
    
    def __init__(self):
        self.config = {
            # Indicadores para swing
            'rsi_period': 14,
            'rsi_overbought': 65,
            'rsi_oversold': 35,
            'sma_short': 20,
            'sma_long': 50,
            'sma_trend': 200,  # Para tendência de longo prazo
            'ema_short': 12,
            'ema_long': 26,
            
            # Configurações de sinal
            'min_confidence': 50,
            'signal_cooldown_minutes': 240,  # 4 horas
            
            # Gestão de risco
            'stop_loss_atr_multiplier': 3.5,
            'target_multipliers': [1.5, 2.5, 4.0],  # Alvos maiores
            
            # Tendência
            'trend_strength_threshold': 0.3,
            
            # Consolidação
            'consolidation_threshold': 0.02  # 2%
        }
        
        self.name = "SWING"
        self.timeframe = "1h"
        self.hold_time = "3-7 dias"
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        Análise específica para swing trading
        
        Args:
            indicators: Indicadores calculados pelo MultiTimeframeManager
            current_price: Preço atual
            
        Returns:
            Sinal de swing trading ou None
        """
        
        # Verificar se temos dados suficientes para swing
        if indicators.get('data_points', 0) < 50:
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
            'trend_analysis': {},
            'risk_reward': 0
        }
        
        # Extrair indicadores
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)
        sma_long = indicators.get('sma_long', current_price)
        ema_short = indicators.get('ema_short', current_price)
        ema_long = indicators.get('ema_long', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # === ANÁLISE DE TENDÊNCIA PRINCIPAL ===
        trend_strength = self._calculate_trend_strength(indicators)
        signal['trend_analysis'] = trend_strength
        
        if trend_strength['direction'] == 'ALTISTA' and trend_strength['strength'] > self.config['trend_strength_threshold']:
            confidence += 30
            reasons.append(f"Tendência altista forte ({trend_strength['strength']:.2f})")
        elif trend_strength['direction'] == 'BAIXISTA' and trend_strength['strength'] > self.config['trend_strength_threshold']:
            confidence -= 30
            reasons.append(f"Tendência baixista forte ({trend_strength['strength']:.2f})")
        
        # === ANÁLISE RSI PARA SWING ===
        if rsi <= self.config['rsi_oversold'] and trend != 'BAIXISTA':
            confidence += 25
            reasons.append(f'RSI oversold em contexto favorável ({rsi:.1f})')
        elif rsi >= self.config['rsi_overbought'] and trend != 'ALTISTA':
            confidence -= 25
            reasons.append(f'RSI overbought em contexto favorável ({rsi:.1f})')
        
        # === ANÁLISE DE MÉDIAS MÓVEIS ===
        sma_alignment = self._analyze_sma_alignment(current_price, sma_short, sma_long)
        
        if sma_alignment['bullish']:
            confidence += 20
            reasons.append('Médias alinhadas altista (20>50)')
        elif sma_alignment['bearish']:
            confidence -= 20
            reasons.append('Médias alinhadas baixista (20<50)')
        
        # === ANÁLISE EMA PARA MOMENTUM ===
        ema_cross = self._analyze_ema_cross(ema_short, ema_long, indicators)
        
        if ema_cross['golden_cross']:
            confidence += 15
            reasons.append('Golden cross EMA (12>26)')
        elif ema_cross['death_cross']:
            confidence -= 15
            reasons.append('Death cross EMA (12<26)')
        
        # === ANÁLISE DE SUPORTE/RESISTÊNCIA CHAVE ===
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        resistance = support_resistance.get('resistance', 0)
        
        if support > 0 and current_price <= support * 1.02:  # 2% do suporte
            confidence += 20
            reasons.append('Próximo de suporte chave')
        elif resistance > 0 and current_price >= resistance * 0.98:  # 2% da resistência
            confidence -= 20
            reasons.append('Próximo de resistência chave')
        
        # === ANÁLISE DE CONSOLIDAÇÃO/BREAKOUT ===
        consolidation = self._detect_consolidation(indicators)
        
        if consolidation['is_consolidating']:
            # Reduzir confiança durante consolidação
            confidence *= 0.7
            reasons.append('Mercado em consolidação')
        elif consolidation['potential_breakout']:
            confidence += 10
            reasons.append('Potencial breakout de consolidação')
        
        # === DETERMINAÇÃO FINAL ===
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
            
            # Calcular risk/reward para swing
            if signal['targets']:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][1] - current_price) if len(signal['targets']) > 1 else abs(signal['targets'][0] - current_price)
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons
        
        return signal
    
    def _calculate_trend_strength(self, indicators: Dict) -> Dict:
        """Calcula força da tendência"""
        sma_short = indicators.get('sma_short', 0)
        sma_long = indicators.get('sma_long', 0)
        current_price = indicators.get('current_price', 0)
        
        if sma_long == 0:
            return {'direction': 'NEUTRO', 'strength': 0}
        
        # Distância percentual entre médias
        sma_distance = abs(sma_short - sma_long) / sma_long
        
        # Posição do preço em relação às médias
        price_position = (current_price - sma_long) / sma_long
        
        direction = 'ALTISTA' if sma_short > sma_long else 'BAIXISTA'
        strength = min(sma_distance * 10, 1.0)  # Normalizar para 0-1
        
        return {
            'direction': direction,
            'strength': strength,
            'sma_distance': sma_distance,
            'price_position': price_position
        }
    
    def _analyze_sma_alignment(self, price: float, sma_short: float, sma_long: float) -> Dict:
        """Analisa alinhamento das médias"""
        return {
            'bullish': price > sma_short > sma_long,
            'bearish': price < sma_short < sma_long,
            'neutral': not (price > sma_short > sma_long or price < sma_short < sma_long)
        }
    
    def _analyze_ema_cross(self, ema_short: float, ema_long: float, indicators: Dict) -> Dict:
        """Analisa cruzamentos EMA"""
        # Simplificado - em implementação real, verificar cruzamento histórico
        return {
            'golden_cross': ema_short > ema_long * 1.005,  # 0.5% acima
            'death_cross': ema_short < ema_long * 0.995,   # 0.5% abaixo
            'ema_spread': abs(ema_short - ema_long) / ema_long if ema_long > 0 else 0
        }
    
    def _detect_consolidation(self, indicators: Dict) -> Dict:
        """Detecta períodos de consolidação"""
        # Simplificado - usar ATR para detectar baixa volatilidade
        atr = indicators.get('atr', 0)
        current_price = indicators.get('current_price', 0)
        
        if current_price == 0:
            return {'is_consolidating': False, 'potential_breakout': False}
        
        atr_percentage = atr / current_price
        
        return {
            'is_consolidating': atr_percentage < self.config['consolidation_threshold'],
            'potential_breakout': False,  # Implementar lógica mais complexa
            'volatility': atr_percentage
        }

# strategies/day_trade_strategy.py  
class DayTradeStrategy:
    """Estratégia de Day Trading - Timeframe 5 minutos (ADAPTAR SUA LÓGICA ATUAL)"""
    
    def __init__(self):
        # USAR SUAS CONFIGURAÇÕES ATUAIS - APENAS EXEMPLO
        self.config = {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'sma_short': 9,
            'sma_long': 21,
            'ema_short': 12,
            'ema_long': 26,
            'min_confidence': 60,
            'signal_cooldown_minutes': 30,
            'stop_loss_atr_multiplier': 2.0,
            'target_multipliers': [1.0, 2.0, 3.0]
        }
        
        self.name = "DAY_TRADE"
        self.timeframe = "5m"
        self.hold_time = "30min - 4h"
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        ADAPTAR: Cole aqui sua lógica atual de day trading
        
        Apenas mude o formato de retorno para seguir o padrão:
        """
        
        # Verificar dados suficientes
        if indicators.get('data_points', 0) < 20:
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
            'risk_reward': 0
        }
        
        # === AQUI: COLE SUA LÓGICA ATUAL ===
        # Exemplo básico (substituir pela sua)
        
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)
        sma_long = indicators.get('sma_long', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # SUA LÓGICA DE RSI
        if rsi < self.config['rsi_oversold']:
            confidence += 30
            reasons.append(f'RSI oversold ({rsi:.1f})')
        elif rsi > self.config['rsi_overbought']:
            confidence -= 30
            reasons.append(f'RSI overbought ({rsi:.1f})')
        
        # SUA LÓGICA DE MÉDIAS
        if sma_short > sma_long * 1.002:
            confidence += 20
            reasons.append('SMA9 > SMA21')
        elif sma_short < sma_long * 0.998:
            confidence -= 20
            reasons.append('SMA9 < SMA21')
        
        # SUA LÓGICA DE TENDÊNCIA
        if trend == 'ALTISTA':
            confidence += 15
            reasons.append('Tendência altista')
        elif trend == 'BAIXISTA':
            confidence -= 15
            reasons.append('Tendência baixista')
        
        # === APLICAR SEUS FILTROS ELLIOTT WAVES, DOUBLE BOTTOM, etc. ===
        # ... sua lógica específica ...
        
        # Determinar ação final
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
            
            # Risk/reward
            if signal['targets']:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][1] - current_price) if len(signal['targets']) > 1 else abs(signal['targets'][0] - current_price)
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons
        
        return signal

# Exemplo de uso das estratégias
if __name__ == "__main__":
    # Teste básico das estratégias
    
    # Dados simulados
    mock_indicators = {
        'current_price': 50000,
        'rsi': 25,
        'sma_short': 49800,
        'sma_long': 49500,
        'ema_short': 49900,
        'ema_long': 49600,
        'atr': 500,
        'trend_direction': 'ALTISTA',
        'data_points': 100,
        'support_resistance': {'support': 49000, 'resistance': 51000}
    }
    
    # Testar estratégias
    scalp = ScalpStrategy()
    day_trade = DayTradeStrategy()
    swing = SwingStrategy()
    
    scalp_signal = scalp.analyze(mock_indicators, 50000)
    day_signal = day_trade.analyze(mock_indicators, 50000)
    swing_signal = swing.analyze(mock_indicators, 50000)
    
    print("=== TESTE DAS ESTRATÉGIAS ===")
    print(f"SCALP: {scalp_signal['action'] if scalp_signal else 'None'} - {scalp_signal['confidence'] if scalp_signal else 0}%")
    print(f"DAY: {day_signal['action'] if day_signal else 'None'} - {day_signal['confidence'] if day_signal else 0}%")
    print(f"SWING: {swing_signal['action'] if swing_signal else 'None'} - {swing_signal['confidence'] if swing_signal else 0}%")
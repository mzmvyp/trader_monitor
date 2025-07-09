# strategies/swing_strategy.py
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class SwingStrategy:
    """Estratégia de Swing Trading - Timeframe 1 hora (IMPLEMENTAÇÃO COMPLETA)"""
    
    def __init__(self):
        self.config = {
            # Indicadores para análise de longo prazo
            'rsi_period': 14,
            'rsi_overbought': 65,  # Menos extremo que day trade
            'rsi_oversold': 35,
            'sma_short': 20,
            'sma_long': 50,
            'sma_trend': 200,  # Tendência muito longa
            'ema_short': 21,
            'ema_long': 55,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            
            # Configurações específicas para swing
            'min_confidence': 50,  # Menos restritivo
            'signal_cooldown_minutes': 240,  # 4 horas
            
            # Gestão de risco para swing
            'stop_loss_atr_multiplier': 3.5,  # Stop mais amplo
            'target_multipliers': [1.5, 2.5, 4.0],  # Targets maiores
            
            # Análise de tendência
            'trend_strength_threshold': 0.25,
            'consolidation_threshold': 0.015,  # 1.5%
            'breakout_threshold': 0.02,  # 2%
            
            # Fibonacci e níveis-chave
            'fibonacci_levels': [0.236, 0.382, 0.5, 0.618, 0.786],
            'pivot_strength': 3
        }
        
        self.name = "SWING"
        self.timeframe = "1h"
        self.hold_time = "3-7 dias"
        
        # Cache para análise multi-período
        self.price_history = []
        self.volume_history = []
    
    def analyze(self, indicators: Dict, current_price: float) -> Optional[Dict]:
        """
        Análise completa para swing trading - 1 hora
        
        Foco em:
        - Tendências de médio prazo
        - Níveis de suporte/resistência significativos
        - Divergências de momentum
        - Padrões de breakout/breakdown
        - Análise de volume institucional
        """
        
        # Verificar dados suficientes para swing (mais dados necessários)
        if indicators.get('data_points', 0) < 100:
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
            'trend_analysis': {},
            'key_levels': {},
            'market_phase': 'UNKNOWN'
        }
        
        # Extrair indicadores
        rsi = indicators.get('rsi', 50)
        sma_short = indicators.get('sma_short', current_price)  # SMA20
        sma_long = indicators.get('sma_long', current_price)    # SMA50
        ema_short = indicators.get('ema_short', current_price)
        ema_long = indicators.get('ema_long', current_price)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend_direction', 'NEUTRO')
        
        confidence = 0
        reasons = []
        
        # === 1. ANÁLISE DE TENDÊNCIA PRINCIPAL ===
        trend_analysis = self._analyze_major_trend(indicators, current_price)
        signal['trend_analysis'] = trend_analysis
        confidence += trend_analysis['score']
        reasons.extend(trend_analysis['reasons'])
        signal['market_phase'] = trend_analysis['phase']
        
        # === 2. ANÁLISE RSI PARA SWING ===
        rsi_analysis = self._analyze_rsi_swing(rsi, trend_analysis)
        confidence += rsi_analysis['score']
        reasons.extend(rsi_analysis['reasons'])
        
        # === 3. ANÁLISE DE MÉDIAS MÓVEIS LONGAS ===
        ma_analysis = self._analyze_moving_averages_swing(current_price, sma_short, sma_long)
        confidence += ma_analysis['score']
        reasons.extend(ma_analysis['reasons'])
        
        # === 4. ANÁLISE MACD ===
        macd_analysis = self._analyze_macd(indicators)
        confidence += macd_analysis['score']
        reasons.extend(macd_analysis['reasons'])
        
        # === 5. SUPORTE E RESISTÊNCIA CHAVE ===
        sr_analysis = self._analyze_key_levels(indicators, current_price)
        signal['key_levels'] = sr_analysis['levels']
        confidence += sr_analysis['score']
        reasons.extend(sr_analysis['reasons'])
        
        # === 6. ANÁLISE DE BREAKOUT/BREAKDOWN ===
        breakout_analysis = self._analyze_breakouts(indicators, current_price)
        confidence += breakout_analysis['score']
        reasons.extend(breakout_analysis['reasons'])
        
        # === 7. VOLUME INSTITUCIONAL ===
        volume_analysis = self._analyze_institutional_volume(indicators)
        confidence += volume_analysis['score']
        reasons.extend(volume_analysis['reasons'])
        
        # === 8. FIBONACCI E RETRAÇÃO ===
        fib_analysis = self._analyze_fibonacci_levels(indicators, current_price)
        confidence += fib_analysis['score']
        reasons.extend(fib_analysis['reasons'])
        
        # === 9. DIVERGÊNCIAS DE MOMENTUM ===
        divergence_analysis = self._analyze_momentum_divergence(indicators, current_price)
        confidence += divergence_analysis['score']
        reasons.extend(divergence_analysis['reasons'])
        
        # === 10. FILTROS DE MERCADO ===
        # Filtro de volatilidade (swing prefere volatilidade moderada)
        if atr > 0:
            volatility = atr / current_price
            if 0.02 <= volatility <= 0.08:  # 2-8% volatilidade ideal para swing
                confidence += 5
                reasons.append('Volatilidade ideal para swing')
            elif volatility > 0.12:  # Muito volátil
                confidence *= 0.6
                reasons.append('Volatilidade excessiva')
        
        # === 11. CONTEXTO DE MERCADO ===
        market_context = self._analyze_market_context(trend_analysis, current_price)
        confidence += market_context['score']
        reasons.extend(market_context['reasons'])
        
        # === 12. DETERMINAÇÃO FINAL ===
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
            
            # Risk/reward para swing (usar target médio)
            if signal['targets'] and len(signal['targets']) >= 2:
                risk = abs(current_price - signal['stop_loss'])
                reward = abs(signal['targets'][1] - current_price)  # Target intermediário
                signal['risk_reward'] = reward / risk if risk > 0 else 0
        
        signal['confidence'] = abs_confidence
        signal['reasons'] = reasons[:10]  # Manter as mais importantes
        
        return signal
    
    def _analyze_major_trend(self, indicators: Dict, current_price: float) -> Dict:
        """Análise da tendência principal de médio/longo prazo"""
        
        score = 0
        reasons = []
        
        sma_short = indicators.get('sma_short', current_price)  # SMA20
        sma_long = indicators.get('sma_long', current_price)    # SMA50
        
        # Estrutura das médias
        if current_price > sma_short > sma_long:
            score += 35
            reasons.append('Estrutura altista forte (preço > SMA20 > SMA50)')
            phase = 'UPTREND'
        elif current_price < sma_short < sma_long:
            score -= 35
            reasons.append('Estrutura baixista forte (preço < SMA20 < SMA50)')
            phase = 'DOWNTREND'
        elif sma_short > sma_long and current_price > sma_long:
            score += 20
            reasons.append('Tendência altista em desenvolvimento')
            phase = 'EMERGING_UPTREND'
        elif sma_short < sma_long and current_price < sma_long:
            score -= 20
            reasons.append('Tendência baixista em desenvolvimento')
            phase = 'EMERGING_DOWNTREND'
        else:
            phase = 'CONSOLIDATION'
            reasons.append('Mercado em consolidação')
        
        # Força da tendência
        if sma_long > 0:
            trend_strength = abs(sma_short - sma_long) / sma_long
            
            if trend_strength > self.config['trend_strength_threshold']:
                score += 10 if sma_short > sma_long else -10
                reasons.append(f'Tendência forte ({trend_strength:.2%})')
            elif trend_strength < 0.01:  # Muito fracas
                score *= 0.7
                reasons.append('Tendência muito fraca')
        
        # Momentum da tendência
        ema_short = indicators.get('ema_short', current_price)
        ema_long = indicators.get('ema_long', current_price)
        
        if ema_long > 0:
            ema_momentum = (ema_short - ema_long) / ema_long
            if ema_momentum > 0.02:  # 2% de momentum
                score += 15
                reasons.append('Momentum EMA altista')
            elif ema_momentum < -0.02:
                score -= 15
                reasons.append('Momentum EMA baixista')
        
        return {
            'score': score,
            'reasons': reasons,
            'phase': phase,
            'strength': trend_strength if 'trend_strength' in locals() else 0,
            'momentum': ema_momentum if 'ema_momentum' in locals() else 0
        }
    
    def _analyze_rsi_swing(self, rsi: float, trend_analysis: Dict) -> Dict:
        """Análise RSI específica para swing trading"""
        
        score = 0
        reasons = []
        
        phase = trend_analysis.get('phase', 'CONSOLIDATION')
        
        # RSI em contexto de tendência
        if phase in ['UPTREND', 'EMERGING_UPTREND']:
            if 40 <= rsi <= 60:  # RSI saudável em uptrend
                score += 20
                reasons.append('RSI saudável em tendência altista')
            elif rsi <= self.config['rsi_oversold']:
                score += 25
                reasons.append('RSI oversold em uptrend (oportunidade)')
            elif rsi >= 70:  # Cuidado em uptrend
                score -= 10
                reasons.append('RSI overbought em uptrend')
                
        elif phase in ['DOWNTREND', 'EMERGING_DOWNTREND']:
            if 40 <= rsi <= 60:  # RSI neutro em downtrend
                score -= 20
                reasons.append('RSI neutro em tendência baixista')
            elif rsi >= self.config['rsi_overbought']:
                score -= 25
                reasons.append('RSI overbought em downtrend (oportunidade venda)')
            elif rsi <= 30:  # Cuidado em downtrend
                score += 10
                reasons.append('RSI oversold em downtrend')
                
        else:  # CONSOLIDATION
            if rsi <= self.config['rsi_oversold']:
                score += 15
                reasons.append('RSI oversold em consolidação')
            elif rsi >= self.config['rsi_overbought']:
                score -= 15
                reasons.append('RSI overbought em consolidação')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_moving_averages_swing(self, price: float, sma_20: float, sma_50: float) -> Dict:
        """Análise específica de médias para swing"""
        
        score = 0
        reasons = []
        
        # Distância das médias (swing gosta de entradas próximas das médias)
        if sma_20 > 0:
            distance_sma20 = abs(price - sma_20) / sma_20 * 100
            
            if distance_sma20 <= 2:  # Dentro de 2% da SMA20
                score += 15
                reasons.append('Preço próximo da SMA20 (entrada ideal)')
            elif distance_sma20 > 5:  # Muito longe
                score *= 0.6
                reasons.append('Preço distante da SMA20')
        
        if sma_50 > 0:
            distance_sma50 = abs(price - sma_50) / sma_50 * 100
            
            if distance_sma50 <= 3:  # Dentro de 3% da SMA50
                score += 10
                reasons.append('Preço próximo da SMA50')
        
        # Convergência/divergência das médias
        if sma_50 > 0:
            ma_convergence = abs(sma_20 - sma_50) / sma_50 * 100
            
            if ma_convergence < 1:  # Médias muito próximas
                score *= 0.8
                reasons.append('Médias convergindo (indecisão)')
            elif ma_convergence > 5:  # Médias muito distantes
                score += 5
                reasons.append('Médias bem separadas (tendência clara)')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_macd(self, indicators: Dict) -> Dict:
        """Análise MACD (simplificada)"""
        
        score = 0
        reasons = []
        
        # Simular MACD usando EMAs disponíveis
        ema_short = indicators.get('ema_short', 0)
        ema_long = indicators.get('ema_long', 0)
        
        if ema_long > 0:
            macd_line = ema_short - ema_long
            macd_percentage = macd_line / ema_long * 100
            
            if macd_percentage > 0.5:  # MACD positivo forte
                score += 15
                reasons.append('MACD altista forte')
            elif macd_percentage > 0:
                score += 8
                reasons.append('MACD altista')
            elif macd_percentage < -0.5:  # MACD negativo forte
                score -= 15
                reasons.append('MACD baixista forte')
            elif macd_percentage < 0:
                score -= 8
                reasons.append('MACD baixista')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_key_levels(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de níveis-chave de suporte e resistência"""
        
        score = 0
        reasons = []
        levels = {}
        
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        resistance = support_resistance.get('resistance', 0)
        
        levels['support'] = support
        levels['resistance'] = resistance
        
        # Análise de suporte
        if support > 0:
            distance_support = (current_price - support) / support * 100
            
            if distance_support <= 1.5:  # Muito próximo do suporte
                score += 25
                reasons.append('Muito próximo do suporte chave')
            elif distance_support <= 3:
                score += 15
                reasons.append('Próximo do suporte')
            elif distance_support >= 10:  # Longe do suporte
                score += 5
                reasons.append('Distante do suporte (espaço para subir)')
        
        # Análise de resistência
        if resistance > 0:
            distance_resistance = (resistance - current_price) / current_price * 100
            
            if distance_resistance <= 1.5:  # Muito próximo da resistência
                score -= 25
                reasons.append('Muito próximo da resistência chave')
            elif distance_resistance <= 3:
                score -= 15
                reasons.append('Próximo da resistência')
            elif distance_resistance >= 10:  # Longe da resistência
                score -= 5
                reasons.append('Distante da resistência (espaço para cair)')
        
        return {'score': score, 'reasons': reasons, 'levels': levels}
    
    def _analyze_breakouts(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de breakouts e breakdowns"""
        
        score = 0
        reasons = []
        
        support_resistance = indicators.get('support_resistance', {})
        support = support_resistance.get('support', 0)
        resistance = support_resistance.get('resistance', 0)
        
        # Breakout de resistência
        if resistance > 0 and current_price > resistance * 1.01:  # 1% acima
            score += 20
            reasons.append('Breakout de resistência confirmado')
        elif resistance > 0 and current_price > resistance * 0.995:  # Testando resistência
            score += 10
            reasons.append('Testando resistência (potencial breakout)')
        
        # Breakdown de suporte
        if support > 0 and current_price < support * 0.99:  # 1% abaixo
            score -= 20
            reasons.append('Breakdown de suporte confirmado')
        elif support > 0 and current_price < support * 1.005:  # Testando suporte
            score -= 10
            reasons.append('Testando suporte (potencial breakdown)')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_institutional_volume(self, indicators: Dict) -> Dict:
        """Análise de volume institucional"""
        
        score = 0
        reasons = []
        
        volume_sma = indicators.get('volume_sma', 0)
        current_volume = indicators.get('current_volume', 0)
        
        if volume_sma > 0 and current_volume > 0:
            volume_ratio = current_volume / volume_sma
            
            if volume_ratio >= 2.0:  # Volume muito alto
                score += 20
                reasons.append('Volume institucional (2x+ média)')
            elif volume_ratio >= 1.5:
                score += 15
                reasons.append('Volume elevado (1.5x+ média)')
            elif volume_ratio >= 1.2:
                score += 8
                reasons.append('Volume acima da média')
            elif volume_ratio < 0.5:  # Volume muito baixo
                score *= 0.7
                reasons.append('Volume baixo (falta confirmação)')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_fibonacci_levels(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de níveis de Fibonacci (simplificada)"""
        
        score = 0
        reasons = []
        
        # Simular níveis de Fibonacci usando support/resistance
        support = indicators.get('support_resistance', {}).get('support', 0)
        resistance = indicators.get('support_resistance', {}).get('resistance', 0)
        
        if support > 0 and resistance > 0:
            range_size = resistance - support
            
            # Níveis de Fibonacci
            fib_levels = {
                '23.6%': support + (range_size * 0.236),
                '38.2%': support + (range_size * 0.382),
                '50.0%': support + (range_size * 0.5),
                '61.8%': support + (range_size * 0.618),
                '78.6%': support + (range_size * 0.786)
            }
            
            # Verificar se está próximo de algum nível Fibonacci
            for level_name, level_price in fib_levels.items():
                distance = abs(current_price - level_price) / level_price * 100
                
                if distance <= 1:  # Dentro de 1% do nível Fibonacci
                    if level_name in ['38.2%', '50.0%', '61.8%']:  # Níveis mais importantes
                        score += 10
                        reasons.append(f'Próximo do Fibonacci {level_name}')
                    else:
                        score += 5
                        reasons.append(f'Nível Fibonacci {level_name}')
                    break
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_momentum_divergence(self, indicators: Dict, current_price: float) -> Dict:
        """Análise de divergências de momentum"""
        
        score = 0
        reasons = []
        
        # Atualizar histórico
        self.price_history.append(current_price)
        if len(self.price_history) > 50:  # Manter últimos 50 períodos
            self.price_history.pop(0)
        
        # Divergência simples (precisaria de mais dados históricos para implementação completa)
        if len(self.price_history) >= 20:
            recent_high = max(self.price_history[-10:])
            previous_high = max(self.price_history[-20:-10])
            
            rsi = indicators.get('rsi', 50)
            
            # Divergência baixista: preço faz máximo maior, mas momentum enfraquece
            if (recent_high > previous_high * 1.01 and  # Novo máximo significativo
                rsi < 60):  # Mas RSI não confirma
                score -= 15
                reasons.append('Possível divergência baixista')
            
            # Divergência altista: preço faz mínimo menor, mas momentum melhora
            recent_low = min(self.price_history[-10:])
            previous_low = min(self.price_history[-20:-10])
            
            if (recent_low < previous_low * 0.99 and  # Novo mínimo significativo
                rsi > 40):  # Mas RSI está melhorando
                score += 15
                reasons.append('Possível divergência altista')
        
        return {'score': score, 'reasons': reasons}
    
    def _analyze_market_context(self, trend_analysis: Dict, current_price: float) -> Dict:
        """Análise do contexto geral de mercado"""
        
        score = 0
        reasons = []
        
        phase = trend_analysis.get('phase', 'CONSOLIDATION')
        strength = trend_analysis.get('strength', 0)
        
        # Contexto baseado na fase do mercado
        if phase == 'UPTREND' and strength > 0.03:  # Tendência altista forte
            score += 10
            reasons.append('Contexto altista forte favorável')
        elif phase == 'DOWNTREND' and strength > 0.03:  # Tendência baixista forte
            score -= 10
            reasons.append('Contexto baixista forte')
        elif phase == 'CONSOLIDATION':
            score *= 0.9  # Reduzir um pouco a confiança
            reasons.append('Mercado lateral (aguardar direção)')
        
        return {'score': score, 'reasons': reasons}

# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE SWING TRADING STRATEGY ===")
    
    # Dados simulados
    mock_indicators = {
        'current_price': 67543.21,
        'rsi': 42.5,
        'sma_short': 67200,    # SMA20
        'sma_long': 66800,     # SMA50
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
    
    swing_trade = SwingStrategy()
    signal = swing_trade.analyze(mock_indicators, mock_indicators['current_price'])
    
    if signal:
        print(f"Ação: {signal['action']}")
        print(f"Confiança: {signal['confidence']:.1f}%")
        print(f"Stop Loss: ${signal['stop_loss']:,.2f}")
        if signal['targets']:
            print(f"Targets: ${signal['targets'][0]:,.2f} | ${signal['targets'][1]:,.2f} | ${signal['targets'][2]:,.2f}")
        print(f"Risk/Reward: {signal['risk_reward']:.2f}")
        print(f"Fase do Mercado: {signal['market_phase']}")
        print(f"Razões: {', '.join(signal['reasons'][:3])}")
    else:
        print("Dados insuficientes")
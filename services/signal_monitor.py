# services/signal_monitor.py
# Monitor contínuo para gerenciar lifecycle dos sinais de trading

import threading
import time
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.logging_config import logger
from config import app_config

class SignalMonitor:
    """
    Monitor contínuo que:
    1. Verifica sinais ativos periodicamente
    2. Atualiza status quando atingem targets/stops
    3. Remove sinais antigos da memória
    4. Evita duplicação
    5. Persiste mudanças no banco
    """
    
    def __init__(self, trading_analyzer, db_path: str = None):
        self.trading_analyzer = trading_analyzer
        self.db_path = db_path or app_config.TRADING_ANALYZER_DB
        self.is_running = False
        self.monitor_thread = None
        self.check_interval = 30  # Verifica a cada 30 segundos
        self.last_cleanup = datetime.now()
        self.cleanup_interval = 3600  # Limpeza a cada 1 hora
        
        # Controle de duplicação
        self.processed_signals = set()
        self.last_price_update = {}
        
        logger.info("[MONITOR] Signal Monitor inicializado")
    
    def start_monitoring(self):
        """Inicia o monitor em thread separada"""
        if self.is_running:
            logger.warning("[MONITOR] Monitor já está rodando")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("[MONITOR] Monitor de sinais iniciado ✅")
    
    def stop_monitoring(self):
        """Para o monitor"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("[MONITOR] Monitor de sinais parado")
    
    def _monitoring_loop(self):
        """Loop principal do monitor"""
        while self.is_running:
            try:
                # 1. Verificar sinais ativos
                self._check_active_signals()
                
                # 2. Limpar sinais antigos periodicamente
                if self._should_cleanup():
                    self._cleanup_old_signals()
                
                # 3. Verificar duplicações
                self._fix_duplicated_signals()
                
                # 4. Aguardar próxima verificação
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"[MONITOR] Erro no loop de monitoramento: {e}")
                time.sleep(60)  # Espera 1 minuto em caso de erro
    
    def _check_active_signals(self):
        """Verifica e atualiza sinais ativos"""
        try:
            # Obter preço atual do Bitcoin
            current_price = self._get_current_bitcoin_price()
            if not current_price:
                return
            
            # Obter sinais ativos
            active_signals = [s for s in self.trading_analyzer.signals if s.get('status') == 'ACTIVE']
            
            if not active_signals:
                return
            
            updated_signals = 0
            closed_signals = 0
            
            for signal in active_signals:
                try:
                    # Verificar se sinal precisa ser atualizado
                    signal_id = signal.get('id')
                    if self._should_update_signal(signal_id, current_price):
                        
                        # Atualizar P&L
                        old_pnl = signal.get('profit_loss', 0)
                        new_pnl = self._calculate_pnl(signal, current_price)
                        signal['profit_loss'] = new_pnl
                        
                        # Atualizar max profit/drawdown
                        signal['max_profit'] = max(signal.get('max_profit', 0), new_pnl)
                        signal['max_drawdown'] = min(signal.get('max_drawdown', 0), new_pnl)
                        
                        # Verificar condições de saída
                        exit_status = self._check_exit_conditions(signal, current_price)
                        
                        if exit_status:
                            # Fechar sinal
                            signal['status'] = exit_status
                            signal['exit_price'] = current_price
                            signal['exit_time'] = datetime.now().isoformat()
                            signal['updated_at'] = datetime.now().isoformat()
                            
                            # Persistir no banco
                            self._update_signal_in_db(signal)
                            
                            logger.info(f"[MONITOR] Sinal #{signal_id} fechado: {exit_status} | P&L: {new_pnl:.2f}%")
                            closed_signals += 1
                        
                        elif abs(new_pnl - old_pnl) > 0.01:  # Mudança significativa
                            # Apenas atualizar P&L
                            self._update_signal_pnl_in_db(signal)
                            updated_signals += 1
                        
                        # Registrar última atualização
                        self.last_price_update[signal_id] = {
                            'price': current_price,
                            'timestamp': datetime.now()
                        }
                
                except Exception as e:
                    logger.error(f"[MONITOR] Erro ao processar sinal {signal.get('id')}: {e}")
            
            if updated_signals > 0 or closed_signals > 0:
                logger.debug(f"[MONITOR] Sinais processados: {updated_signals} atualizados, {closed_signals} fechados")
                
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao verificar sinais ativos: {e}")
    
    def _should_update_signal(self, signal_id: str, current_price: float) -> bool:
        """Verifica se sinal precisa ser atualizado"""
        if not signal_id:
            return True
        
        last_update = self.last_price_update.get(signal_id)
        if not last_update:
            return True
        
        # Atualizar se preço mudou significativamente
        price_diff = abs(current_price - last_update['price']) / last_update['price']
        if price_diff > 0.001:  # 0.1% de mudança
            return True
        
        # Atualizar se passou muito tempo
        time_diff = datetime.now() - last_update['timestamp']
        if time_diff > timedelta(minutes=5):
            return True
        
        return False
    
    def _calculate_pnl(self, signal: Dict, current_price: float) -> float:
        """Calcula P&L atual do sinal"""
        try:
            entry_price = signal.get('entry_price', 0)
            if not entry_price:
                return 0
            
            signal_type = signal.get('signal_type', signal.get('pattern_type', ''))
            is_buy = 'BUY' in signal_type.upper()
            
            if is_buy:
                pnl = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl = ((entry_price - current_price) / entry_price) * 100
            
            return round(pnl, 2)
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao calcular P&L: {e}")
            return 0
    
    def _check_exit_conditions(self, signal: Dict, current_price: float) -> Optional[str]:
        """Verifica se sinal deve ser fechado"""
        try:
            signal_type = signal.get('signal_type', signal.get('pattern_type', ''))
            is_buy = 'BUY' in signal_type.upper()
            
            # Obter níveis
            stop_loss = signal.get('stop_loss', 0)
            target_1 = signal.get('target_1', signal.get('target_price', 0))
            target_2 = signal.get('target_2', 0)
            target_3 = signal.get('target_3', 0)
            
            if is_buy:
                # Sinal de COMPRA
                if current_price <= stop_loss:
                    return 'HIT_STOP'
                elif target_3 and current_price >= target_3:
                    return 'HIT_TARGET_3'
                elif target_2 and current_price >= target_2:
                    return 'HIT_TARGET_2'
                elif target_1 and current_price >= target_1:
                    return 'HIT_TARGET'
            else:
                # Sinal de VENDA
                if current_price >= stop_loss:
                    return 'HIT_STOP'
                elif target_3 and current_price <= target_3:
                    return 'HIT_TARGET_3'
                elif target_2 and current_price <= target_2:
                    return 'HIT_TARGET_2'
                elif target_1 and current_price <= target_1:
                    return 'HIT_TARGET'
            
            # Verificar expiração (24 horas)
            created_at = signal.get('created_at')
            if created_at:
                try:
                    signal_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if datetime.now() - signal_time > timedelta(hours=24):
                        return 'EXPIRED'
                except:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao verificar condições de saída: {e}")
            return None
    
    def _update_signal_in_db(self, signal: Dict):
        """Atualiza sinal completo no banco de dados"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Atualizar na tabela principal
            cursor.execute("""
                UPDATE trading_signals 
                SET status = ?, profit_loss = ?, activated = ?
                WHERE id = ?
            """, (
                signal['status'],
                signal.get('profit_loss', 0),
                True,
                signal.get('id')
            ))
            
            # Se existe tabela enhanced_signals, atualizar também
            try:
                cursor.execute("""
                    UPDATE enhanced_signals 
                    SET status = ?, profit_loss = ?, max_profit = ?, max_drawdown = ?, updated_at = ?
                    WHERE timestamp = ? AND signal_type = ?
                """, (
                    signal['status'],
                    signal.get('profit_loss', 0),
                    signal.get('max_profit', 0),
                    signal.get('max_drawdown', 0),
                    signal.get('updated_at'),
                    signal.get('timestamp'),
                    signal.get('signal_type', signal.get('pattern_type'))
                ))
            except:
                pass  # Tabela pode não existir
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao atualizar sinal no banco: {e}")
    
    def _update_signal_pnl_in_db(self, signal: Dict):
        """Atualiza apenas P&L no banco (operação mais leve)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE trading_signals 
                SET profit_loss = ?
                WHERE id = ?
            """, (signal.get('profit_loss', 0), signal.get('id')))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao atualizar P&L no banco: {e}")
    
    def _fix_duplicated_signals(self):
        """Remove sinais duplicados da memória"""
        try:
            if not self.trading_analyzer.signals:
                return
            
            # Agrupar por ID
            signals_by_id = {}
            for signal in self.trading_analyzer.signals:
                signal_id = signal.get('id')
                if signal_id:
                    if signal_id not in signals_by_id:
                        signals_by_id[signal_id] = []
                    signals_by_id[signal_id].append(signal)
            
            # Encontrar duplicados
            duplicated_ids = [sid for sid, slist in signals_by_id.items() if len(slist) > 1]
            
            if duplicated_ids:
                logger.info(f"[MONITOR] Removendo duplicações: {len(duplicated_ids)} IDs duplicados")
                
                # Manter apenas o sinal mais recente de cada ID
                clean_signals = []
                for signal_id, signal_list in signals_by_id.items():
                    if len(signal_list) > 1:
                        # Ordenar por timestamp e manter o mais recente
                        sorted_signals = sorted(
                            signal_list, 
                            key=lambda s: s.get('created_at', ''), 
                            reverse=True
                        )
                        clean_signals.append(sorted_signals[0])
                    else:
                        clean_signals.append(signal_list[0])
                
                # Atualizar lista
                self.trading_analyzer.signals = clean_signals
                
                logger.info(f"[MONITOR] Duplicações removidas. Sinais restantes: {len(clean_signals)}")
        
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao remover duplicações: {e}")
    
    def _should_cleanup(self) -> bool:
        """Verifica se deve fazer limpeza"""
        return datetime.now() - self.last_cleanup > timedelta(seconds=self.cleanup_interval)
    
    def _cleanup_old_signals(self):
        """Remove sinais antigos da memória"""
        try:
            if not self.trading_analyzer.signals:
                return
            
            initial_count = len(self.trading_analyzer.signals)
            
            # Remover sinais fechados há mais de 1 hora da memória
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            active_or_recent = []
            for signal in self.trading_analyzer.signals:
                status = signal.get('status', 'ACTIVE')
                
                if status == 'ACTIVE':
                    # Manter sinais ativos
                    active_or_recent.append(signal)
                else:
                    # Verificar se fechou recentemente
                    updated_at = signal.get('updated_at', signal.get('created_at'))
                    if updated_at:
                        try:
                            signal_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                            if signal_time > cutoff_time:
                                active_or_recent.append(signal)  # Manter se fechou recentemente
                        except:
                            pass  # Remover se timestamp inválido
            
            # Atualizar lista
            self.trading_analyzer.signals = active_or_recent
            
            # Salvar estado
            self.trading_analyzer.save_analyzer_state()
            
            removed_count = initial_count - len(active_or_recent)
            if removed_count > 0:
                logger.info(f"[MONITOR] Limpeza concluída: {removed_count} sinais antigos removidos da memória")
            
            self.last_cleanup = datetime.now()
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro na limpeza: {e}")
    
    def _get_current_bitcoin_price(self) -> Optional[float]:
        """Obtém preço atual do Bitcoin"""
        try:
            # Tentar obter do trading analyzer
            if self.trading_analyzer.price_history:
                return self.trading_analyzer.price_history[-1]['price']
            
            # Fallback: tentar obter do BitcoinStreamer via app
            # (isso será configurado no IntegratedController)
            return None
            
        except Exception as e:
            logger.error(f"[MONITOR] Erro ao obter preço do Bitcoin: {e}")
            return None
    
    def set_current_price_source(self, price_source_func):
        """Configura fonte de preço atual"""
        self._get_current_bitcoin_price = price_source_func
    
    def get_monitor_stats(self) -> Dict:
        """Retorna estatísticas do monitor"""
        return {
            'is_running': self.is_running,
            'check_interval': self.check_interval,
            'last_cleanup': self.last_cleanup.isoformat(),
            'processed_signals_count': len(self.processed_signals),
            'tracked_signals_count': len(self.last_price_update),
            'active_signals_in_analyzer': len([
                s for s in self.trading_analyzer.signals 
                if s.get('status') == 'ACTIVE'
            ]),
            'total_signals_in_analyzer': len(self.trading_analyzer.signals)
        }
    
    def force_check_signals(self):
        """Força verificação imediata dos sinais"""
        logger.info("[MONITOR] Verificação forçada de sinais iniciada")
        self._check_active_signals()
        self._fix_duplicated_signals()
    
    def reset_duplicates_tracking(self):
        """Reseta tracking de duplicados"""
        self.processed_signals.clear()
        self.last_price_update.clear()
        logger.info("[MONITOR] Tracking de duplicados resetado")
# middleware/config_middleware.py - Middleware para interceptar e aplicar configurações

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional
from utils.logging_config import logger

class ConfigurationMiddleware:
    """
    Middleware que intercepta mudanças de configuração e as aplica automaticamente
    aos componentes do sistema, com cache, rate limiting e rollback automático.
    """
    
    def __init__(self, app_instance=None):
        self.app_instance = app_instance
        self.config_cache = {}
        self.last_applied_config = {}
        self.config_lock = threading.Lock()
        
        # Rate limiting para aplicação de configurações
        self.last_apply_time = 0
        self.min_apply_interval = 1.0  # Mínimo 1 segundo entre aplicações
        
        # Auto-refresh das configurações
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 30  # 30 segundos
        self.refresh_thread = None
        
        # Callbacks para mudanças de configuração
        self.config_change_callbacks = []
        
        # Histórico de aplicações
        self.application_history = []
        self.max_history_size = 100
        
        # Configuração de rollback automático
        self.auto_rollback_enabled = True
        self.rollback_timeout = 300  # 5 minutos
        
        self.start_auto_refresh()
    
    def register_app_instance(self, app_instance):
        """Registra instância da aplicação para aplicar configurações"""
        self.app_instance = app_instance
        logger.info("[CONFIG_MIDDLEWARE] Instância da aplicação registrada")
    
    def add_config_change_callback(self, callback: Callable[[Dict, Dict], None]):
        """
        Adiciona callback para ser chamado quando configuração muda
        
        Args:
            callback: Função que recebe (old_config, new_config)
        """
        self.config_change_callbacks.append(callback)
        logger.info(f"[CONFIG_MIDDLEWARE] Callback registrado: {callback.__name__}")
    
    def remove_config_change_callback(self, callback: Callable):
        """Remove callback de mudança de configuração"""
        if callback in self.config_change_callbacks:
            self.config_change_callbacks.remove(callback)
            logger.info(f"[CONFIG_MIDDLEWARE] Callback removido: {callback.__name__}")
    
    def intercept_config_change(self, new_config: Dict[str, Any], 
                               source: str = 'unknown', 
                               apply_immediately: bool = True) -> Dict[str, Any]:
        """
        Intercepta mudança de configuração e a processa
        
        Args:
            new_config: Nova configuração
            source: Origem da mudança (api, ui, auto)
            apply_immediately: Se deve aplicar imediatamente
            
        Returns:
            Resultado da operação
        """
        try:
            with self.config_lock:
                # Verificar rate limiting
                current_time = time.time()
                if current_time - self.last_apply_time < self.min_apply_interval:
                    return {
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': self.min_apply_interval - (current_time - self.last_apply_time)
                    }
                
                # Validar configuração
                validation_result = self._validate_config_change(new_config)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': 'Configuration validation failed',
                        'validation_errors': validation_result['errors']
                    }
                
                # Cachear configuração anterior para rollback
                old_config = self.config_cache.copy()
                
                # Atualizar cache
                self.config_cache = new_config.copy()
                
                # Aplicar configuração se solicitado
                if apply_immediately and self.app_instance:
                    apply_result = self._apply_config_safely(new_config, old_config)
                    
                    if apply_result['success']:
                        self.last_apply_time = current_time
                        self.last_applied_config = new_config.copy()
                        
                        # Registrar no histórico
                        self._add_to_history(old_config, new_config, source, apply_result)
                        
                        # Chamar callbacks
                        self._call_config_change_callbacks(old_config, new_config)
                        
                        # Agendar rollback automático se habilitado
                        if self.auto_rollback_enabled:
                            self._schedule_auto_rollback(old_config, new_config)
                        
                        logger.info(f"[CONFIG_MIDDLEWARE] Configuração aplicada com sucesso (source: {source})")
                        return {
                            'success': True,
                            'applied_at': datetime.now().isoformat(),
                            'source': source,
                            'components_affected': apply_result.get('applied_components', [])
                        }
                    else:
                        # Rollback do cache em caso de erro
                        self.config_cache = old_config
                        return {
                            'success': False,
                            'error': f'Failed to apply configuration: {apply_result["error"]}',
                            'rollback_performed': True
                        }
                else:
                    # Apenas cachear sem aplicar
                    self._add_to_history(old_config, new_config, source, {'success': True, 'applied': False})
                    return {
                        'success': True,
                        'cached_at': datetime.now().isoformat(),
                        'applied': False,
                        'source': source
                    }
                    
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro ao interceptar mudança: {e}")
            return {
                'success': False,
                'error': str(e),
                'exception_type': type(e).__name__
            }
    
    def _validate_config_change(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Valida mudança de configuração"""
        try:
            errors = []
            warnings = []
            
            # Validações básicas de estrutura
            if not isinstance(config, dict):
                errors.append("Configuration must be a dictionary")
                return {'valid': False, 'errors': errors, 'warnings': warnings}
            
            # Validar seção trading se presente
            if 'trading' in config:
                trading_validation = self._validate_trading_config(config['trading'])
                errors.extend(trading_validation['errors'])
                warnings.extend(trading_validation['warnings'])
            
            # Validar seção streaming se presente  
            if 'streaming' in config:
                streaming_validation = self._validate_streaming_config(config['streaming'])
                errors.extend(streaming_validation['errors'])
                warnings.extend(streaming_validation['warnings'])
            
            # Validações específicas
            specific_errors = self._validate_specific_rules(config)
            errors.extend(specific_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro na validação: {e}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}'],
                'warnings': []
            }
    
    def _validate_trading_config(self, trading_config: Dict) -> Dict:
        """Valida configuração de trading"""
        errors = []
        warnings = []
        
        if 'ta_params' in trading_config:
            ta_params = trading_config['ta_params']
            
            # RSI validation
            if 'rsi_overbought' in ta_params and 'rsi_oversold' in ta_params:
                if ta_params['rsi_oversold'] >= ta_params['rsi_overbought']:
                    errors.append("RSI oversold must be less than overbought")
            
            # Moving averages validation
            if 'sma_short' in ta_params and 'sma_long' in ta_params:
                if ta_params['sma_short'] >= ta_params['sma_long']:
                    errors.append("Short SMA period must be less than long SMA period")
            
            if 'ema_short' in ta_params and 'ema_long' in ta_params:
                if ta_params['ema_short'] >= ta_params['ema_long']:
                    errors.append("Short EMA period must be less than long EMA period")
            
            # Confidence validation
            if 'min_confidence' in ta_params:
                confidence = ta_params['min_confidence']
                if not (0 <= confidence <= 100):
                    errors.append("Minimum confidence must be between 0 and 100")
                elif confidence < 50:
                    warnings.append("Low confidence threshold may generate too many signals")
        
        if 'indicator_weights' in trading_config:
            weights = trading_config['indicator_weights']
            total_weight = sum(weights.values())
            
            if abs(total_weight - 1.0) > 0.01:
                errors.append(f"Indicator weights must sum to 1.0 (current: {total_weight:.3f})")
            
            for indicator, weight in weights.items():
                if not (0 <= weight <= 1):
                    errors.append(f"Weight for {indicator} must be between 0 and 1")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_streaming_config(self, streaming_config: Dict) -> Dict:
        """Valida configuração de streaming"""
        errors = []
        warnings = []
        
        for asset, config in streaming_config.items():
            if isinstance(config, dict):
                if 'fetch_interval' in config:
                    interval = config['fetch_interval']
                    if not (30 <= interval <= 3600):
                        errors.append(f"Fetch interval for {asset} must be between 30 and 3600 seconds")
                    elif interval < 60:
                        warnings.append(f"Very short fetch interval for {asset} may cause rate limiting")
                
                if 'max_queue_size' in config:
                    queue_size = config['max_queue_size']
                    if not (10 <= queue_size <= 1000):
                        errors.append(f"Queue size for {asset} must be between 10 and 1000")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_specific_rules(self, config: Dict) -> list:
        """Validações específicas e personalizadas"""
        errors = []
        
        try:
            # Validação de consistência entre configurações
            if 'trading' in config and 'streaming' in config:
                # Verificar se intervalos de trading são compatíveis com streaming
                trading_cooldown = config.get('trading', {}).get('signal_config', {}).get('signal_cooldown_minutes', 60)
                
                for asset, stream_config in config.get('streaming', {}).items():
                    if isinstance(stream_config, dict):
                        fetch_interval = stream_config.get('fetch_interval', 300)
                        if trading_cooldown * 60 < fetch_interval * 2:
                            errors.append(f"Signal cooldown too short for {asset} fetch interval")
            
            # Validar limites de recursos
            if 'trading' in config:
                max_signals = config.get('trading', {}).get('signal_config', {}).get('max_active_signals', 5)
                if max_signals > 50:
                    errors.append("Too many active signals may impact performance")
            
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro nas validações específicas: {e}")
            errors.append(f"Specific validation error: {str(e)}")
        
        return errors
    
    def _apply_config_safely(self, new_config: Dict, old_config: Dict) -> Dict:
        """Aplica configuração de forma segura com rollback automático"""
        try:
            # Aplicar configuração usando o config manager
            from config_manager import dynamic_config_manager
            
            apply_result = dynamic_config_manager.apply_config_to_system(self.app_instance)
            
            if apply_result['success']:
                logger.info(f"[CONFIG_MIDDLEWARE] Configuração aplicada: {', '.join(apply_result.get('applied_components', []))}")
                return apply_result
            else:
                logger.error(f"[CONFIG_MIDDLEWARE] Falha na aplicação: {apply_result['error']}")
                return apply_result
                
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro na aplicação segura: {e}")
            return {'success': False, 'error': str(e)}
    
    def _add_to_history(self, old_config: Dict, new_config: Dict, source: str, result: Dict):
        """Adiciona aplicação ao histórico"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'source': source,
                'success': result.get('success', False),
                'applied_components': result.get('applied_components', []),
                'config_changes': self._calculate_config_diff(old_config, new_config),
                'error': result.get('error')
            }
            
            self.application_history.append(history_entry)
            
            # Manter tamanho máximo do histórico
            if len(self.application_history) > self.max_history_size:
                self.application_history = self.application_history[-self.max_history_size:]
                
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro ao adicionar ao histórico: {e}")
    
    def _calculate_config_diff(self, old_config: Dict, new_config: Dict) -> list:
        """Calcula diferenças entre configurações"""
        try:
            changes = []
            
            # Função recursiva para comparar configurações aninhadas
            def compare_dicts(old_dict, new_dict, path=""):
                for key, new_value in new_dict.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    if key not in old_dict:
                        changes.append({
                            'type': 'added',
                            'path': current_path,
                            'new_value': new_value
                        })
                    elif isinstance(new_value, dict) and isinstance(old_dict[key], dict):
                        compare_dicts(old_dict[key], new_value, current_path)
                    elif old_dict[key] != new_value:
                        changes.append({
                            'type': 'modified',
                            'path': current_path,
                            'old_value': old_dict[key],
                            'new_value': new_value
                        })
                
                # Verificar itens removidos
                for key in old_dict:
                    if key not in new_dict:
                        current_path = f"{path}.{key}" if path else key
                        changes.append({
                            'type': 'removed',
                            'path': current_path,
                            'old_value': old_dict[key]
                        })
            
            compare_dicts(old_config, new_config)
            return changes
            
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro ao calcular diff: {e}")
            return []
    
    def _call_config_change_callbacks(self, old_config: Dict, new_config: Dict):
        """Chama todos os callbacks de mudança de configuração"""
        for callback in self.config_change_callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                logger.error(f"[CONFIG_MIDDLEWARE] Erro no callback {callback.__name__}: {e}")
    
    def _schedule_auto_rollback(self, old_config: Dict, new_config: Dict):
        """Agenda rollback automático em caso de problemas"""
        def auto_rollback():
            try:
                time.sleep(self.rollback_timeout)
                
                # Verificar se o sistema está saudável
                if not self._is_system_healthy():
                    logger.warning("[CONFIG_MIDDLEWARE] Sistema não saudável, executando rollback automático")
                    self.rollback_to_config(old_config, 'auto_rollback')
                
            except Exception as e:
                logger.error(f"[CONFIG_MIDDLEWARE] Erro no rollback automático: {e}")
        
        # Executar rollback em thread separada
        rollback_thread = threading.Thread(target=auto_rollback, daemon=True)
        rollback_thread.start()
    
    def _is_system_healthy(self) -> bool:
        """Verifica se o sistema está saudável após mudança de configuração"""
        try:
            if not self.app_instance:
                return True  # Sem app instance, assumir saudável
            
            # Verificar componentes principais
            components_healthy = True
            
            # Verificar trading analyzer
            if hasattr(self.app_instance, 'trading_analyzer'):
                try:
                    status = self.app_instance.trading_analyzer.get_system_status()
                    if 'error' in status:
                        components_healthy = False
                except:
                    components_healthy = False
            
            # Verificar bitcoin streamer
            if hasattr(self.app_instance, 'bitcoin_streamer'):
                try:
                    stats = self.app_instance.bitcoin_streamer.get_stream_statistics()
                    if stats['api_errors'] > 10:  # Muitos erros
                        components_healthy = False
                except:
                    components_healthy = False
            
            return components_healthy
            
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro na verificação de saúde: {e}")
            return False
    
    def rollback_to_config(self, config: Dict, source: str = 'manual') -> Dict:
        """Executa rollback para uma configuração específica"""
        try:
            logger.info(f"[CONFIG_MIDDLEWARE] Executando rollback (source: {source})")
            
            current_config = self.config_cache.copy()
            result = self.intercept_config_change(config, f'rollback_{source}', apply_immediately=True)
            
            if result['success']:
                logger.info("[CONFIG_MIDDLEWARE] Rollback executado com sucesso")
            else:
                logger.error(f"[CONFIG_MIDDLEWARE] Falha no rollback: {result['error']}")
            
            return result
            
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro no rollback: {e}")
            return {'success': False, 'error': str(e)}
    
    def start_auto_refresh(self):
        """Inicia refresh automático das configurações"""
        if self.auto_refresh_enabled and not self.refresh_thread:
            def auto_refresh_worker():
                while self.auto_refresh_enabled:
                    try:
                        time.sleep(self.auto_refresh_interval)
                        
                        # Verificar se há mudanças nas configurações
                        from config_manager import dynamic_config_manager
                        current_config = dynamic_config_manager.load_config()
                        
                        if current_config != self.config_cache:
                            logger.info("[CONFIG_MIDDLEWARE] Detectada mudança externa de configuração")
                            self.intercept_config_change(current_config, 'auto_refresh', apply_immediately=True)
                        
                    except Exception as e:
                        logger.error(f"[CONFIG_MIDDLEWARE] Erro no auto-refresh: {e}")
            
            self.refresh_thread = threading.Thread(target=auto_refresh_worker, daemon=True)
            self.refresh_thread.start()
            logger.info(f"[CONFIG_MIDDLEWARE] Auto-refresh iniciado (intervalo: {self.auto_refresh_interval}s)")
    
    def stop_auto_refresh(self):
        """Para o refresh automático"""
        self.auto_refresh_enabled = False
        logger.info("[CONFIG_MIDDLEWARE] Auto-refresh parado")
    
    def get_middleware_status(self) -> Dict:
        """Retorna status do middleware"""
        return {
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'auto_refresh_interval': self.auto_refresh_interval,
            'auto_rollback_enabled': self.auto_rollback_enabled,
            'rollback_timeout': self.rollback_timeout,
            'min_apply_interval': self.min_apply_interval,
            'config_cached': bool(self.config_cache),
            'last_apply_time': datetime.fromtimestamp(self.last_apply_time).isoformat() if self.last_apply_time > 0 else None,
            'callbacks_registered': len(self.config_change_callbacks),
            'history_size': len(self.application_history),
            'app_instance_registered': self.app_instance is not None
        }
    
    def get_application_history(self, limit: int = 50) -> list:
        """Retorna histórico de aplicações de configuração"""
        return self.application_history[-limit:]
    
    def clear_history(self):
        """Limpa histórico de aplicações"""
        self.application_history.clear()
        logger.info("[CONFIG_MIDDLEWARE] Histórico de aplicações limpo")
    
    def get_cached_config(self) -> Dict:
        """Retorna configuração em cache"""
        return self.config_cache.copy()
    
    def force_config_sync(self) -> Dict:
        """Força sincronização da configuração"""
        try:
            from config_manager import dynamic_config_manager
            
            # Carregar configuração atual do banco
            db_config = dynamic_config_manager.load_config()
            
            # Aplicar se diferente do cache
            if db_config != self.config_cache:
                result = self.intercept_config_change(db_config, 'force_sync', apply_immediately=True)
                logger.info("[CONFIG_MIDDLEWARE] Sincronização forçada executada")
                return result
            else:
                return {'success': True, 'message': 'Configuration already in sync'}
                
        except Exception as e:
            logger.error(f"[CONFIG_MIDDLEWARE] Erro na sincronização forçada: {e}")
            return {'success': False, 'error': str(e)}


# ==================== GLOBAL MIDDLEWARE INSTANCE ====================

# Instância global do middleware
config_middleware = ConfigurationMiddleware()

# Callbacks úteis para logging e monitoramento
def log_config_change(old_config: Dict, new_config: Dict):
    """Callback para logar mudanças de configuração"""
    try:
        changes = []
        
        # Calcular mudanças simples
        def find_changes(old_dict, new_dict, path=""):
            for key, new_value in new_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in old_dict:
                    changes.append(f"Added {current_path} = {new_value}")
                elif isinstance(new_value, dict) and isinstance(old_dict[key], dict):
                    find_changes(old_dict[key], new_value, current_path)
                elif old_dict[key] != new_value:
                    changes.append(f"Changed {current_path}: {old_dict[key]} -> {new_value}")
        
        find_changes(old_config, new_config)
        
        if changes:
            logger.info(f"[CONFIG_CHANGE] {len(changes)} mudanças: {'; '.join(changes[:5])}")
            if len(changes) > 5:
                logger.info(f"[CONFIG_CHANGE] ... e mais {len(changes) - 5} mudanças")
                
    except Exception as e:
        logger.error(f"[CONFIG_CHANGE] Erro no callback de log: {e}")

def monitor_performance_impact(old_config: Dict, new_config: Dict):
    """Callback para monitorar impacto na performance"""
    try:
        # Verificar mudanças que podem impactar performance
        performance_sensitive_keys = [
            'trading.signal_config.max_active_signals',
            'trading.ta_params.min_confidence', 
            'streaming.bitcoin.fetch_interval',
            'streaming.bitcoin.max_queue_size'
        ]
        
        warnings = []
        
        def check_performance_impact(old_dict, new_dict, path=""):
            for key, new_value in new_dict.items():
                current_path = f"{path}.{key}" if path else key
                
                if current_path in performance_sensitive_keys:
                    if key in old_dict and old_dict[key] != new_value:
                        if current_path == 'trading.signal_config.max_active_signals' and new_value > 20:
                            warnings.append(f"High number of active signals ({new_value}) may impact performance")
                        elif current_path == 'streaming.bitcoin.fetch_interval' and new_value < 60:
                            warnings.append(f"Short fetch interval ({new_value}s) may cause rate limiting")
                        elif current_path == 'trading.ta_params.min_confidence' and new_value < 50:
                            warnings.append(f"Low confidence threshold ({new_value}%) may generate many signals")
                
                elif isinstance(new_value, dict) and isinstance(old_dict.get(key, {}), dict):
                    check_performance_impact(old_dict.get(key, {}), new_value, current_path)
        
        check_performance_impact(old_config, new_config)
        
        for warning in warnings:
            logger.warning(f"[PERFORMANCE_IMPACT] {warning}")
            
    except Exception as e:
        logger.error(f"[PERFORMANCE_MONITOR] Erro no callback: {e}")

# Registrar callbacks padrão
config_middleware.add_config_change_callback(log_config_change)
config_middleware.add_config_change_callback(monitor_performance_impact)
# models/trading_signal.py

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalStatus(Enum):
    ACTIVE = "ACTIVE"
    HIT_TARGET_1 = "HIT_TARGET_1"
    HIT_TARGET_2 = "HIT_TARGET_2" 
    HIT_TARGET_3 = "HIT_TARGET_3"
    HIT_STOP = "HIT_STOP"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class SignalSource(Enum):
    INDICATORS = "INDICATORS"
    PATTERN = "PATTERN"
    COMBINED = "COMBINED"
    MANUAL = "MANUAL"

@dataclass
class TradingSignal:
    """
    Modelo completo para sinais de trading com rastreamento de performance
    """
    # Identificação
    id: Optional[int] = None
    asset_symbol: str = "BTC"
    signal_type: SignalType = SignalType.BUY
    source: SignalSource = SignalSource.INDICATORS
    pattern_type: Optional[str] = None
    
    # Preços e Targets
    entry_price: float = 0.0
    current_price: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    target_3: float = 0.0
    stop_loss: float = 0.0
    
    # Status e Timing
    status: SignalStatus = SignalStatus.ACTIVE
    confidence: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    
    # Performance
    max_profit_pct: float = 0.0
    max_loss_pct: float = 0.0
    current_pnl_pct: float = 0.0
    final_pnl_pct: Optional[float] = None
    target_hit: Optional[int] = None  # 1, 2, 3 ou None
    
    # Metadata
    reasons: List[str] = None
    technical_indicators: Dict[str, Any] = None
    volume_confirmation: bool = False
    risk_reward_ratio: float = 0.0
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.technical_indicators is None:
            self.technical_indicators = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if self.expiry_time is None:
            # Default: sinal expira em 24 horas se não for ativado
            self.expiry_time = self.created_at + timedelta(hours=24)
    
    def update_current_price(self, new_price: float) -> bool:
        """
        Atualiza o preço atual e verifica se targets/stops foram atingidos
        Retorna True se o status mudou
        """
        if self.status != SignalStatus.ACTIVE:
            return False
            
        old_status = self.status
        self.current_price = new_price
        self.updated_at = datetime.now()
        
        # Calcula PnL atual
        if self.signal_type == SignalType.BUY:
            self.current_pnl_pct = ((new_price - self.entry_price) / self.entry_price) * 100
        else:
            self.current_pnl_pct = ((self.entry_price - new_price) / self.entry_price) * 100
        
        # Atualiza máximos
        if self.current_pnl_pct > self.max_profit_pct:
            self.max_profit_pct = self.current_pnl_pct
        if self.current_pnl_pct < self.max_loss_pct:
            self.max_loss_pct = self.current_pnl_pct
        
        # Verifica se stop loss foi atingido
        if self._check_stop_loss(new_price):
            self.status = SignalStatus.HIT_STOP
            self.closed_at = datetime.now()
            self.final_pnl_pct = self.current_pnl_pct
            logger.info(f"Signal {self.id} hit STOP LOSS at {new_price}")
            return True
        
        # Verifica targets (do maior para o menor para evitar pular targets)
        target_hit = self._check_targets(new_price)
        if target_hit:
            if target_hit == 3:
                self.status = SignalStatus.HIT_TARGET_3
            elif target_hit == 2:
                self.status = SignalStatus.HIT_TARGET_2
            elif target_hit == 1:
                self.status = SignalStatus.HIT_TARGET_1
            
            self.target_hit = target_hit
            self.closed_at = datetime.now()
            self.final_pnl_pct = self.current_pnl_pct
            logger.info(f"Signal {self.id} hit TARGET {target_hit} at {new_price}")
            return True
        
        # Verifica expiração
        if datetime.now() > self.expiry_time:
            self.status = SignalStatus.EXPIRED
            self.closed_at = datetime.now()
            self.final_pnl_pct = self.current_pnl_pct
            logger.info(f"Signal {self.id} EXPIRED")
            return True
        
        return old_status != self.status
    
    def _check_stop_loss(self, current_price: float) -> bool:
        """Verifica se o stop loss foi atingido"""
        if self.stop_loss <= 0:
            return False
            
        if self.signal_type == SignalType.BUY:
            return current_price <= self.stop_loss
        else:
            return current_price >= self.stop_loss
    
    def _check_targets(self, current_price: float) -> Optional[int]:
        """Verifica qual target foi atingido (retorna o maior target atingido)"""
        targets = [(3, self.target_3), (2, self.target_2), (1, self.target_1)]
        
        for target_num, target_price in targets:
            if target_price <= 0:
                continue
                
            if self.signal_type == SignalType.BUY:
                if current_price >= target_price:
                    return target_num
            else:
                if current_price <= target_price:
                    return target_num
        
        return None
    
    def is_active(self) -> bool:
        """Verifica se o sinal ainda está ativo"""
        return self.status == SignalStatus.ACTIVE
    
    def is_profitable(self) -> bool:
        """Verifica se o sinal foi lucrativo"""
        if self.final_pnl_pct is None:
            return self.current_pnl_pct > 0
        return self.final_pnl_pct > 0
    
    def get_duration_minutes(self) -> int:
        """Retorna duração do sinal em minutos"""
        end_time = self.closed_at or datetime.now()
        return int((end_time - self.created_at).total_seconds() / 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para serialização"""
        return {
            'id': self.id,
            'asset_symbol': self.asset_symbol,
            'signal_type': self.signal_type.value,
            'source': self.source.value,
            'pattern_type': self.pattern_type,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'target_1': self.target_1,
            'target_2': self.target_2,
            'target_3': self.target_3,
            'stop_loss': self.stop_loss,
            'status': self.status.value,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'expiry_time': self.expiry_time.isoformat() if self.expiry_time else None,
            'max_profit_pct': self.max_profit_pct,
            'max_loss_pct': self.max_loss_pct,
            'current_pnl_pct': self.current_pnl_pct,
            'final_pnl_pct': self.final_pnl_pct,
            'target_hit': self.target_hit,
            'reasons': self.reasons,
            'technical_indicators': self.technical_indicators,
            'volume_confirmation': self.volume_confirmation,
            'risk_reward_ratio': self.risk_reward_ratio,
            'duration_minutes': self.get_duration_minutes()
        }


class SignalManager:
    """
    Gerenciador de sinais de trading com persistência no banco de dados
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.active_signals: Dict[str, List[TradingSignal]] = {}
        self._init_database()
        self._load_active_signals()
    
    def _init_database(self):
        """Inicializa tabelas do banco de dados"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    pattern_type TEXT,
                    entry_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    target_1 REAL NOT NULL,
                    target_2 REAL NOT NULL,
                    target_3 REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT,
                    expiry_time TEXT NOT NULL,
                    max_profit_pct REAL DEFAULT 0.0,
                    max_loss_pct REAL DEFAULT 0.0,
                    current_pnl_pct REAL DEFAULT 0.0,
                    final_pnl_pct REAL,
                    target_hit INTEGER,
                    reasons TEXT,
                    technical_indicators TEXT,
                    volume_confirmation BOOLEAN DEFAULT FALSE,
                    risk_reward_ratio REAL DEFAULT 0.0
                )
            """)
            
            # Criar índices para performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_asset_status ON trading_signals(asset_symbol, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created_at ON trading_signals(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON trading_signals(status)")
            
            conn.commit()
    
    def _load_active_signals(self):
        """Carrega sinais ativos do banco para memória"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM trading_signals 
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
            """)
            
            for row in cursor.fetchall():
                signal = self._row_to_signal(row)
                asset_signals = self.active_signals.get(signal.asset_symbol, [])
                asset_signals.append(signal)
                self.active_signals[signal.asset_symbol] = asset_signals
        
        logger.info(f"Loaded {sum(len(signals) for signals in self.active_signals.values())} active signals")
    
    def _row_to_signal(self, row: sqlite3.Row) -> TradingSignal:
        """Converte linha do banco para objeto TradingSignal"""
        return TradingSignal(
            id=row['id'],
            asset_symbol=row['asset_symbol'],
            signal_type=SignalType(row['signal_type']),
            source=SignalSource(row['source']),
            pattern_type=row['pattern_type'],
            entry_price=row['entry_price'],
            current_price=row['current_price'],
            target_1=row['target_1'],
            target_2=row['target_2'],
            target_3=row['target_3'],
            stop_loss=row['stop_loss'],
            status=SignalStatus(row['status']),
            confidence=row['confidence'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            closed_at=datetime.fromisoformat(row['closed_at']) if row['closed_at'] else None,
            expiry_time=datetime.fromisoformat(row['expiry_time']),
            max_profit_pct=row['max_profit_pct'],
            max_loss_pct=row['max_loss_pct'],
            current_pnl_pct=row['current_pnl_pct'],
            final_pnl_pct=row['final_pnl_pct'],
            target_hit=row['target_hit'],
            reasons=json.loads(row['reasons']) if row['reasons'] else [],
            technical_indicators=json.loads(row['technical_indicators']) if row['technical_indicators'] else {},
            volume_confirmation=bool(row['volume_confirmation']),
            risk_reward_ratio=row['risk_reward_ratio']
        )
    
    def create_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """
        Cria um novo sinal, verificando duplicação
        """
        # Verificar duplicação
        if self._is_duplicate_signal(signal):
            logger.warning(f"Duplicate signal detected for {signal.asset_symbol}, skipping")
            return None
        
        # Verificar limite de sinais ativos
        active_count = len(self.get_active_signals(signal.asset_symbol))
        max_signals = 5  # Configurável
        
        if active_count >= max_signals:
            logger.warning(f"Maximum active signals ({max_signals}) reached for {signal.asset_symbol}")
            return None
        
        # Salvar no banco
        signal_id = self._save_signal(signal)
        if signal_id:
            signal.id = signal_id
            
            # Adicionar à memória
            asset_signals = self.active_signals.get(signal.asset_symbol, [])
            asset_signals.append(signal)
            self.active_signals[signal.asset_symbol] = asset_signals
            
            logger.info(f"Created new signal {signal_id} for {signal.asset_symbol}")
            return signal
        
        return None
    
    def _is_duplicate_signal(self, new_signal: TradingSignal, time_window_minutes: int = 30) -> bool:
        """
        Verifica se existe um sinal similar muito recente
        """
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        for existing_signal in self.get_active_signals(new_signal.asset_symbol):
            if (existing_signal.created_at >= cutoff_time and
                existing_signal.signal_type == new_signal.signal_type and
                existing_signal.source == new_signal.source and
                abs(existing_signal.entry_price - new_signal.entry_price) / existing_signal.entry_price < 0.02):  # 2% de diferença
                return True
        
        return False
    
    def _save_signal(self, signal: TradingSignal) -> Optional[int]:
        """Salva sinal no banco de dados"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO trading_signals (
                        asset_symbol, signal_type, source, pattern_type, entry_price, current_price,
                        target_1, target_2, target_3, stop_loss, status, confidence,
                        created_at, updated_at, expiry_time, max_profit_pct, max_loss_pct,
                        current_pnl_pct, reasons, technical_indicators, volume_confirmation,
                        risk_reward_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal.asset_symbol, signal.signal_type.value, signal.source.value,
                    signal.pattern_type, signal.entry_price, signal.current_price,
                    signal.target_1, signal.target_2, signal.target_3, signal.stop_loss,
                    signal.status.value, signal.confidence,
                    signal.created_at.isoformat(), signal.updated_at.isoformat(),
                    signal.expiry_time.isoformat(), signal.max_profit_pct, signal.max_loss_pct,
                    signal.current_pnl_pct, json.dumps(signal.reasons),
                    json.dumps(signal.technical_indicators), signal.volume_confirmation,
                    signal.risk_reward_ratio
                ))
                
                return cursor.lastrowid
        
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
            return None
    
    def update_signals_with_price(self, asset_symbol: str, current_price: float):
        """
        Atualiza todos os sinais ativos de um asset com o preço atual
        """
        active_signals = self.get_active_signals(asset_symbol)
        
        for signal in active_signals:
            status_changed = signal.update_current_price(current_price)
            
            if status_changed:
                # Atualizar no banco
                self._update_signal_in_db(signal)
                
                # Remover da lista de ativos se foi fechado
                if not signal.is_active():
                    self._remove_from_active(signal)
                    logger.info(f"Signal {signal.id} closed: {signal.status.value}")
            else:
                # Mesmo sem mudança de status, atualizar preço atual no banco
                self._update_signal_price_in_db(signal)
    
    def _update_signal_in_db(self, signal: TradingSignal):
        """Atualiza sinal completo no banco"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE trading_signals SET
                        current_price = ?, status = ?, updated_at = ?, closed_at = ?,
                        max_profit_pct = ?, max_loss_pct = ?, current_pnl_pct = ?,
                        final_pnl_pct = ?, target_hit = ?
                    WHERE id = ?
                """, (
                    signal.current_price, signal.status.value, signal.updated_at.isoformat(),
                    signal.closed_at.isoformat() if signal.closed_at else None,
                    signal.max_profit_pct, signal.max_loss_pct, signal.current_pnl_pct,
                    signal.final_pnl_pct, signal.target_hit, signal.id
                ))
        except Exception as e:
            logger.error(f"Error updating signal {signal.id}: {e}")
    
    def _update_signal_price_in_db(self, signal: TradingSignal):
        """Atualiza apenas preço e PnL no banco (operação mais leve)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE trading_signals SET
                        current_price = ?, updated_at = ?, current_pnl_pct = ?,
                        max_profit_pct = ?, max_loss_pct = ?
                    WHERE id = ?
                """, (
                    signal.current_price, signal.updated_at.isoformat(),
                    signal.current_pnl_pct, signal.max_profit_pct, signal.max_loss_pct,
                    signal.id
                ))
        except Exception as e:
            logger.error(f"Error updating signal price {signal.id}: {e}")
    
    def _remove_from_active(self, signal: TradingSignal):
        """Remove sinal da lista de ativos na memória"""
        if signal.asset_symbol in self.active_signals:
            self.active_signals[signal.asset_symbol] = [
                s for s in self.active_signals[signal.asset_symbol] if s.id != signal.id
            ]
    
    def get_active_signals(self, asset_symbol: str = None) -> List[TradingSignal]:
        """Retorna sinais ativos"""
        if asset_symbol:
            return self.active_signals.get(asset_symbol, [])
        
        all_signals = []
        for signals in self.active_signals.values():
            all_signals.extend(signals)
        return all_signals
    
    def get_recent_signals(self, asset_symbol: str = None, limit: int = 50) -> List[TradingSignal]:
        """Retorna sinais recentes (incluindo fechados)"""
        query = """
            SELECT * FROM trading_signals 
            WHERE created_at >= datetime('now', '-7 days')
        """
        params = []
        
        if asset_symbol:
            query += " AND asset_symbol = ?"
            params.append(asset_symbol)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        signals = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                
                for row in cursor.fetchall():
                    signals.append(self._row_to_signal(row))
        
        except Exception as e:
            logger.error(f"Error fetching recent signals: {e}")
        
        return signals
    
    def get_performance_stats(self, asset_symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """Calcula estatísticas de performance dos sinais"""
        query = """
            SELECT * FROM trading_signals 
            WHERE status != 'ACTIVE' AND created_at >= datetime('now', '-{} days')
        """.format(days)
        
        params = []
        if asset_symbol:
            query += " AND asset_symbol = ?"
            params.append(asset_symbol)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                
                closed_signals = [self._row_to_signal(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Error fetching performance stats: {e}")
            return {}
        
        if not closed_signals:
            return {
                'total_signals': 0,
                'success_rate': 0,
                'avg_profit': 0,
                'avg_loss': 0,
                'best_signal': 0,
                'worst_signal': 0
            }
        
        profitable_signals = [s for s in closed_signals if s.is_profitable()]
        
        return {
            'total_signals': len(closed_signals),
            'profitable_signals': len(profitable_signals),
            'success_rate': len(profitable_signals) / len(closed_signals) * 100,
            'avg_profit': sum(s.final_pnl_pct for s in profitable_signals) / len(profitable_signals) if profitable_signals else 0,
            'avg_loss': sum(s.final_pnl_pct for s in closed_signals if not s.is_profitable()) / (len(closed_signals) - len(profitable_signals)) if len(closed_signals) > len(profitable_signals) else 0,
            'best_signal': max(s.final_pnl_pct for s in closed_signals),
            'worst_signal': min(s.final_pnl_pct for s in closed_signals),
            'avg_duration_minutes': sum(s.get_duration_minutes() for s in closed_signals) / len(closed_signals),
            'target_1_hits': len([s for s in closed_signals if s.target_hit == 1]),
            'target_2_hits': len([s for s in closed_signals if s.target_hit == 2]),
            'target_3_hits': len([s for s in closed_signals if s.target_hit == 3]),
            'stop_hits': len([s for s in closed_signals if s.status == SignalStatus.HIT_STOP])
        }
    
    def cleanup_old_signals(self, days_to_keep: int = 30):
        """Remove sinais antigos do banco de dados"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM trading_signals 
                    WHERE status != 'ACTIVE' AND created_at < datetime('now', '-{} days')
                """.format(days_to_keep))
                
                deleted_count = cursor.rowcount
                logger.info(f"Cleaned up {deleted_count} old signals")
                return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up old signals: {e}")
            return 0
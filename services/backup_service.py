# services/backup_service.py - Sistema de backup automático

import os
import shutil
import sqlite3
import gzip
import json
import threading
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib
import zipfile

from utils.logging_config import logger
from config import app_config


class BackupService:
    """
    Serviço de backup automático para bancos de dados e configurações
    Suporta: backup completo, incremental, compressão, rotação automática
    """
    
    def __init__(self, backup_dir: str = None):
        self.backup_dir = Path(backup_dir or os.path.join(app_config.DATA_DIR, 'backups'))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações de backup
        self.config = {
            'auto_backup_enabled': True,
            'backup_schedule': '02:00',  # 2:00 AM
            'retention_days': 30,
            'max_backups': 50,
            'compression_enabled': True,
            'include_configs': True,
            'include_databases': True,
            'include_logs': False,
            'backup_types': ['daily', 'weekly', 'monthly'],
            'weekly_day': 'sunday',
            'monthly_day': 1,
            'incremental_enabled': True,
            'verify_backups': True
        }
        
        # Estado do serviço
        self.is_running = False
        self.last_backup_time = None
        self.backup_thread = None
        self.scheduler_thread = None
        
        # Estatísticas
        self.backup_stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'total_size_bytes': 0,
            'last_backup_duration': 0,
            'last_backup_status': 'never'
        }
        
        # Lock para operações thread-safe
        self.backup_lock = threading.Lock()
        
        self.load_config()
        self.init_backup_database()
    
    def load_config(self):
        """Carrega configuração de backup"""
        try:
            config_file = self.backup_dir / 'backup_config.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
                    logger.info("[BACKUP] Configuração carregada")
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao carregar configuração: {e}")
    
    def save_config(self):
        """Salva configuração de backup"""
        try:
            config_file = self.backup_dir / 'backup_config.json'
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("[BACKUP] Configuração salva")
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao salvar configuração: {e}")
    
    def init_backup_database(self):
        """Inicializa banco de dados de backup"""
        try:
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            # Tabela de metadados de backups
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_id TEXT UNIQUE NOT NULL,
                    backup_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    compressed BOOLEAN DEFAULT 0,
                    verification_status TEXT,
                    checksum TEXT,
                    included_databases TEXT,
                    included_configs TEXT,
                    duration_seconds REAL,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            ''')
            
            # Tabela de arquivos incluídos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    checksum TEXT,
                    last_modified TEXT,
                    FOREIGN KEY (backup_id) REFERENCES backup_history (backup_id)
                )
            ''')
            
            # Índices para performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backup_created_at ON backup_history(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backup_type ON backup_history(backup_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backup_files_backup_id ON backup_files(backup_id)')
            
            conn.commit()
            conn.close()
            
            logger.info("[BACKUP] Banco de metadados inicializado")
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao inicializar banco de metadados: {e}")
    
    def start_auto_backup(self):
        """Inicia serviço de backup automático"""
        if self.is_running:
            logger.warning("[BACKUP] Serviço já está em execução")
            return
        
        self.is_running = True
        
        # Configurar agendamento
        schedule.clear()
        
        if self.config['auto_backup_enabled']:
            schedule.every().day.at(self.config['backup_schedule']).do(self._scheduled_backup, 'daily')
            
            if 'weekly' in self.config['backup_types']:
                getattr(schedule.every(), self.config['weekly_day']).at(self.config['backup_schedule']).do(
                    self._scheduled_backup, 'weekly'
                )
            
            if 'monthly' in self.config['backup_types']:
                # Backup mensal no dia especificado
                schedule.every().month.do(self._scheduled_backup, 'monthly')
        
        # Thread para executar agendamentos
        self.scheduler_thread = threading.Thread(target=self._scheduler_worker, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("[BACKUP] Serviço de backup automático iniciado")
    
    def stop_auto_backup(self):
        """Para serviço de backup automático"""
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("[BACKUP] Serviço de backup automático parado")
    
    def _scheduler_worker(self):
        """Worker thread para executar agendamentos"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Verificar a cada minuto
            except Exception as e:
                logger.error(f"[BACKUP] Erro no scheduler: {e}")
                time.sleep(60)
    
    def _scheduled_backup(self, backup_type: str):
        """Executa backup agendado"""
        try:
            logger.info(f"[BACKUP] Iniciando backup agendado: {backup_type}")
            result = self.create_backup(backup_type=backup_type, auto_cleanup=True)
            
            if result['success']:
                logger.info(f"[BACKUP] Backup {backup_type} concluído: {result['backup_file']}")
            else:
                logger.error(f"[BACKUP] Falha no backup {backup_type}: {result['error']}")
                
        except Exception as e:
            logger.error(f"[BACKUP] Erro no backup agendado: {e}")
    
    def create_backup(self, 
                     backup_type: str = 'manual',
                     include_databases: bool = None,
                     include_configs: bool = None,
                     include_logs: bool = None,
                     auto_cleanup: bool = False) -> Dict[str, Any]:
        """
        Cria backup completo do sistema
        
        Args:
            backup_type: Tipo do backup (manual, daily, weekly, monthly)
            include_databases: Se deve incluir bancos de dados
            include_configs: Se deve incluir configurações
            include_logs: Se deve incluir logs
            auto_cleanup: Se deve fazer limpeza automática após backup
            
        Returns:
            Resultado da operação
        """
        with self.backup_lock:
            try:
                start_time = time.time()
                backup_id = self._generate_backup_id(backup_type)
                
                # Usar configurações padrão se não especificado
                if include_databases is None:
                    include_databases = self.config['include_databases']
                if include_configs is None:
                    include_configs = self.config['include_configs']
                if include_logs is None:
                    include_logs = self.config['include_logs']
                
                logger.info(f"[BACKUP] Criando backup {backup_id}")
                
                # Criar estrutura temporária
                temp_dir = self.backup_dir / f"temp_{backup_id}"
                temp_dir.mkdir(exist_ok=True)
                
                try:
                    # Coletar arquivos para backup
                    files_to_backup = []
                    included_items = []
                    
                    if include_databases:
                        db_files = self._collect_database_files()
                        files_to_backup.extend(db_files)
                        included_items.extend([f['source'] for f in db_files])
                    
                    if include_configs:
                        config_files = self._collect_config_files()
                        files_to_backup.extend(config_files)
                        included_items.extend([f['source'] for f in config_files])
                    
                    if include_logs:
                        log_files = self._collect_log_files()
                        files_to_backup.extend(log_files)
                        included_items.extend([f['source'] for f in log_files])
                    
                    if not files_to_backup:
                        return {
                            'success': False,
                            'error': 'Nenhum arquivo encontrado para backup'
                        }
                    
                    # Copiar arquivos para diretório temporário
                    total_size = 0
                    file_info = []
                    
                    for file_item in files_to_backup:
                        source_path = Path(file_item['source'])
                        dest_path = temp_dir / file_item['relative_path']
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copiar arquivo
                        if source_path.exists():
                            shutil.copy2(source_path, dest_path)
                            
                            # Calcular checksum e tamanho
                            file_size = dest_path.stat().st_size
                            checksum = self._calculate_checksum(dest_path)
                            
                            total_size += file_size
                            file_info.append({
                                'path': file_item['relative_path'],
                                'size': file_size,
                                'checksum': checksum,
                                'modified': datetime.fromtimestamp(source_path.stat().st_mtime).isoformat()
                            })
                    
                    # Criar metadados do backup
                    metadata = {
                        'backup_id': backup_id,
                        'backup_type': backup_type,
                        'created_at': datetime.now().isoformat(),
                        'included_databases': include_databases,
                        'included_configs': include_configs,
                        'included_logs': include_logs,
                        'total_files': len(file_info),
                        'total_size_bytes': total_size,
                        'files': file_info
                    }
                    
                    # Salvar metadados
                    metadata_file = temp_dir / 'backup_metadata.json'
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    # Criar arquivo de backup
                    if self.config['compression_enabled']:
                        backup_file = self.backup_dir / f"{backup_id}.zip"
                        self._create_compressed_backup(temp_dir, backup_file)
                    else:
                        backup_file = self.backup_dir / f"{backup_id}.tar"
                        self._create_tar_backup(temp_dir, backup_file)
                    
                    # Calcular checksum do backup
                    backup_checksum = self._calculate_checksum(backup_file)
                    backup_size = backup_file.stat().st_size
                    
                    # Verificar backup se habilitado
                    verification_status = 'not_verified'
                    if self.config['verify_backups']:
                        verification_status = self._verify_backup(backup_file)
                    
                    # Registrar no banco de metadados
                    duration = time.time() - start_time
                    self._record_backup(
                        backup_id=backup_id,
                        backup_type=backup_type,
                        file_path=str(backup_file),
                        file_size=backup_size,
                        compressed=self.config['compression_enabled'],
                        verification_status=verification_status,
                        checksum=backup_checksum,
                        included_databases=json.dumps(included_items) if include_databases else None,
                        included_configs='yes' if include_configs else 'no',
                        duration=duration,
                        status='success'
                    )
                    
                    # Registrar arquivos individuais
                    self._record_backup_files(backup_id, file_info)
                    
                    # Atualizar estatísticas
                    self._update_stats(success=True, size=backup_size, duration=duration)
                    
                    # Limpeza automática se solicitada
                    if auto_cleanup:
                        self.cleanup_old_backups()
                    
                    logger.info(f"[BACKUP] Backup concluído: {backup_file} ({self._format_size(backup_size)})")
                    
                    return {
                        'success': True,
                        'backup_id': backup_id,
                        'backup_file': str(backup_file),
                        'size_bytes': backup_size,
                        'duration_seconds': duration,
                        'files_included': len(file_info),
                        'verification_status': verification_status
                    }
                    
                finally:
                    # Limpar diretório temporário
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                
            except Exception as e:
                logger.error(f"[BACKUP] Erro ao criar backup: {e}")
                
                # Registrar falha
                try:
                    self._record_backup(
                        backup_id=backup_id,
                        backup_type=backup_type,
                        file_path='',
                        file_size=0,
                        compressed=False,
                        verification_status='failed',
                        checksum='',
                        included_databases='',
                        included_configs='',
                        duration=time.time() - start_time,
                        status='failed',
                        error_message=str(e)
                    )
                    self._update_stats(success=False)
                except:
                    pass
                
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def _collect_database_files(self) -> List[Dict]:
        """Coleta arquivos de banco de dados para backup"""
        files = []
        
        # Bitcoin stream database
        if hasattr(app_config, 'BITCOIN_STREAM_DB') and os.path.exists(app_config.BITCOIN_STREAM_DB):
            files.append({
                'source': app_config.BITCOIN_STREAM_DB,
                'relative_path': 'databases/bitcoin_stream.db'
            })
        
        # Trading analyzer database
        if hasattr(app_config, 'TRADING_ANALYZER_DB') and os.path.exists(app_config.TRADING_ANALYZER_DB):
            files.append({
                'source': app_config.TRADING_ANALYZER_DB,
                'relative_path': 'databases/trading_analyzer.db'
            })
        
        # Dynamic config database
        dynamic_config_db = os.path.join(app_config.DATA_DIR, 'dynamic_config.db')
        if os.path.exists(dynamic_config_db):
            files.append({
                'source': dynamic_config_db,
                'relative_path': 'databases/dynamic_config.db'
            })
        
        # Settings database
        settings_db = os.path.join(app_config.DATA_DIR, 'settings.db')
        if os.path.exists(settings_db):
            files.append({
                'source': settings_db,
                'relative_path': 'databases/settings.db'
            })
        
        # Backup metadata database
        backup_db = self.backup_dir / 'backup_metadata.db'
        if backup_db.exists():
            files.append({
                'source': str(backup_db),
                'relative_path': 'databases/backup_metadata.db'
            })
        
        return files
    
    def _collect_config_files(self) -> List[Dict]:
        """Coleta arquivos de configuração para backup"""
        files = []
        
        # Arquivo de configuração principal
        if hasattr(app_config, 'CONFIG_FILE') and os.path.exists(app_config.CONFIG_FILE):
            files.append({
                'source': app_config.CONFIG_FILE,
                'relative_path': 'configs/app_config.py'
            })
        
        # Configurações de notificação
        notification_config = os.path.join(app_config.DATA_DIR, 'notification_config.json')
        if os.path.exists(notification_config):
            files.append({
                'source': notification_config,
                'relative_path': 'configs/notification_config.json'
            })
        
        # Configurações de backup
        backup_config = self.backup_dir / 'backup_config.json'
        if backup_config.exists():
            files.append({
                'source': str(backup_config),
                'relative_path': 'configs/backup_config.json'
            })
        
        return files
    
    def _collect_log_files(self) -> List[Dict]:
        """Coleta arquivos de log para backup (últimos 7 dias)"""
        files = []
        
        try:
            log_dir = Path(app_config.DATA_DIR) / 'logs'
            if log_dir.exists():
                cutoff_date = datetime.now() - timedelta(days=7)
                
                for log_file in log_dir.glob('*.log'):
                    if log_file.is_file():
                        mod_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if mod_time > cutoff_date:
                            files.append({
                                'source': str(log_file),
                                'relative_path': f'logs/{log_file.name}'
                            })
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao coletar logs: {e}")
        
        return files
    
    def _create_compressed_backup(self, source_dir: Path, output_file: Path):
        """Cria backup comprimido em ZIP"""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
    
    def _create_tar_backup(self, source_dir: Path, output_file: Path):
        """Cria backup em formato TAR"""
        import tarfile
        
        with tarfile.open(output_file, 'w') as tar:
            tar.add(source_dir, arcname='.')
    
    def _verify_backup(self, backup_file: Path) -> str:
        """Verifica integridade do backup"""
        try:
            if backup_file.suffix == '.zip':
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    # Testar integridade do ZIP
                    bad_files = zipf.testzip()
                    if bad_files:
                        return f'corrupted ({bad_files})'
                    
                    # Verificar se contém metadados
                    if 'backup_metadata.json' in zipf.namelist():
                        return 'verified'
                    else:
                        return 'incomplete'
            else:
                # Para TAR, verificar se pode ser aberto
                import tarfile
                with tarfile.open(backup_file, 'r'):
                    return 'verified'
                    
        except Exception as e:
            logger.error(f"[BACKUP] Erro na verificação: {e}")
            return f'error ({str(e)[:50]})'
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcula checksum SHA256 do arquivo"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _generate_backup_id(self, backup_type: str) -> str:
        """Gera ID único para o backup"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"backup_{backup_type}_{timestamp}"
    
    def _record_backup(self, **kwargs):
        """Registra backup no banco de metadados"""
        try:
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO backup_history 
                (backup_id, backup_type, created_at, file_path, file_size_bytes,
                 compressed, verification_status, checksum, included_databases,
                 included_configs, duration_seconds, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                kwargs['backup_id'],
                kwargs['backup_type'],
                kwargs.get('created_at', datetime.now().isoformat()),
                kwargs['file_path'],
                kwargs['file_size'],
                kwargs['compressed'],
                kwargs['verification_status'],
                kwargs['checksum'],
                kwargs['included_databases'],
                kwargs['included_configs'],
                kwargs['duration'],
                kwargs['status'],
                kwargs.get('error_message')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao registrar backup: {e}")
    
    def _record_backup_files(self, backup_id: str, file_info: List[Dict]):
        """Registra arquivos individuais do backup"""
        try:
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            for file_data in file_info:
                cursor.execute('''
                    INSERT INTO backup_files 
                    (backup_id, file_path, file_size_bytes, checksum, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    backup_id,
                    file_data['path'],
                    file_data['size'],
                    file_data['checksum'],
                    file_data['modified']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao registrar arquivos: {e}")
    
    def _update_stats(self, success: bool, size: int = 0, duration: float = 0):
        """Atualiza estatísticas de backup"""
        self.backup_stats['total_backups'] += 1
        
        if success:
            self.backup_stats['successful_backups'] += 1
            self.backup_stats['total_size_bytes'] += size
            self.backup_stats['last_backup_duration'] = duration
            self.backup_stats['last_backup_status'] = 'success'
            self.last_backup_time = datetime.now()
        else:
            self.backup_stats['failed_backups'] += 1
            self.backup_stats['last_backup_status'] = 'failed'
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Remove backups antigos baseado nas regras de retenção"""
        try:
            deleted_count = 0
            deleted_size = 0
            
            # Obter lista de backups
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            # Backups mais antigos que o período de retenção
            cutoff_date = datetime.now() - timedelta(days=self.config['retention_days'])
            
            cursor.execute('''
                SELECT backup_id, file_path, file_size_bytes 
                FROM backup_history 
                WHERE created_at < ? AND status = 'success'
                ORDER BY created_at ASC
            ''', (cutoff_date.isoformat(),))
            
            old_backups = cursor.fetchall()
            
            # Aplicar limite máximo de backups também
            cursor.execute('''
                SELECT backup_id, file_path, file_size_bytes 
                FROM backup_history 
                WHERE status = 'success'
                ORDER BY created_at DESC
            ''')
            
            all_backups = cursor.fetchall()
            
            # Se temos mais backups que o limite máximo, remover os mais antigos
            if len(all_backups) > self.config['max_backups']:
                excess_backups = all_backups[self.config['max_backups']:]
                old_backups.extend(excess_backups)
            
            # Remover duplicatas
            old_backups = list(set(old_backups))
            
            # Deletar backups antigos
            for backup_id, file_path, file_size in old_backups:
                try:
                    backup_file = Path(file_path)
                    if backup_file.exists():
                        backup_file.unlink()
                        deleted_size += file_size or 0
                        deleted_count += 1
                    
                    # Remover do banco de dados
                    cursor.execute('DELETE FROM backup_files WHERE backup_id = ?', (backup_id,))
                    cursor.execute('DELETE FROM backup_history WHERE backup_id = ?', (backup_id,))
                    
                except Exception as e:
                    logger.error(f"[BACKUP] Erro ao deletar backup {backup_id}: {e}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"[BACKUP] Limpeza concluída: {deleted_count} backups removidos ({self._format_size(deleted_size)})")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'deleted_size_bytes': deleted_size,
                'space_freed': self._format_size(deleted_size)
            }
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro na limpeza: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def restore_backup(self, backup_id: str, restore_path: str = None) -> Dict[str, Any]:
        """
        Restaura backup específico
        
        Args:
            backup_id: ID do backup para restaurar
            restore_path: Caminho onde restaurar (padrão: temporário)
            
        Returns:
            Resultado da operação
        """
        try:
            # Buscar informações do backup
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT file_path, compressed, verification_status 
                FROM backup_history 
                WHERE backup_id = ? AND status = 'success'
            ''', (backup_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return {
                    'success': False,
                    'error': f'Backup {backup_id} não encontrado ou falhou'
                }
            
            file_path, compressed, verification_status = result
            backup_file = Path(file_path)
            
            if not backup_file.exists():
                return {
                    'success': False,
                    'error': f'Arquivo de backup não encontrado: {file_path}'
                }
            
            # Verificar integridade se não foi verificado antes
            if verification_status != 'verified':
                current_verification = self._verify_backup(backup_file)
                if current_verification not in ['verified', 'incomplete']:
                    return {
                        'success': False,
                        'error': f'Backup corrompido: {current_verification}'
                    }
            
            # Definir caminho de restauração
            if not restore_path:
                restore_path = self.backup_dir / f"restore_{backup_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            restore_dir = Path(restore_path)
            restore_dir.mkdir(parents=True, exist_ok=True)
            
            # Extrair backup
            if compressed or backup_file.suffix == '.zip':
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    zipf.extractall(restore_dir)
            else:
                import tarfile
                with tarfile.open(backup_file, 'r') as tar:
                    tar.extractall(restore_dir)
            
            # Verificar se metadados foram extraídos
            metadata_file = restore_dir / 'backup_metadata.json'
            metadata = {}
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            
            logger.info(f"[BACKUP] Backup {backup_id} restaurado em: {restore_dir}")
            
            return {
                'success': True,
                'backup_id': backup_id,
                'restore_path': str(restore_dir),
                'metadata': metadata,
                'files_restored': len(list(restore_dir.rglob('*')))
            }
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro na restauração: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_backups(self, backup_type: str = None, limit: int = 50) -> List[Dict]:
        """Lista backups disponíveis"""
        try:
            backup_db = self.backup_dir / 'backup_metadata.db'
            conn = sqlite3.connect(str(backup_db))
            cursor = conn.cursor()
            
            query = '''
                SELECT backup_id, backup_type, created_at, file_path, file_size_bytes,
                       compressed, verification_status, duration_seconds, status
                FROM backup_history
            '''
            params = []
            
            if backup_type:
                query += ' WHERE backup_type = ?'
                params.append(backup_type)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            backups = []
            for row in results:
                backup_info = {
                    'backup_id': row[0],
                    'backup_type': row[1],
                    'created_at': row[2],
                    'file_path': row[3],
                    'size_bytes': row[4],
                    'size_formatted': self._format_size(row[4]),
                    'compressed': bool(row[5]),
                    'verification_status': row[6],
                    'duration_seconds': row[7],
                    'status': row[8],
                    'file_exists': Path(row[3]).exists() if row[3] else False
                }
                backups.append(backup_info)
            
            return backups
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao listar backups: {e}")
            return []
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de backup"""
        try:
            # Estatísticas básicas
            stats = self.backup_stats.copy()
            
            # Adicionar informações calculadas
            stats['success_rate'] = (
                (stats['successful_backups'] / stats['total_backups'] * 100)
                if stats['total_backups'] > 0 else 0
            )
            
            stats['total_size_formatted'] = self._format_size(stats['total_size_bytes'])
            stats['last_backup_time'] = self.last_backup_time.isoformat() if self.last_backup_time else None
            stats['service_running'] = self.is_running
            stats['backup_directory'] = str(self.backup_dir)
            
            # Estatísticas do banco de dados
            backup_db = self.backup_dir / 'backup_metadata.db'
            if backup_db.exists():
                conn = sqlite3.connect(str(backup_db))
                cursor = conn.cursor()
                
                # Total de backups por tipo
                cursor.execute('''
                    SELECT backup_type, COUNT(*) 
                    FROM backup_history 
                    WHERE status = 'success'
                    GROUP BY backup_type
                ''')
                stats['backups_by_type'] = dict(cursor.fetchall())
                
                # Backup mais recente
                cursor.execute('''
                    SELECT backup_id, created_at, backup_type 
                    FROM backup_history 
                    WHERE status = 'success'
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''')
                recent = cursor.fetchone()
                if recent:
                    stats['most_recent_backup'] = {
                        'backup_id': recent[0],
                        'created_at': recent[1],
                        'backup_type': recent[2]
                    }
                
                conn.close()
            
            return stats
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao obter estatísticas: {e}")
            return self.backup_stats.copy()
    
    def _format_size(self, size_bytes: int) -> str:
        """Formata tamanho em bytes para formato legível"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def update_config(self, new_config: Dict) -> bool:
        """Atualiza configuração do serviço"""
        try:
            old_schedule = self.config.get('backup_schedule')
            old_enabled = self.config.get('auto_backup_enabled')
            
            self.config.update(new_config)
            self.save_config()
            
            # Reiniciar se configurações de agendamento mudaram
            if (self.is_running and 
                (new_config.get('backup_schedule') != old_schedule or
                 new_config.get('auto_backup_enabled') != old_enabled)):
                
                self.stop_auto_backup()
                if new_config.get('auto_backup_enabled', True):
                    self.start_auto_backup()
            
            logger.info("[BACKUP] Configuração atualizada")
            return True
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao atualizar configuração: {e}")
            return False


# ==================== GLOBAL INSTANCE ====================

# Instância global do serviço de backup
backup_service = BackupService()

def start_backup_service():
    """Inicia serviço de backup automático"""
    backup_service.start_auto_backup()

def stop_backup_service():
    """Para serviço de backup automático"""
    backup_service.stop_auto_backup()

def create_manual_backup(backup_type: str = 'manual') -> Dict[str, Any]:
    """Cria backup manual"""
    return backup_service.create_backup(backup_type=backup_type)

def get_backup_service() -> BackupService:
    """Retorna instância do serviço de backup"""
    return backup_service
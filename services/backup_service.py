# services/backup_service.py - Sistema de backup automático e manual

import os
import json
import shutil
import sqlite3
import zipfile
import hashlib
import schedule
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from utils.logging_config import logger

class BackupService:
    """
    Serviço de backup que oferece:
    - Backup automático agendado
    - Backup manual sob demanda
    - Compressão e verificação de integridade
    - Rotação automática de backups antigos
    - Restauração de backups
    """
    
    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = backup_dir or os.path.join('data', 'backups')
        self.metadata_db = os.path.join(self.backup_dir, 'backup_metadata.db')
        
        # Configurações padrão
        self.config = {
            'auto_backup_enabled': True,
            'backup_schedule': '02:00',  # 2:00 AM
            'retention_days': 30,
            'max_backups': 50,
            'compression_enabled': True,
            'verify_backups': True,
            'backup_types': ['daily', 'weekly', 'monthly']
        }
        
        # Estado do serviço
        self.backup_thread = None
        self.is_running = False
        self.last_backup_time = None
        
        # Caminhos dos dados para backup
        self.data_paths = {
            'databases': 'data',
            'configs': 'data',
            'logs': 'data/logs'
        }
        
        self.setup_backup_directory()
        self.setup_metadata_db()
    
    def setup_backup_directory(self):
        """Configura diretório de backups"""
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            logger.info(f"[BACKUP] Diretório de backup: {self.backup_dir}")
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao criar diretório: {e}")
    
    def setup_metadata_db(self):
        """Configura banco de metadados dos backups"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Tabela de metadados dos backups
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_id TEXT UNIQUE NOT NULL,
                    backup_type TEXT NOT NULL,
                    backup_file TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    verified BOOLEAN DEFAULT 0,
                    file_exists BOOLEAN DEFAULT 1,
                    includes_databases BOOLEAN DEFAULT 1,
                    includes_configs BOOLEAN DEFAULT 1,
                    includes_logs BOOLEAN DEFAULT 0,
                    compression_ratio REAL,
                    notes TEXT
                )
            ''')
            
            # Tabela de histórico de operações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    backup_id TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT,
                    details TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("[BACKUP] Banco de metadados inicializado")
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao configurar metadados: {e}")
    
    def create_backup(self, backup_type: str = 'manual', include_databases: bool = True,
                     include_configs: bool = True, include_logs: bool = False,
                     auto_cleanup: bool = False) -> Dict[str, Any]:
        """
        Cria um backup do sistema
        
        Args:
            backup_type: Tipo do backup (manual, daily, weekly, monthly)
            include_databases: Incluir arquivos de banco de dados
            include_configs: Incluir arquivos de configuração
            include_logs: Incluir arquivos de log
            auto_cleanup: Executar limpeza automática após backup
            
        Returns:
            Resultado da operação
        """
        operation_id = self._start_operation('CREATE_BACKUP', backup_type)
        
        try:
            # Gerar ID único para o backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_id = f"backup_{backup_type}_{timestamp}"
            backup_filename = f"{backup_id}.zip"
            backup_filepath = os.path.join(self.backup_dir, backup_filename)
            
            logger.info(f"[BACKUP] Iniciando backup: {backup_id}")
            
            # Coletar arquivos para backup
            files_to_backup = []
            
            if include_databases:
                db_files = self._collect_database_files()
                files_to_backup.extend(db_files)
            
            if include_configs:
                config_files = self._collect_config_files()
                files_to_backup.extend(config_files)
            
            if include_logs:
                log_files = self._collect_log_files()
                files_to_backup.extend(log_files)
            
            if not files_to_backup:
                error = "Nenhum arquivo encontrado para backup"
                self._complete_operation(operation_id, 'FAILED', error)
                return {'success': False, 'error': error}
            
            # Criar arquivo zip
            total_size_before = sum(os.path.getsize(f['source']) for f in files_to_backup if os.path.exists(f['source']))
            
            with zipfile.ZipFile(backup_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in files_to_backup:
                    source_path = file_info['source']
                    archive_path = file_info['relative_path']
                    
                    if os.path.exists(source_path):
                        zipf.write(source_path, archive_path)
                        logger.debug(f"[BACKUP] Adicionado: {archive_path}")
            
            # Calcular informações do backup
            backup_size = os.path.getsize(backup_filepath)
            compression_ratio = backup_size / total_size_before if total_size_before > 0 else 0
            checksum = self._calculate_checksum(backup_filepath)
            
            # Verificar integridade se habilitado
            verified = False
            if self.config.get('verify_backups', True):
                verified = self._verify_backup(backup_filepath)
            
            # Salvar metadados
            self._save_backup_metadata(
                backup_id, backup_type, backup_filename, backup_size,
                checksum, verified, include_databases, include_configs,
                include_logs, compression_ratio
            )
            
            # Executar limpeza se solicitado
            if auto_cleanup:
                self._cleanup_old_backups()
            
            self.last_backup_time = datetime.now()
            
            result = {
                'success': True,
                'backup_id': backup_id,
                'backup_file': backup_filepath,
                'size_bytes': backup_size,
                'compression_ratio': compression_ratio,
                'verified': verified,
                'files_included': len(files_to_backup),
                'created_at': datetime.now().isoformat()
            }
            
            self._complete_operation(operation_id, 'SUCCESS', json.dumps(result))
            logger.info(f"[BACKUP] Backup criado com sucesso: {backup_id} ({backup_size} bytes)")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[BACKUP] Erro ao criar backup: {e}")
            self._complete_operation(operation_id, 'FAILED', error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'backup_type': backup_type
            }
    
    def _collect_database_files(self) -> List[Dict[str, str]]:
        """Coleta arquivos de banco de dados"""
        db_files = []
        data_dir = self.data_paths['databases']
        
        if os.path.exists(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    if file.endswith('.db') or file.endswith('.sqlite'):
                        full_path = os.path.join(root, file)
                        relative_path = os.path.join('databases', os.path.relpath(full_path, data_dir))
                        
                        db_files.append({
                            'source': full_path,
                            'relative_path': relative_path
                        })
        
        logger.debug(f"[BACKUP] Encontrados {len(db_files)} arquivos de banco")
        return db_files
    
    def _collect_config_files(self) -> List[Dict[str, str]]:
        """Coleta arquivos de configuração"""
        config_files = []
        
        # Arquivos de configuração específicos
        config_patterns = [
            'config.py',
            'config.json',
            '*.conf',
            'dynamic_config.db',
            'notifications.db'
        ]
        
        data_dir = self.data_paths['configs']
        
        if os.path.exists(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    # Verificar se é arquivo de configuração
                    if (file.endswith('.json') or file.endswith('.conf') or 
                        file.endswith('.yaml') or file.endswith('.yml') or
                        'config' in file.lower()):
                        
                        full_path = os.path.join(root, file)
                        relative_path = os.path.join('configs', os.path.relpath(full_path, data_dir))
                        
                        config_files.append({
                            'source': full_path,
                            'relative_path': relative_path
                        })
        
        logger.debug(f"[BACKUP] Encontrados {len(config_files)} arquivos de configuração")
        return config_files
    
    def _collect_log_files(self) -> List[Dict[str, str]]:
        """Coleta arquivos de log"""
        log_files = []
        logs_dir = self.data_paths['logs']
        
        if os.path.exists(logs_dir):
            # Apenas logs dos últimos 7 dias
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for root, dirs, files in os.walk(logs_dir):
                for file in files:
                    if file.endswith('.log'):
                        full_path = os.path.join(root, file)
                        
                        # Verificar data do arquivo
                        file_time = datetime.fromtimestamp(os.path.getmtime(full_path))
                        if file_time >= cutoff_date:
                            relative_path = os.path.join('logs', os.path.relpath(full_path, logs_dir))
                            
                            log_files.append({
                                'source': full_path,
                                'relative_path': relative_path
                            })
        
        logger.debug(f"[BACKUP] Encontrados {len(log_files)} arquivos de log")
        return log_files
    
    def _calculate_checksum(self, filepath: str) -> str:
        """Calcula checksum MD5 do arquivo"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao calcular checksum: {e}")
            return ""
    
    def _verify_backup(self, filepath: str) -> bool:
        """Verifica integridade do backup"""
        try:
            with zipfile.ZipFile(filepath, 'r') as zipf:
                # Testar se o arquivo pode ser aberto e lido
                bad_files = zipf.testzip()
                if bad_files:
                    logger.error(f"[BACKUP] Arquivos corrompidos no backup: {bad_files}")
                    return False
                
                # Verificar se contém arquivos
                if len(zipf.namelist()) == 0:
                    logger.error("[BACKUP] Backup vazio")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"[BACKUP] Erro na verificação: {e}")
            return False
    
    def _save_backup_metadata(self, backup_id: str, backup_type: str, filename: str,
                             size_bytes: int, checksum: str, verified: bool,
                             includes_databases: bool, includes_configs: bool,
                             includes_logs: bool, compression_ratio: float):
        """Salva metadados do backup"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO backup_metadata 
                (backup_id, backup_type, backup_file, created_at, size_bytes, checksum, 
                 verified, includes_databases, includes_configs, includes_logs, compression_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backup_id, backup_type, filename, datetime.now().isoformat(),
                size_bytes, checksum, verified, includes_databases,
                includes_configs, includes_logs, compression_ratio
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao salvar metadados: {e}")
    
    def list_backups(self, backup_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Lista backups disponíveis"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            if backup_type:
                cursor.execute('''
                    SELECT backup_id, backup_type, backup_file, created_at, size_bytes,
                           verified, file_exists, includes_databases, includes_configs, includes_logs
                    FROM backup_metadata
                    WHERE backup_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (backup_type, limit))
            else:
                cursor.execute('''
                    SELECT backup_id, backup_type, backup_file, created_at, size_bytes,
                           verified, file_exists, includes_databases, includes_configs, includes_logs
                    FROM backup_metadata
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
            
            backups = []
            for row in cursor.fetchall():
                backup_path = os.path.join(self.backup_dir, row[2])
                file_exists = os.path.exists(backup_path)
                
                # Atualizar status no banco se necessário
                if file_exists != bool(row[6]):
                    cursor.execute('UPDATE backup_metadata SET file_exists = ? WHERE backup_id = ?',
                                 (file_exists, row[0]))
                
                backups.append({
                    'backup_id': row[0],
                    'backup_type': row[1],
                    'backup_file': row[2],
                    'full_path': backup_path,
                    'created_at': row[3],
                    'size_bytes': row[4],
                    'verified': bool(row[5]),
                    'file_exists': file_exists,
                    'includes_databases': bool(row[7]),
                    'includes_configs': bool(row[8]),
                    'includes_logs': bool(row[9])
                })
            
            conn.commit()
            conn.close()
            
            return backups
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao listar backups: {e}")
            return []
    
    def restore_backup(self, backup_id: str, restore_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Restaura um backup
        
        Args:
            backup_id: ID do backup para restaurar
            restore_path: Caminho para restaurar (padrão: diretório original)
            
        Returns:
            Resultado da operação
        """
        operation_id = self._start_operation('RESTORE_BACKUP', backup_id)
        
        try:
            # Buscar metadados do backup
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT backup_file, size_bytes, verified, includes_databases, includes_configs, includes_logs
                FROM backup_metadata
                WHERE backup_id = ?
            ''', (backup_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                error = f"Backup não encontrado: {backup_id}"
                self._complete_operation(operation_id, 'FAILED', error)
                return {'success': False, 'error': error}
            
            backup_file, size_bytes, verified, inc_db, inc_config, inc_logs = result
            backup_path = os.path.join(self.backup_dir, backup_file)
            
            if not os.path.exists(backup_path):
                error = f"Arquivo de backup não encontrado: {backup_path}"
                self._complete_operation(operation_id, 'FAILED', error)
                return {'success': False, 'error': error}
            
            # Determinar diretório de restauração
            if not restore_path:
                restore_path = 'data_restored'
            
            os.makedirs(restore_path, exist_ok=True)
            
            # Extrair backup
            extracted_files = []
            
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                for file_info in zipf.infolist():
                    extracted_path = os.path.join(restore_path, file_info.filename)
                    
                    # Criar diretório se necessário
                    os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
                    
                    # Extrair arquivo
                    with zipf.open(file_info) as source, open(extracted_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    
                    extracted_files.append(extracted_path)
            
            result = {
                'success': True,
                'backup_id': backup_id,
                'restore_path': restore_path,
                'files_restored': len(extracted_files),
                'total_size': size_bytes,
                'verified': bool(verified),
                'restored_at': datetime.now().isoformat()
            }
            
            self._complete_operation(operation_id, 'SUCCESS', json.dumps(result))
            logger.info(f"[BACKUP] Backup restaurado: {backup_id} -> {restore_path}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[BACKUP] Erro ao restaurar backup: {e}")
            self._complete_operation(operation_id, 'FAILED', error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'backup_id': backup_id
            }
    
    def _cleanup_old_backups(self):
        """Remove backups antigos baseado na política de retenção"""
        try:
            retention_days = self.config.get('retention_days', 30)
            max_backups = self.config.get('max_backups', 50)
            
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
            
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Buscar backups para remoção
            cursor.execute('''
                SELECT backup_id, backup_file 
                FROM backup_metadata 
                WHERE created_at < ? OR backup_id IN (
                    SELECT backup_id FROM backup_metadata 
                    ORDER BY created_at DESC 
                    LIMIT -1 OFFSET ?
                )
            ''', (cutoff_date, max_backups))
            
            backups_to_remove = cursor.fetchall()
            removed_count = 0
            
            for backup_id, backup_file in backups_to_remove:
                backup_path = os.path.join(self.backup_dir, backup_file)
                
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    # Remover do banco
                    cursor.execute('DELETE FROM backup_metadata WHERE backup_id = ?', (backup_id,))
                    removed_count += 1
                    
                except Exception as e:
                    logger.error(f"[BACKUP] Erro ao remover {backup_id}: {e}")
            
            conn.commit()
            conn.close()
            
            if removed_count > 0:
                logger.info(f"[BACKUP] Removidos {removed_count} backups antigos")
                
        except Exception as e:
            logger.error(f"[BACKUP] Erro na limpeza: {e}")
    
    def start_auto_backup(self):
        """Inicia backup automático agendado"""
        if self.is_running:
            logger.warning("[BACKUP] Backup automático já está rodando")
            return
        
        try:
            # Configurar agendamento
            schedule_time = self.config.get('backup_schedule', '02:00')
            schedule.every().day.at(schedule_time).do(self._run_scheduled_backup)
            
            # Thread para executar agendamentos
            def backup_worker():
                while self.is_running:
                    schedule.run_pending()
                    time.sleep(60)  # Verificar a cada minuto
            
            self.is_running = True
            self.backup_thread = threading.Thread(target=backup_worker, daemon=True)
            self.backup_thread.start()
            
            logger.info(f"[BACKUP] Backup automático iniciado (agendado para {schedule_time})")
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao iniciar backup automático: {e}")
            self.is_running = False
    
    def stop_auto_backup(self):
        """Para backup automático"""
        self.is_running = False
        schedule.clear()
        
        if self.backup_thread and self.backup_thread.is_alive():
            self.backup_thread.join(timeout=5)
        
        logger.info("[BACKUP] Backup automático parado")
    
    def _run_scheduled_backup(self):
        """Executa backup agendado"""
        try:
            # Determinar tipo de backup baseado na data
            now = datetime.now()
            
            if now.day == 1:  # Primeiro dia do mês
                backup_type = 'monthly'
            elif now.weekday() == 6:  # Domingo
                backup_type = 'weekly'
            else:
                backup_type = 'daily'
            
            # Executar backup
            result = self.create_backup(
                backup_type=backup_type,
                include_databases=True,
                include_configs=True,
                include_logs=False,
                auto_cleanup=True
            )
            
            if result['success']:
                logger.info(f"[BACKUP] Backup agendado criado: {backup_type}")
            else:
                logger.error(f"[BACKUP] Falha no backup agendado: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"[BACKUP] Erro no backup agendado: {e}")
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas dos backups"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Total de backups
            cursor.execute('SELECT COUNT(*) FROM backup_metadata')
            total_backups = cursor.fetchone()[0]
            
            # Backups por tipo
            cursor.execute('''
                SELECT backup_type, COUNT(*) 
                FROM backup_metadata 
                GROUP BY backup_type
            ''')
            by_type = dict(cursor.fetchall())
            
            # Tamanho total
            cursor.execute('SELECT SUM(size_bytes) FROM backup_metadata WHERE file_exists = 1')
            total_size = cursor.fetchone()[0] or 0
            
            # Último backup
            cursor.execute('''
                SELECT backup_id, backup_type, created_at 
                FROM backup_metadata 
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            last_backup = cursor.fetchone()
            
            # Backups verificados
            cursor.execute('SELECT COUNT(*) FROM backup_metadata WHERE verified = 1')
            verified_backups = cursor.fetchone()[0]
            
            # Operações recentes
            cursor.execute('''
                SELECT COUNT(*) 
                FROM backup_operations 
                WHERE status = "SUCCESS" AND started_at > datetime("now", "-24 hours")
            ''')
            successful_last_24h = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'service_running': self.is_running,
                'total_backups': total_backups,
                'by_type': by_type,
                'total_size_bytes': total_size,
                'last_backup': {
                    'backup_id': last_backup[0] if last_backup else None,
                    'backup_type': last_backup[1] if last_backup else None,
                    'created_at': last_backup[2] if last_backup else None
                } if last_backup else None,
                'verified_backups': verified_backups,
                'success_rate': verified_backups / total_backups if total_backups > 0 else 0,
                'successful_last_24h': successful_last_24h,
                'next_scheduled': self.config.get('backup_schedule', '02:00'),
                'retention_days': self.config.get('retention_days', 30),
                'auto_backup_enabled': self.config.get('auto_backup_enabled', True)
            }
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao obter estatísticas: {e}")
            return {
                'service_running': self.is_running,
                'total_backups': 0,
                'by_type': {},
                'total_size_bytes': 0,
                'last_backup': None,
                'verified_backups': 0,
                'success_rate': 0,
                'successful_last_24h': 0,
                'next_scheduled': '02:00',
                'retention_days': 30,
                'auto_backup_enabled': True
            }
    
    def _start_operation(self, operation_type: str, details: str = None) -> int:
        """Inicia registro de operação"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO backup_operations 
                (operation_type, backup_id, status, started_at, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (operation_type, details, 'RUNNING', datetime.now().isoformat(), details))
            
            operation_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return operation_id
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao iniciar operação: {e}")
            return 0
    
    def _complete_operation(self, operation_id: int, status: str, details: str = None):
        """Completa registro de operação"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE backup_operations 
                SET status = ?, completed_at = ?, error_message = ?
                WHERE id = ?
            ''', (status, datetime.now().isoformat(), details if status == 'FAILED' else None, operation_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"[BACKUP] Erro ao completar operação: {e}")


# ==================== INSTÂNCIA GLOBAL ====================

# Instância global do serviço de backup
backup_service = BackupService()

def create_system_backup(backup_type: str = 'manual', **kwargs) -> Dict[str, Any]:
    """Função auxiliar para criar backup do sistema"""
    return backup_service.create_backup(backup_type=backup_type, **kwargs)

def get_backup_status() -> Dict[str, Any]:
    """Função auxiliar para obter status dos backups"""
    return backup_service.get_backup_stats()

def start_backup_service():
    """Inicia serviço de backup automático"""
    backup_service.start_auto_backup()

def stop_backup_service():
    """Para serviço de backup automático"""
    backup_service.stop_auto_backup()
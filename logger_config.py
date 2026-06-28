# -*- coding: utf-8 -*-
"""
Logger Config - Detaylı Logging Sistemi
File rotation, performance tracking
"""
import logging
import logging.handlers
import os
from datetime import datetime
import time

# ============================================================================
# LOGGER SETUP
# ============================================================================

class LoggerSetup:
    """Logger Yapılandırması"""
    
    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = log_dir
        self.create_log_directory()
    
    def create_log_directory(self):
        """Log Klasörü Oluştur"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def setup_logger(self, name: str = 'bist_bot', 
                    level: int = logging.INFO) -> logging.Logger:
        """Logger'ı Kur"""
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        if logger.hasHandlers():
            return logger
        
        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 2. File Handler - Tüm Loglar
        log_file = os.path.join(self.log_dir, 'bist_bot.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=10
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 3. Error File Handler - Sadece Hatalar
        error_log_file = os.path.join(self.log_dir, 'errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
        # 4. Performance File Handler
        perf_log_file = os.path.join(self.log_dir, 'performance.log')
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5
        )
        perf_formatter = logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(perf_formatter)
        
        # Performance logger
        perf_logger = logging.getLogger(f'{name}.performance')
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        
        return logger

# ============================================================================
# PERFORMANCE TRACKER
# ============================================================================

class PerformanceTracker:
    """Performans Takip Sistemi"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.perf_logger = logging.getLogger(f'{logger.name}.performance')
        self.metrics = {}
    
    def start_timer(self, operation_name: str) -> float:
        """Zamanlayıcı Başlat"""
        start_time = time.time()
        self.metrics[operation_name] = {'start': start_time}
        return start_time
    
    def end_timer(self, operation_name: str) -> float:
        """Zamanlayıcı Bitir"""
        if operation_name not in self.metrics:
            return 0
        
        end_time = time.time()
        start_time = self.metrics[operation_name]['start']
        duration = end_time - start_time
        
        self.metrics[operation_name]['duration'] = duration
        self.metrics[operation_name]['end'] = end_time
        
        self.perf_logger.info(
            f"⏱️ {operation_name}: {duration:.2f}s"
        )
        
        return duration
    
    def get_metric(self, operation_name: str) -> dict:
        """Metrik Al"""
        return self.metrics.get(operation_name, {})
    
    def log_metrics_summary(self):
        """Metrik Özeti Yazdır"""
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 PERFORMANCE METRICS SUMMARY")
        self.logger.info("="*60)
        
        for op_name, metrics in self.metrics.items():
            if 'duration' in metrics:
                self.logger.info(f"  {op_name}: {metrics['duration']:.2f}s")
        
        self.logger.info("="*60 + "\n")

# ============================================================================
# STRUCTURED LOGGING
# ============================================================================

class StructuredLogger:
    """Yapılandırılmış Logging"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_event(self, event_type: str, event_data: dict):
        """Olay Günlüğü"""
        message = f"[{event_type}] " + " | ".join(
            f"{k}={v}" for k, v in event_data.items()
        )
        self.logger.info(message)
    
    def log_trade_signal(self, kod: str, sinyal: str, veri: dict):
        """Ticaret Sinyali Günlüğü"""
        message = (
            f"[TRADE_SIGNAL] "
            f"kod={kod} | "
            f"sinyal={sinyal} | "
            f"skor={veri.get('skor', 0)} | "
            f"fiyat={veri.get('fiyat', 0)} | "
            f"rr={veri.get('rr', 0)}"
        )
        self.logger.info(message)
    
    def log_scan_result(self, toplam: int, gecen: int, oran: float):
        """Tarama Sonucu Günlüğü"""
        message = (
            f"[SCAN_RESULT] "
            f"toplam={toplam} | "
            f"gecen={gecen} | "
            f"oran={oran:.1f}%"
        )
        self.logger.info(message)
    
    def log_error_detail(self, error_type: str, error_msg: str, 
                        context: dict = None):
        """Detaylı Hata Günlüğü"""
        message = (
            f"[ERROR_DETAIL] "
            f"type={error_type} | "
            f"message={error_msg}"
        )
        if context:
            context_str = " | ".join(
                f"{k}={v}" for k, v in context.items()
            )
            message += f" | {context_str}"
        
        self.logger.error(message)

# ============================================================================
# GLOBAL LOGGER SETUP
# ============================================================================

def get_logger(name: str = 'bist_bot') -> logging.Logger:
    """Global Logger Al"""
    logger_setup = LoggerSetup(log_dir='logs')
    return logger_setup.setup_logger(name)

def get_performance_tracker(logger: logging.Logger) -> PerformanceTracker:
    """Performance Tracker Al"""
    return PerformanceTracker(logger)

def get_structured_logger(logger: logging.Logger) -> StructuredLogger:
    """Structured Logger Al"""
    return StructuredLogger(logger)

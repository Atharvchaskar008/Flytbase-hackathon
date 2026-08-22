"""
Phase 19 - Backend Hardening ⭐⭐⭐⭐⭐

This is where robustness comes from.

Components:
1. Validation (Video format, corrupted files, empty uploads, FPS/resolution validation)
2. Exception Handling (If one stage fails, status = Failed, log error, return reason)
3. Logging (Every stage logs progress)
4. Database Transactions (Begin → Insert → Commit/Rollback)
5. Performance (Stream processing, never load entire video, proper indexes)

The server should never crash.
"""

import logging
import traceback
import functools
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List, Union
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import psutil
import gc

# Configure comprehensive logging
def setup_comprehensive_logging():
    """Setup comprehensive logging for backend hardening"""
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s:%(lineno)-4d | %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for detailed logs
    file_handler = logging.FileHandler('logs/trace_backend.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler('logs/trace_errors.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    return logging.getLogger('backend_hardening')

logger = setup_comprehensive_logging()


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ProcessingError(Exception):
    """Custom processing error"""
    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR", stage: str = "unknown"):
        self.message = message
        self.error_code = error_code
        self.stage = stage
        super().__init__(message)


class DatabaseError(Exception):
    """Custom database error"""
    def __init__(self, message: str, error_code: str = "DATABASE_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def robust_error_handler(
    operation_name: str,
    log_errors: bool = True,
    reraise: bool = False,
    default_return: Any = None
) -> Callable:
    """
    Decorator for robust error handling
    
    Args:
        operation_name: Name of operation for logging
        log_errors: Whether to log errors
        reraise: Whether to reraise the exception
        default_return: Default return value on error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                logger.info(f"🚀 Starting operation: {operation_name}")
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                logger.info(f"✅ Operation completed: {operation_name} ({duration:.2f}s)")
                
                return result
                
            except ValidationError as e:
                if log_errors:
                    logger.error(f"❌ Validation error in {operation_name}: {e.message}")
                if reraise:
                    raise
                return {'error': e.message, 'error_code': e.error_code, 'status': 'validation_failed'}
                
            except ProcessingError as e:
                if log_errors:
                    logger.error(f"❌ Processing error in {operation_name} (stage: {e.stage}): {e.message}")
                if reraise:
                    raise
                return {'error': e.message, 'error_code': e.error_code, 'stage': e.stage, 'status': 'processing_failed'}
                
            except DatabaseError as e:
                if log_errors:
                    logger.error(f"❌ Database error in {operation_name}: {e.message}")
                if reraise:
                    raise
                return {'error': e.message, 'error_code': e.error_code, 'status': 'database_failed'}
                
            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"Unexpected error in {operation_name} after {duration:.2f}s: {str(e)}"
                
                if log_errors:
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())
                
                if reraise:
                    raise
                
                return default_return or {
                    'error': error_msg,
                    'error_code': 'UNEXPECTED_ERROR',
                    'status': 'failed',
                    'traceback': traceback.format_exc() if log_errors else None
                }
        
        return wrapper
    return decorator


class DatabaseTransactionManager:
    """
    Manages database transactions with proper rollback
    
    Usage:
        with DatabaseTransactionManager(db) as tx:
            tx.add(model)
            tx.commit()  # Auto-commits on success, rolls back on exception
    """
    
    def __init__(self, db: Session, description: str = "Database Transaction"):
        self.db = db
        self.description = description
        self.committed = False
        
    def __enter__(self):
        logger.debug(f"🔄 Starting transaction: {self.description}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, rollback
            logger.error(f"❌ Transaction failed, rolling back: {self.description}")
            logger.error(f"Exception: {exc_type.__name__}: {exc_val}")
            self.rollback()
            return False  # Re-raise the exception
        
        elif not self.committed:
            # No exception but not explicitly committed, commit now
            self.commit()
        
        logger.debug(f"✅ Transaction completed: {self.description}")
        return True
    
    def add(self, instance):
        """Add instance to session"""
        self.db.add(instance)
        
    def flush(self):
        """Flush changes without committing"""
        self.db.flush()
        
    def commit(self):
        """Commit transaction"""
        try:
            self.db.commit()
            self.committed = True
            logger.debug(f"✅ Transaction committed: {self.description}")
        except SQLAlchemyError as e:
            logger.error(f"❌ Commit failed for {self.description}: {e}")
            self.rollback()
            raise DatabaseError(f"Transaction commit failed: {str(e)}", "COMMIT_FAILED")
    
    def rollback(self):
        """Rollback transaction"""
        try:
            self.db.rollback()
            logger.debug(f"🔄 Transaction rolled back: {self.description}")
        except SQLAlchemyError as e:
            logger.error(f"❌ Rollback failed for {self.description}: {e}")


class PerformanceMonitor:
    """
    Monitors performance metrics and resource usage
    """
    
    def __init__(self):
        self.metrics = {}
        
    def start_monitoring(self, operation_name: str) -> Dict[str, Any]:
        """Start monitoring an operation"""
        
        start_metrics = {
            'operation': operation_name,
            'start_time': time.time(),
            'start_memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'start_cpu_percent': psutil.Process().cpu_percent()
        }
        
        self.metrics[operation_name] = start_metrics
        logger.debug(f"📊 Starting performance monitoring: {operation_name}")
        
        return start_metrics
    
    def stop_monitoring(self, operation_name: str) -> Dict[str, Any]:
        """Stop monitoring and return metrics"""
        
        if operation_name not in self.metrics:
            logger.warning(f"No monitoring started for operation: {operation_name}")
            return {}
        
        start_metrics = self.metrics[operation_name]
        
        end_metrics = {
            'operation': operation_name,
            'duration_seconds': time.time() - start_metrics['start_time'],
            'end_memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'end_cpu_percent': psutil.Process().cpu_percent(),
            'memory_delta_mb': 0,
            'peak_memory_usage': 'N/A'
        }
        
        end_metrics['memory_delta_mb'] = end_metrics['end_memory_mb'] - start_metrics['start_memory_mb']
        
        # Log performance metrics
        if end_metrics['duration_seconds'] > 10:
            logger.warning(f"⚠️  Slow operation detected: {operation_name} took {end_metrics['duration_seconds']:.2f}s")
        
        if end_metrics['memory_delta_mb'] > 100:
            logger.warning(f"⚠️  High memory usage: {operation_name} used {end_metrics['memory_delta_mb']:.2f}MB")
        
        logger.info(f"📊 Performance metrics for {operation_name}: {end_metrics['duration_seconds']:.2f}s, {end_metrics['memory_delta_mb']:.2f}MB")
        
        # Cleanup
        del self.metrics[operation_name]
        
        return end_metrics


class StreamingVideoProcessor:
    """
    Processes videos in streaming mode to avoid loading entire video into memory
    
    This ensures optimal performance and prevents out-of-memory errors.
    """
    
    def __init__(self, chunk_size: int = 30):
        """
        Initialize streaming processor
        
        Args:
            chunk_size: Number of frames to process at once
        """
        self.chunk_size = chunk_size
        self.performance_monitor = PerformanceMonitor()
        
    @robust_error_handler("streaming_video_process", log_errors=True)
    def process_video_stream(
        self, 
        video_path: str, 
        processor_func: Callable,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Process video in streaming chunks
        
        Args:
            video_path: Path to video file
            processor_func: Function to process each frame chunk
            progress_callback: Optional callback for progress updates
            
        Returns:
            Processing results
        """
        import cv2
        
        self.performance_monitor.start_monitoring("video_streaming")
        
        try:
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ProcessingError(f"Cannot open video: {video_path}", "VIDEO_OPEN_FAILED", "video_loading")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"📹 Starting streaming processing: {total_frames} frames at {fps} FPS")
            
            # Process in chunks
            processed_frames = 0
            chunk_buffer = []
            results = {'chunks_processed': 0, 'total_frames_processed': 0, 'errors': []}
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                chunk_buffer.append((processed_frames, frame))
                
                # Process chunk when buffer is full
                if len(chunk_buffer) >= self.chunk_size:
                    try:
                        chunk_result = processor_func(chunk_buffer)
                        results['chunks_processed'] += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(processed_frames, total_frames)
                        
                    except Exception as e:
                        error_info = f"Chunk processing failed at frame {processed_frames}: {str(e)}"
                        results['errors'].append(error_info)
                        logger.error(error_info)
                    
                    finally:
                        # Clear buffer to free memory
                        chunk_buffer.clear()
                        gc.collect()  # Force garbage collection
                
                processed_frames += 1
                
                # Memory check
                if processed_frames % 100 == 0:
                    memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
                    if memory_usage > 2000:  # 2GB threshold
                        logger.warning(f"⚠️  High memory usage during streaming: {memory_usage:.2f}MB")
                        gc.collect()
            
            # Process remaining frames in buffer
            if chunk_buffer:
                try:
                    chunk_result = processor_func(chunk_buffer)
                    results['chunks_processed'] += 1
                except Exception as e:
                    error_info = f"Final chunk processing failed: {str(e)}"
                    results['errors'].append(error_info)
                    logger.error(error_info)
            
            results['total_frames_processed'] = processed_frames
            
            # Cleanup
            cap.release()
            
            # Performance metrics
            performance_metrics = self.performance_monitor.stop_monitoring("video_streaming")
            results['performance'] = performance_metrics
            
            logger.info(f"✅ Streaming processing completed: {processed_frames} frames in {results['chunks_processed']} chunks")
            
            return results
            
        except Exception as e:
            if 'cap' in locals():
                cap.release()
            raise ProcessingError(f"Streaming processing failed: {str(e)}", "STREAMING_FAILED", "video_processing")


class DatabaseIndexManager:
    """
    Manages database indexes for optimal query performance
    """
    
    def __init__(self, db: Session):
        self.db = db
        
    def create_performance_indexes(self) -> Dict[str, bool]:
        """
        Create indexes for optimal search performance
        
        Returns:
            Results of index creation
        """
        logger.info("🔧 Creating performance indexes...")
        
        indexes = {
            'events_timestamp_idx': 'CREATE INDEX IF NOT EXISTS events_timestamp_idx ON events (timestamp);',
            'events_track_id_idx': 'CREATE INDEX IF NOT EXISTS events_track_id_idx ON events (track_id);',
            'events_video_id_idx': 'CREATE INDEX IF NOT EXISTS events_video_id_idx ON events (video_id);',
            'events_type_idx': 'CREATE INDEX IF NOT EXISTS events_type_idx ON events (event_type);',
            'tracks_video_id_idx': 'CREATE INDEX IF NOT EXISTS tracks_video_id_idx ON tracks (video_id);',
            'tracks_first_seen_idx': 'CREATE INDEX IF NOT EXISTS tracks_first_seen_idx ON tracks (first_seen);',
            'track_history_track_id_idx': 'CREATE INDEX IF NOT EXISTS track_history_track_id_idx ON track_history (track_id);',
            'track_history_frame_idx': 'CREATE INDEX IF NOT EXISTS track_history_frame_idx ON track_history (frame_number);',
            'videos_status_idx': 'CREATE INDEX IF NOT EXISTS videos_status_idx ON videos (status);',
            'videos_created_at_idx': 'CREATE INDEX IF NOT EXISTS videos_created_at_idx ON videos (created_at);',
        }
        
        results = {}
        
        for index_name, sql in indexes.items():
            try:
                self.db.execute(text(sql))
                self.db.commit()
                results[index_name] = True
                logger.info(f"✅ Created index: {index_name}")
            except Exception as e:
                results[index_name] = False
                logger.error(f"❌ Failed to create index {index_name}: {e}")
        
        return results
    
    def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """
        Analyze query performance using EXPLAIN
        
        Args:
            query: SQL query to analyze
            
        Returns:
            Query performance analysis
        """
        try:
            explain_query = f"EXPLAIN ANALYZE {query}"
            result = self.db.execute(text(explain_query))
            execution_plan = result.fetchall()
            
            analysis = {
                'query': query,
                'execution_plan': [row[0] for row in execution_plan],
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {'error': str(e)}


class BackendHardeningService:
    """
    Main service that coordinates all hardening components
    """
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.streaming_processor = StreamingVideoProcessor()
        
    @robust_error_handler("backend_initialization", log_errors=True)
    def initialize_hardened_backend(self, db: Session) -> Dict[str, Any]:
        """
        Initialize all backend hardening components
        
        Args:
            db: Database session
            
        Returns:
            Initialization results
        """
        logger.info("🛡️ Initializing hardened backend...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'components_initialized': [],
            'errors': [],
            'status': 'success'
        }
        
        try:
            # Initialize database indexes
            index_manager = DatabaseIndexManager(db)
            index_results = index_manager.create_performance_indexes()
            results['database_indexes'] = index_results
            results['components_initialized'].append('database_indexes')
            
            # Setup logging
            setup_comprehensive_logging()
            results['components_initialized'].append('comprehensive_logging')
            
            # Initialize performance monitoring
            self.performance_monitor.start_monitoring('backend_initialization')
            results['components_initialized'].append('performance_monitoring')
            
            logger.info("✅ Backend hardening initialization completed")
            
        except Exception as e:
            error_msg = f"Backend hardening initialization failed: {str(e)}"
            results['errors'].append(error_msg)
            results['status'] = 'partial_failure'
            logger.error(error_msg)
        
        return results
    
    @contextmanager
    def hardened_operation(self, operation_name: str, db: Session):
        """
        Context manager for hardened operations
        
        Usage:
            with hardening_service.hardened_operation('video_processing', db) as ctx:
                # Your operation here
                ctx.add(model)
                ctx.commit()
        """
        with DatabaseTransactionManager(db, operation_name) as tx:
            self.performance_monitor.start_monitoring(operation_name)
            
            try:
                yield tx
            finally:
                self.performance_monitor.stop_monitoring(operation_name)


# Global hardening service instance
hardening_service = BackendHardeningService()


def harden_api_endpoint(endpoint_name: str):
    """
    Decorator to harden API endpoints
    
    Usage:
        @harden_api_endpoint("upload_video")
        def upload_video_endpoint(...):
            ...
    """
    return robust_error_handler(
        endpoint_name,
        log_errors=True,
        reraise=False,
        default_return={'status': 'error', 'message': 'Internal server error'}
    )
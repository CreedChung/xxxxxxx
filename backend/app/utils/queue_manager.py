"""队列管理器 - 处理API限流和顺序执行"""
import asyncio
import uuid
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class QueueTask:
    """队列任务"""
    id: str
    name: str
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 20  # 秒
    result: Any = None
    error: str = None
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class QueueManager:
    """队列管理器"""
    
    def __init__(self):
        self.tasks: Dict[str, QueueTask] = {}
        self.running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """启动队列处理器"""
        if not self.running:
            self.running = True
            self._processing_task = asyncio.create_task(self._process_queue())
            logger.info("队列管理器已启动")
    
    async def stop(self):
        """停止队列处理器"""
        self.running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("队列管理器已停止")
    
    def add_task(
        self, 
        name: str, 
        func: Callable, 
        *args, 
        max_retries: int = 3, 
        retry_delay: int = 20,
        **kwargs
    ) -> str:
        """添加任务到队列"""
        task_id = str(uuid.uuid4())
        task = QueueTask(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        
        self.tasks[task_id] = task
        asyncio.create_task(self._queue.put(task))
        
        logger.info(f"任务已添加: {name} (ID: {task_id})")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            'id': task.id,
            'name': task.name,
            'status': task.status.value,
            'retry_count': task.retry_count,
            'max_retries': task.max_retries,
            'progress': self._calculate_progress(task),
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'error': task.error
        }
    
    async def get_all_tasks(self) -> List[Dict]:
        """获取所有任务状态"""
        return [await self.get_task_status(task_id) for task_id in self.tasks.keys()]
    
    def _calculate_progress(self, task: QueueTask) -> float:
        """计算任务进度"""
        if task.status == TaskStatus.COMPLETED:
            return 100.0
        elif task.status == TaskStatus.FAILED:
            return 0.0
        elif task.status == TaskStatus.RETRYING:
            return 50.0 + (task.retry_count / task.max_retries) * 30.0
        elif task.status == TaskStatus.RUNNING:
            return 50.0
        elif task.status == TaskStatus.PENDING:
            return 0.0
        return 0.0
    
    async def _process_queue(self):
        """处理队列中的任务"""
        while self.running:
            try:
                # 获取任务
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                
                # 处理任务
                await self._execute_task(task)
                
                # 标记任务完成
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"队列处理错误: {e}")
    
    async def _execute_task(self, task: QueueTask):
        """执行任务"""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            logger.info(f"开始执行任务: {task.name} (ID: {task.id})")
            
            # 执行任务
            if asyncio.iscoroutinefunction(task.func):
                task.result = await task.func(*task.args, **task.kwargs)
            else:
                task.result = task.func(*task.args, **task.kwargs)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"任务完成: {task.name} (ID: {task.id})")
            
        except Exception as e:
            error_msg = str(e)
            task.error = error_msg
            task.retry_count += 1
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                logger.warning(f"任务失败，准备重试: {task.name} (ID: {task.id}, 尝试 {task.retry_count}/{task.max_retries})")
                
                # 等待重试延迟
                await asyncio.sleep(task.retry_delay)
                
                # 重新添加到队列
                await self._queue.put(task)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                logger.error(f"任务最终失败: {task.name} (ID: {task.id}, 错误: {error_msg})")

# 全局队列管理器实例
queue_manager = QueueManager()
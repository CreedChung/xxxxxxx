"""队列状态查询API路由"""
from fastapi import APIRouter, HTTPException
from ..utils.queue_manager import queue_manager
import json

router = APIRouter(prefix="/api/queue", tags=["队列管理"])


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """获取特定任务的状态"""
    try:
        status = await queue_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="任务不存在")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.get("/status")
async def get_all_tasks_status():
    """获取所有任务状态"""
    try:
        tasks = await queue_manager.get_all_tasks()
        return {"tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.post("/start")
async def start_queue():
    """启动队列管理器"""
    try:
        await queue_manager.start()
        return {"message": "队列管理器已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动队列管理器失败: {str(e)}")


@router.post("/stop")
async def stop_queue():
    """停止队列管理器"""
    try:
        await queue_manager.stop()
        return {"message": "队列管理器已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止队列管理器失败: {str(e)}")
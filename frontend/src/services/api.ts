/**
 * API服务
 */
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 调整为60秒
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API请求错误:', error);
    return Promise.reject(error);
  }
);

export interface ConfigData {
  api_key: string;
  base_url?: string;
  model_name: string;
}

export interface FileUploadResponse {
  success: boolean;
  message: string;
  file_content?: string;
  old_outline?: string;
}

export interface AnalysisRequest {
  file_content: string;
  analysis_type: 'overview' | 'requirements';
}

export interface OutlineRequest {
  overview: string;
  requirements: string;
  uploaded_expand?: boolean;
  old_outline?: string;
  old_document?: string;
}

export interface ContentGenerationRequest {
  outline: { outline: any[] };
  project_overview: string;
}

export interface ChapterContentRequest {
  chapter: any;
  parent_chapters?: any[];
  sibling_chapters?: any[];
  project_overview: string;
}

export interface TaskStatus {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'retrying';
  retry_count: number;
  max_retries: number;
  progress: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface QueueStatus {
  task_id: string;
  status: TaskStatus;
  callback?: (result: any) => void;
  error_callback?: (error: string) => void;
}

// 配置相关API
export const configApi = {
  // 保存配置
  saveConfig: (config: ConfigData) =>
    api.post('/api/config/save', config),

  // 加载配置
  loadConfig: () =>
    api.get('/api/config/load'),

  // 获取可用模型
  getModels: (config: ConfigData) =>
    api.post('/api/config/models', config),
};

// 文档相关API
export const documentApi = {
  // 上传文件
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },


  // 流式分析文档
  analyzeDocumentStream: (data: AnalysisRequest) =>
    fetch(`${API_BASE_URL}/api/document/analyze-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 导出Word文档
  exportWord: (data: any) =>
    fetch(`${API_BASE_URL}/api/document/export-word`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),
};

// 目录相关API
export const outlineApi = {
  // 生成目录
  generateOutline: (data: OutlineRequest) =>
    api.post('/api/outline/generate', data),

  // 流式生成目录
  generateOutlineStream: (data: OutlineRequest) =>
    fetch(`${API_BASE_URL}/api/outline/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

};

// 内容相关API
export const contentApi = {
  // 生成单章节内容
  generateChapterContent: (data: ChapterContentRequest) =>
    api.post('/api/content/generate-chapter', data),

  // 流式生成单章节内容
  generateChapterContentStream: (data: ChapterContentRequest) =>
    fetch(`${API_BASE_URL}/api/content/generate-chapter-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),
};

// 方案扩写相关API
export const expandApi = {
  // 上传方案扩写文件
  uploadExpandFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/expand/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 文件上传专用超时设置：5分钟
    });
  },
};

// 队列管理类
class QueueManager {
  private queues: Map<string, QueueStatus> = new Map();
  private statusPollers: Map<string, NodeJS.Timeout> = new Map();

  // 添加任务到队列
  addTask(
    taskName: string,
    apiCall: () => Promise<any>,
    callback?: (result: any) => void,
    error_callback?: (error: string) => void
  ): string {
    const taskId = this.generateTaskId();

    const queueStatus: QueueStatus = {
      task_id: taskId,
      status: {
        id: taskId,
        name: taskName,
        status: 'pending',
        retry_count: 0,
        max_retries: 3,
        progress: 0,
        created_at: new Date().toISOString(),
      },
      callback,
      error_callback,
    };

    this.queues.set(taskId, queueStatus);

    // 开始执行任务
    this.executeTask(taskId, apiCall);

    return taskId;
  }

  // 生成任务ID
  private generateTaskId(): string {
    return 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }

  // 执行任务
  private async executeTask(taskId: string, apiCall: () => Promise<any>) {
    const queueStatus = this.queues.get(taskId);
    if (!queueStatus) return;

    try {
      // 更新状态为运行中
      this.updateTaskStatus(taskId, 'running');

      // 执行API调用
      const result = await apiCall();

      // 更新状态为完成
      this.updateTaskStatus(taskId, 'completed');

      // 执行回调
      if (queueStatus.callback) {
        queueStatus.callback(result);
      }

      // 清理轮询
      this.stopStatusPolling(taskId);

    } catch (error) {
      console.error(`任务执行失败: ${taskId}`, error);

      // 检查是否是限流错误
      const isRateLimit = this.isRateLimitError(error);
      const currentRetry = queueStatus.status.retry_count;
      const maxRetries = queueStatus.status.max_retries;

      if (isRateLimit && currentRetry < maxRetries) {
        // 重试限流错误
        this.updateTaskStatus(taskId, 'retrying');

        // 计算重试延迟（20秒后重试，最多3次）
        const retryDelay = 20000; // 20秒

        setTimeout(() => {
          this.updateTaskRetry(taskId);
          this.executeTask(taskId, apiCall);
        }, retryDelay);

      } else {
        // 最终失败
        this.updateTaskStatus(taskId, 'failed');

        // 执行错误回调
        if (queueStatus.error_callback) {
          queueStatus.error_callback(error instanceof Error ? error.message : String(error));
        }

        // 清理轮询
        this.stopStatusPolling(taskId);
      }
    }
  }

  // 检查是否为限流错误
  private isRateLimitError(error: any): boolean {
    if (error.response) {
      const status = error.response.status;
      const message = error.response.data?.message || '';
      return status === 429 || message.includes('限流') || message.includes('rate limit');
    }
    return false;
  }

  // 更新任务状态
  private updateTaskStatus(taskId: string, status: TaskStatus['status']) {
    const queueStatus = this.queues.get(taskId);
    if (queueStatus) {
      queueStatus.status.status = status;
      if (status === 'running') {
        queueStatus.status.started_at = new Date().toISOString();
      } else if (status === 'completed' || status === 'failed') {
        queueStatus.status.completed_at = new Date().toISOString();
        queueStatus.status.progress = status === 'completed' ? 100 : 0;
      }
    }
  }

  // 更新重试次数
  private updateTaskRetry(taskId: string) {
    const queueStatus = this.queues.get(taskId);
    if (queueStatus) {
      queueStatus.status.retry_count += 1;
    }
  }

  // 开始状态轮询
  startStatusPolling(taskId: string) {
    if (this.statusPollers.has(taskId)) {
      return; // 已经在轮询
    }

    const poller = setInterval(async () => {
      try {
        const response = await api.get(`/api/queue/status/${taskId}`);
        const status = response.data;

        const queueStatus = this.queues.get(taskId);
        if (queueStatus) {
          queueStatus.status = { ...queueStatus.status, ...status };

          // 如果任务完成或失败，停止轮询
          if (status.status === 'completed' || status.status === 'failed') {
            this.stopStatusPolling(taskId);
          }
        }
      } catch (error) {
        console.error(`获取任务状态失败: ${taskId}`, error);
      }
    }, 2000); // 每2秒查询一次

    this.statusPollers.set(taskId, poller);
  }

  // 停止状态轮询
  private stopStatusPolling(taskId: string) {
    const poller = this.statusPollers.get(taskId);
    if (poller) {
      clearInterval(poller);
      this.statusPollers.delete(taskId);
    }
  }

  // 获取任务状态
  getTaskStatus(taskId: string): QueueStatus | undefined {
    return this.queues.get(taskId);
  }

  // 获取所有任务状态
  getAllTasks(): QueueStatus[] {
    return Array.from(this.queues.values());
  }

  // 清理已完成的任务
  cleanupCompletedTasks() {
    for (const [taskId, queueStatus] of Array.from(this.queues.entries())) {
      if (queueStatus.status.status === 'completed' || queueStatus.status.status === 'failed') {
        this.stopStatusPolling(taskId);
        this.queues.delete(taskId);
      }
    }
  }
}

// 创建全局队列管理器实例
export const queueManager = new QueueManager();

// 定期清理已完成的任务
setInterval(() => {
  queueManager.cleanupCompletedTasks();
}, 60000); // 每分钟清理一次

export default api;
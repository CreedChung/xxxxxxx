"""配置管理工具"""
import json
import os
from typing import Dict, Optional
from dotenv import load_dotenv


class ConfigManager:
    """用户配置管理器"""
    
    def __init__(self):
        # 配置文件路径 - 存储到用户家目录中
        self.config_dir = os.path.join(os.path.expanduser("~"), ".ai_write_helper")
        self.config_file = os.path.join(self.config_dir, "user_config.json")
        
        # 确保配置目录存在
        os.makedirs(self.config_dir, exist_ok=True)
    
    def load_config(self) -> Dict:
        """从本地JSON文件加载配置"""
        # 加载 .env 文件（如果存在）
        load_dotenv()

        # 优先使用环境变量，否则使用默认值
        default_config = {
            'api_key': os.environ.get('API_KEY', 'sk-947751651f228c1862d92fac8372f6e6'),
            'base_url': os.environ.get('API_BASE_URL', 'https://apis.iflow.cn/v1'),
            'model_name': os.environ.get('MODEL_NAME', 'gpt-3.5-turbo')
        }

        # 允许用户自定义 model_name（存储在本地的配置会覆盖默认值）
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 只更新 model_name，保留 api_key 和 base_url 的默认值
                    if 'model_name' in loaded_config:
                        default_config['model_name'] = loaded_config['model_name']
            except Exception:
                pass  # 如果读取失败，使用默认配置

        return default_config
    
    def save_config(self, api_key: str, base_url: str, model_name: str) -> bool:
        """保存配置到本地JSON文件"""
        # 只保存 model_name，忽略 api_key 和 base_url
        config = {
            'model_name': model_name
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


# 全局配置管理器实例
config_manager = ConfigManager()
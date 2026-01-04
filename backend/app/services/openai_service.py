"""OpenAI服务"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio
import time
import logging

from ..utils.outline_util import get_random_indexes, calculate_nodes_distribution, generate_one_outline_json_by_level1
from ..utils.json_util import check_json
from ..utils.config_manager import config_manager

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI服务类"""
    
    def __init__(self):
        """初始化OpenAI服务，从config_manager读取配置"""
        # 从配置管理器加载配置
        config = config_manager.load_config()
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', '')
        self.model_name = config.get('model_name', 'gpt-3.5-turbo')

        # 初始化OpenAI客户端 - 使用异步客户端
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url if self.base_url else None
        )
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        try:
            models = await self.client.models.list()
            chat_models = []
            for model in models.data:
                model_id = model.id.lower()
                if any(keyword in model_id for keyword in ['gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek']):
                    chat_models.append(model.id)
            return sorted(list(set(chat_models)))
        except Exception as e:
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    async def stream_chat_completion(
        self, 
        messages: list, 
        temperature: float = 0.7,
        response_format: dict = None,
        max_retries: int = 3,
        retry_delay: float = 20.0
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 带限流重试的异步实现"""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    **({"response_format": response_format} if response_format is not None else {})
                )

                async for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
                return  # 成功完成，退出函数

            except openai.RateLimitError as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(f"API限流，第 {attempt + 1} 次重试，等待 {wait_time} 秒: {str(e)}")
                    yield f"data: {json.dumps({'status': 'rate_limited', 'message': f'API限流，正在重试... ({attempt + 1}/{max_retries})', 'wait_time': wait_time}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"API限流重试 {max_retries} 次后仍然失败: {str(e)}")
                    yield f"data: {json.dumps({'status': 'error', 'message': f'API限流重试 {max_retries} 次后失败，请稍后重试'}, ensure_ascii=False)}\n\n"
                    raise Exception(f"API限流重试 {max_retries} 次后失败: {str(e)}")
                    
            except openai.APITimeoutError as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"API超时，第 {attempt + 1} 次重试，等待 {wait_time} 秒: {str(e)}")
                    yield f"data: {json.dumps({'status': 'timeout', 'message': f'API超时，正在重试... ({attempt + 1}/{max_retries})', 'wait_time': wait_time}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"API超时重试 {max_retries} 次后仍然失败: {str(e)}")
                    yield f"data: {json.dumps({'status': 'error', 'message': f'API超时重试 {max_retries} 次后失败，请检查网络连接'}, ensure_ascii=False)}\n\n"
                    raise Exception(f"API超时重试 {max_retries} 次后失败: {str(e)}")
                    
            except Exception as e:
                last_error = e
                logger.error(f"API调用失败: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'API调用失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                raise e
        
        # 如果到达这里，说明所有重试都失败了
        if last_error:
            raise last_error

    async def _collect_stream_text(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str:
        """收集流式返回的文本到一个完整字符串"""
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
        ):
            full_content += chunk
        return full_content

    async def _generate_with_json_check(
        self,
        messages: list,
        schema: str | Dict[str, Any],
        max_retries: int = 3,
        temperature: float = 0.7,
        response_format: dict | None = None,
        log_prefix: str = "",
        raise_on_fail: bool = True,
    ) -> str:
        """
        通用的带 JSON 结构校验与重试的生成函数。

        返回：通过校验的 full_content；如果 raise_on_fail=False，则在多次失败后返回最后一次内容。
        """
        attempt = 0
        last_error_msg = ""

        while True:
            full_content = await self._collect_stream_text(
                messages,
                temperature=temperature,
                response_format=response_format,
            )

            isok, error_msg = check_json(str(full_content), schema)
            if isok:
                return full_content

            last_error_msg = error_msg
            prefix = f"{log_prefix} " if log_prefix else ""

            if attempt >= max_retries:
                print(f"{prefix}check_json 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                if raise_on_fail:
                    raise Exception(f"{prefix}check_json 校验失败: {last_error_msg}")
                # 不抛异常，返回最后一次内容（保持原有行为）
                return full_content

            attempt += 1
            print(f"{prefix}check_json 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
            await asyncio.sleep(0.5)

    async def generate_content_for_outline(self, outline: Dict[str, Any], project_overview: str = "") -> Dict[str, Any]:
        """为目录结构生成内容"""
        try:
            if not isinstance(outline, dict) or 'outline' not in outline:
                raise Exception("无效的outline数据格式")
            
            # 深拷贝outline数据
            import copy
            result_outline = copy.deepcopy(outline)
            
            # 计算总章节数（叶子节点数）
            total_leaf_chapters = self._count_leaf_chapters(result_outline['outline'])
            logger.info(f"开始为 {len(result_outline['outline'])} 个主章节生成内容，共 {total_leaf_chapters} 个叶子章节")
            
            # 递归处理目录
            await self._process_outline_recursive(result_outline['outline'], [], project_overview, 0, total_leaf_chapters)
            
            return result_outline
            
        except Exception as e:
            raise Exception(f"处理过程中发生错误: {str(e)}")
    
    def _count_leaf_chapters(self, chapters: list) -> int:
        """计算叶子节点数量"""
        count = 0
        for chapter in chapters:
            if 'children' not in chapter or not chapter.get('children'):
                count += 1
            else:
                count += self._count_leaf_chapters(chapter['children'])
        return count
    
    async def _process_outline_recursive(self, chapters: list, parent_chapters: list = None, project_overview: str = "", chapter_index: int = 0, total_chapters: int = 0):
        """递归处理章节列表，按顺序生成内容"""
        for idx, chapter in enumerate(chapters):
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            
            # 检查是否为叶子节点
            is_leaf = 'children' not in chapter or not chapter.get('children', [])
            
            # 准备当前章节信息
            current_chapter_info = {
                'id': chapter_id,
                'title': chapter_title,
                'description': chapter.get('description', '')
            }
            
            # 构建完整的上级章节列表
            current_parent_chapters = []
            if parent_chapters:
                current_parent_chapters.extend(parent_chapters)
            current_parent_chapters.append(current_chapter_info)
            
            current_chapter_num = chapter_index + idx + 1
            
            if is_leaf:
                # 为叶子节点生成内容，传递同级章节信息
                try:
                    logger.info(f"正在生成第 {current_chapter_num}/{total_chapters} 章内容: {chapter_title}")
                    content = ""
                    async for chunk in self._generate_chapter_content(
                        chapter, 
                        current_parent_chapters[:-1],  # 上级章节列表（排除当前章节）
                        chapters,  # 同级章节列表
                        project_overview
                    ):
                        content += chunk
                    if content:
                        chapter['content'] = content
                    logger.info(f"第 {current_chapter_num} 章内容生成完成: {chapter_title}")
                except Exception as e:
                    logger.error(f"第 {current_chapter_num} 章内容生成失败: {str(e)}")
                    chapter['error'] = str(e)
                    chapter['content'] = f"[内容生成失败: {str(e)}]"
            else:
                # 递归处理子章节
                child_chapters = chapter.get('children', [])
                await self._process_outline_recursive(
                    child_chapters, 
                    current_parent_chapters, 
                    project_overview,
                    chapter_index + idx,
                    total_chapters
                )
    
    async def _generate_chapter_content(self, chapter: dict, parent_chapters: list = None, sibling_chapters: list = None, project_overview: str = "") -> AsyncGenerator[str, None]:
        """
        为单个章节流式生成内容

        Args:
            chapter: 章节数据
            parent_chapters: 上级章节列表，每个元素包含章节id、标题和描述
            sibling_chapters: 同级章节列表，避免内容重复
            project_overview: 项目概述信息，提供项目背景和要求

        Yields:
            生成的内容流
        """
        try:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            chapter_description = chapter.get('description', '')

            # 构建提示词
            system_prompt = """你是一个专业的标书编写专家，负责为投标文件的技术标部分生成具体内容。

要求：
1. 内容要专业、准确，与章节标题和描述保持一致
2. 这是技术方案，不是宣传报告，注意朴实无华，不要假大空
3. 语言要正式、规范，符合标书写作要求，但不要使用奇怪的连接词，不要让人觉得内容像是AI生成的
4. 内容要详细具体，避免空泛的描述
5. 注意避免与同级章节内容重复，保持内容的独特性和互补性
6. 直接返回章节内容，不生成标题，不要任何额外说明或格式标记
"""

            # 构建上下文信息
            context_info = ""
            
            # 上级章节信息
            if parent_chapters:
                context_info += "上级章节信息：\n"
                for parent in parent_chapters:
                    context_info += f"- {parent['id']} {parent['title']}\n  {parent['description']}\n"
            
            # 同级章节信息（排除当前章节）
            if sibling_chapters:
                context_info += "同级章节信息（请避免内容重复）：\n"
                for sibling in sibling_chapters:
                    if sibling.get('id') != chapter_id:  # 排除当前章节
                        context_info += f"- {sibling.get('id', 'unknown')} {sibling.get('title', '未命名')}\n  {sibling.get('description', '')}\n"

            # 构建用户提示词
            project_info = ""
            if project_overview.strip():
                project_info = f"项目概述信息：\n{project_overview}\n\n"
            
            user_prompt = f"""请为以下标书章节生成具体内容：

{project_info}{context_info if context_info else ''}当前章节信息：
章节ID: {chapter_id}
章节标题: {chapter_title}
章节描述: {chapter_description}

请根据项目概述信息和上述章节层级关系，生成详细的专业内容，确保与上级章节的内容逻辑相承，同时避免与同级章节内容重复，突出本章节的独特性和技术方案的优势。"""

            # 调用AI流式生成内容
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 流式返回生成的文本
            async for chunk in self.stream_chat_completion(messages, temperature=0.7):
                yield chunk

        except Exception as e:
            print(f"生成章节内容时出错: {str(e)}")
            yield f"错误: {str(e)}"
            
    async def generate_outline_v2(self, overview: str, requirements: str) -> Dict[str, Any]:
        schema_json = json.dumps([
            {
                "rating_item": "原评分项",
                "new_title": "根据评分项修改的标题",
            }
        ])

        system_prompt = f"""
            ### 角色
            你是专业的标书编写专家，擅长根据项目需求编写标书。
            
            ### 人物
            1. 根据得到的项目概述(overview)和评分要求(requirements)，撰写技术标部分的一级提纲
            
            ### 说明
            1. 只设计一级标题，数量要和"评分要求"一一对应
            2. 一级标题名称要进行简单修改，不能完全使用"评分要求"中的文字

            
            ### Output Format in JSON
            {schema_json}

            """
        user_prompt = f"""
            ### 项目信息
            
            <overview>
            {overview}
            </overview>

            <requirements>
            {requirements}
            </requirements>


            直接返回json，不要任何额外说明或格式标记

            """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时抛出异常）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=schema_json,
            max_retries=3,
            temperature=0.7,
            response_format={"type": "json_object"},
            log_prefix="一级提纲",
            raise_on_fail=True,
        )

        # 通过校验后再进行 JSON 解析
        level_l1 = json.loads(full_content.strip())

        expected_word_count = 100000
        leaf_node_count = expected_word_count // 1500
        
        # 随机重点章节
        index1, index2 = get_random_indexes(len(level_l1))

        nodes_distribution = calculate_nodes_distribution(len(level_l1), (index1, index2), leaf_node_count)
        
        # 顺序生成每个一级节点的提纲，避免API限流
        outline = []
        for i, level1_node in enumerate(level_l1):
            try:
                logger.info(f"正在生成第 {i+1}/{len(level_l1)} 章提纲: {level1_node['new_title']}")
                chapter_outline = await self.process_level1_node(i, level1_node, nodes_distribution, level_l1, overview, requirements)
                outline.append(chapter_outline)
                logger.info(f"第 {i+1} 章提纲生成完成: {level1_node['new_title']}")
            except Exception as e:
                logger.error(f"第 {i+1} 章提纲生成失败: {str(e)}")
                # 创建错误章节作为占位符
                error_outline = {
                    "id": f"chapter_{i+1}",
                    "title": f"{level1_node['new_title']} (生成失败)",
                    "description": f"章节生成失败: {str(e)}",
                    "children": [],
                    "error": str(e)
                }
                outline.append(error_outline)
        
        
        
        return {"outline": outline}
    
    async def process_level1_node(self, i, level1_node, nodes_distribution, level_l1, overview, requirements):
        """处理单个一级节点的函数"""

        # 生成json
        json_outline = generate_one_outline_json_by_level1(level1_node["new_title"], i + 1, nodes_distribution)
        print(f"正在处理第{i+1}章: {level1_node['new_title']}")
        
        # 其他标题
        other_outline = "\n".join([f"{j+1}. {node['new_title']}" 
                            for j, node in enumerate(level_l1) 
                            if j!= i])

        system_prompt = f"""
    ### 角色
    你是专业的标书编写专家，擅长根据项目需求编写标书。
    
    ### 任务
    1. 根据得到项目概述(overview)、评分要求(requirements)补全标书的提纲的二三级目录
    
    ### 说明
    1. 你将会得到一段json，这是提纲的其中一个章节，你需要再原结构上补全标题(title)和描述(description)
    2. 二级标题根据一级标题撰写,三级标题根据二级标题撰写
    3. 补全的内容要参考项目概述(overview)、评分要求(requirements)等项目信息
    4. 你还会收到其他章节的标题(other_outline)，你需要确保本章节的内容不会包含其他章节的内容
    
    ### 注意事项
    在原json上补全信息，禁止修改json结构，禁止修改一级标题

    ### Output Format in JSON
    {json_outline}

    """
        user_prompt = f"""
    ### 项目信息

    <overview>
    {overview}
    </overview>

    <requirements>
    {requirements}
    </requirements>
    
    <other_outline>
    {other_outline}
    </other_outline>


    直接返回json，不要任何额外说明或格式标记

    """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有“返回最后一次结果”的行为）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json_outline,
            max_retries=3,
            temperature=0.7,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )

        return json.loads(full_content.strip())
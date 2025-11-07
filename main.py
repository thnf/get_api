"""
AstrBot 定时API获取插件
定时从指定API获取数据并推送到指定会话
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

import aiohttp
import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register


@register(
    "api_fetcher",
    "YourName",
    "定时获取API内容并推送的插件",
    "1.0.0",
    "https://github.com/yourusername/astrbot_plugin_api_fetcher"
)
class APIFetcherPlugin(Star):
    """定时API获取插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 从配置文件读取参数
        self.api_url = config.get("api_url", "")
        self.fetch_interval = config.get("fetch_interval", 3600)  # 默认1小时
        self.enabled = config.get("enabled", False)
        self.target_sessions = config.get("target_sessions", [])  # 推送目标会话列表
        self.message_template = config.get("message_template", "API更新:\n{content}")
        self.headers = config.get("headers", {})
        self.request_method = config.get("request_method", "GET")
        self.request_body = config.get("request_body", {})
        
        # 任务控制
        self.fetch_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 启动定时任务
        if self.enabled and self.api_url:
            asyncio.create_task(self.start_fetch_task())
            logger.info(f"API定时任务已启动,间隔: {self.fetch_interval}秒")
        else:
            logger.info("API定时任务未启用或API地址未配置")

    async def start_fetch_task(self):
        """启动定时获取任务"""
        self.is_running = True
        while self.is_running:
            try:
                await self.fetch_and_send()
            except Exception as e:
                logger.error(f"定时任务执行失败: {e}")
            
            # 等待下一次执行
            await asyncio.sleep(self.fetch_interval)

    async def fetch_api(self) -> dict:
        """
        从API获取数据
        
        Returns:
            dict: API返回的JSON数据
        """
        async with aiohttp.ClientSession() as session:
            try:
                if self.request_method.upper() == "GET":
                    async with session.get(
                        self.api_url,
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
                else:  # POST
                    async with session.post(
                        self.api_url,
                        headers=self.headers,
                        json=self.request_body,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"API请求失败: {e}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                raise

    def format_message(self, data: dict) -> str:
        """
        格式化API返回的数据为消息文本
        
        Args:
            data: API返回的数据
            
        Returns:
            str: 格式化后的消息文本
        """
        try:
            # 尝试使用模板格式化
            content = json.dumps(data, ensure_ascii=False, indent=2)
            return self.message_template.format(
                content=content,
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **data  # 允许在模板中使用数据字段
            )
        except Exception as e:
            logger.error(f"消息格式化失败: {e}")
            # 降级为简单格式
            return f"API数据更新 [{datetime.now().strftime('%H:%M:%S')}]\n{json.dumps(data, ensure_ascii=False, indent=2)}"

    async def fetch_and_send(self):
        """获取API数据并发送到目标会话"""
        try:
            # 获取API数据
            data = await self.fetch_api()
            logger.info(f"成功获取API数据")
            
            # 格式化消息
            message_text = self.format_message(data)
            
            # 构建消息链
            message_chain = MessageChain().message(message_text)
            
            # 发送到所有目标会话
            if not self.target_sessions:
                logger.warning("未配置推送目标会话")
                return
                
            for session_id in self.target_sessions:
                try:
                    await self.context.send_message(session_id, message_chain)
                    logger.info(f"已推送消息到会话: {session_id}")
                except Exception as e:
                    logger.error(f"推送消息到 {session_id} 失败: {e}")
                    
        except Exception as e:
            logger.error(f"fetch_and_send执行失败: {e}")

    @filter.command("apifetch")
    async def manual_fetch(self, event: AstrMessageEvent):
        """手动触发获取API数据"""
        if not self.api_url:
            yield event.plain_result("❌ 未配置API地址")
            return
            
        try:
            yield event.plain_result("⏳ 正在获取API数据...")
            
            data = await self.fetch_api()
            message_text = self.format_message(data)
            
            yield event.plain_result(message_text)
            
        except Exception as e:
            yield event.plain_result(f"❌ 获取失败: {str(e)}")

    @filter.command("apifetch", alias={"api状态"})
    @filter.command_group("apifetch")
    def apifetch_group(self):
        """API获取插件命令组"""
        pass

    @apifetch_group.command("status")
    async def fetch_status(self, event: AstrMessageEvent):
        """查看定时任务状态"""
        status_text = f"""
📊 API获取插件状态

🔗 API地址: {self.api_url or '未配置'}
⏰ 获取间隔: {self.fetch_interval}秒
🎯 推送目标: {len(self.target_sessions)}个会话
▶️ 运行状态: {'运行中' if self.is_running else '已停止'}
✅ 启用状态: {'已启用' if self.enabled else '已禁用'}
        """.strip()
        yield event.plain_result(status_text)

    @apifetch_group.command("start")
    async def start_task(self, event: AstrMessageEvent):
        """启动定时任务"""
        if self.is_running:
            yield event.plain_result("⚠️ 定时任务已在运行中")
            return
            
        if not self.api_url:
            yield event.plain_result("❌ 未配置API地址,请先在配置文件中设置")
            return
            
        self.is_running = True
        asyncio.create_task(self.start_fetch_task())
        yield event.plain_result("✅ 定时任务已启动")

    @apifetch_group.command("stop")
    async def stop_task(self, event: AstrMessageEvent):
        """停止定时任务"""
        if not self.is_running:
            yield event.plain_result("⚠️ 定时任务未在运行")
            return
            
        self.is_running = False
        yield event.plain_result("✅ 定时任务已停止")

    @apifetch_group.command("now")
    async def fetch_now(self, event: AstrMessageEvent):
        """立即执行一次获取"""
        if not self.api_url:
            yield event.plain_result("❌ 未配置API地址")
            return
            
        try:
            yield event.plain_result("⏳ 正在获取API数据...")
            await self.fetch_and_send()
            yield event.plain_result("✅ 数据已获取并推送")
        except Exception as e:
            yield event.plain_result(f"❌ 执行失败: {str(e)}")

    @apifetch_group.command("addtarget")
    async def add_target(self, event: AstrMessageEvent):
        """将当前会话添加为推送目标"""
        session_id = event.unified_msg_origin
        
        if session_id in self.target_sessions:
            yield event.plain_result("⚠️ 当前会话已在推送列表中")
            return
            
        self.target_sessions.append(session_id)
        self.config["target_sessions"] = self.target_sessions
        self.config.save_config()
        
        yield event.plain_result(f"✅ 已添加当前会话为推送目标\n当前共有 {len(self.target_sessions)} 个推送目标")

    @apifetch_group.command("removetarget")
    async def remove_target(self, event: AstrMessageEvent):
        """将当前会话从推送目标中移除"""
        session_id = event.unified_msg_origin
        
        if session_id not in self.target_sessions:
            yield event.plain_result("⚠️ 当前会话不在推送列表中")
            return
            
        self.target_sessions.remove(session_id)
        self.config["target_sessions"] = self.target_sessions
        self.config.save_config()
        
        yield event.plain_result(f"✅ 已移除当前会话\n当前共有 {len(self.target_sessions)} 个推送目标")

    async def terminate(self):
        """插件卸载时清理资源"""
        self.is_running = False
        if self.fetch_task and not self.fetch_task.done():
            self.fetch_task.cancel()
        logger.info("API获取插件已停止")
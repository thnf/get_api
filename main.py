# -*- coding: utf-8 -*-
"""
astrbot_plugin_api_fetcher
定时拉取第三方 API 并将结果主动推送到指定会话（unified_msg_origin）。

注意事项：
- 推荐把此目录放到 AstrBot 的 data/plugins 下并通过 AstrBot 管理面板启用。
- 插件可配置项位于 `_conf_schema.json`（由 AstrBot 在 data/config 中保存实际配置）。
- 本插件使用 httpx 进行异步请求（异步库），请在 `requirements.txt` 中声明依赖。

简单实现要点：
- 插件继承自 Star
- 在 __init__ 中启动一个 asyncio 任务作为 scheduler
- 使用 self.context.send_message(session, message_chain) 主动发送消息
- 实现 terminate() 以便停用时干净退出

"""

import asyncio
import json
import os
import hashlib
import time
from typing import Optional
from datetime import datetime, time as dtime, timedelta

import httpx

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.star import Context, Star, register


@register("api_fetcher", "你的名字", "定时拉取 API 并推送结果的示例插件", "1.0.0", "https://example.com/repo")
class APIFetcher(Star):
    """定时拉取 API 并主动发送到指定会话的插件。

    配置项在 `_conf_schema.json` 中定义。常用字段：
      - api_url: 要拉取的 API 地址（string）
      - interval: 拉取间隔，单位秒（int，默认 3600）
      - target_session: 要发送到的 unified_msg_origin（string，例如 aiocqhttp:group:123456 或 aiocqhttp:private:123456）
      - message_template: 格式化消息的模版，支持占位 {data}（string）
    """

    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        # 插件配置（AstrBot 会在实例化时传入配置对象）
        self.config = config or {}
        self.api_url = str(self.config.get("api_url", "")).strip()
        # 间隔最小为 1 秒，防止无睡眠导致忙循环
        self.interval = max(1, int(self.config.get("interval", 3600)))
        self.target_session = str(self.config.get("target_session", "")).strip()
        self.message_template = str(self.config.get("message_template", "{data}"))
        # 调度模式: 'interval' 或 'daily'
        self.schedule_type = str(self.config.get("schedule_type", "interval")).strip()
        # 当 schedule_type == 'daily' 时，使用 daily_time，格式 HH:MM
        self.daily_time = str(self.config.get("daily_time", "00:00")).strip()

        # 内存中记录上一次已发送的内容哈希，用于简单去重（重启失效）。
        self._last_hash = None
        # 控制任务运行
        self._running = True

        # 如果用户没有填写必要配置，仍然不抛异常，但 scheduler 会跳过执行并每 10s 检查一次配置
        asyncio.create_task(self._scheduler())

    async def terminate(self):
        """当插件被卸载/停用时调用，退出后台任务。"""
        self._running = False
        # 给任务一点时间退出
        await asyncio.sleep(0.1)

    async def _fetch_api(self) -> str:
        """使用 httpx 异步请求 API，返回文本结果。"""
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(self.api_url)
            r.raise_for_status()
            return r.text

    def _hash_text(self, s: str) -> str:
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    def _format_message(self, raw: str) -> str:
        # 默认将 raw 文本替换到 message_template 的 {data} 位置
        try:
            return self.message_template.format(data=raw)
        except Exception:
            # 如果格式化失败则退回原文（截断到 1500 字以防过长）
            return raw[:1500]

    async def _send_message_to_session(self, text: str) -> bool:
        # 构造 MessageChain 并调用 context.send_message
        try:
            chain = MessageChain().message(text)
            ok = await self.context.send_message(self.target_session, chain)
            logger.info(f"api_fetcher: send_message returned {ok}")
            return bool(ok)
        except Exception as e:
            logger.error(f"api_fetcher: send_message error: {e}")
            return False

    async def _scheduler(self):
        """后台调度任务：按间隔拉取 API 并在检测到新内容时推送。"""
        # 初次延迟 3 秒，以便 AstrBot 其余部分完成初始化
        await asyncio.sleep(3)
        while self._running:
            try:
                if not self.api_url or not self.target_session:
                    logger.warning("api_fetcher: api_url or target_session not set in config, waiting...")
                    await asyncio.sleep(10)
                    continue

                # 根据调度类型执行一次拉取
                raw = await self._fetch_api()
                # 简单过滤：空响应则跳过
                if raw is None or raw.strip() == "":
                    logger.info("api_fetcher: empty response, skip")
                else:
                    current_hash = self._hash_text(raw)
                    if current_hash == self._last_hash:
                        logger.debug("api_fetcher: content unchanged, skip sending")
                    else:
                        text = self._format_message(raw)
                        sent = await self._send_message_to_session(text)
                        if sent:
                            self._last_hash = current_hash
                        # 如果不发送成功也不抛，让下次继续重试
            except Exception as e:
                logger.error(f"api_fetcher: scheduler error: {e}")
            # 计算下一次等待时间：根据 schedule_type
            try:
                if self.schedule_type == 'daily':
                    # daily_time 格式应为 HH:MM
                    hh_mm = self.daily_time.split(":")
                    if len(hh_mm) != 2:
                        logger.error(f"api_fetcher: invalid daily_time format: {self.daily_time}, fallback to interval")
                        await asyncio.sleep(self.interval)
                        continue
                    hour = int(hh_mm[0])
                    minute = int(hh_mm[1])
                    now = datetime.now()
                    target_today = datetime.combine(now.date(), dtime(hour=hour, minute=minute))
                    if target_today <= now:
                        # 已过今日时间，排到明天
                        target_today = target_today + timedelta(days=1)
                    sleep_seconds = (target_today - now).total_seconds()
                    logger.info(f"api_fetcher: next daily run in {int(sleep_seconds)} seconds (at {target_today.isoformat()})")
                    # 分段睡眠以便能响应 terminate 请求
                    remained = sleep_seconds
                    while remained > 0 and self._running:
                        step = min(remained, 60)
                        await asyncio.sleep(step)
                        remained -= step
                else:
                    # 默认按间隔
                    await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"api_fetcher: schedule wait error: {e}")
                # 出现异常时短暂等待，避免进入紧密/无限循环
                try:
                    await asyncio.sleep(10)
                except Exception:
                    # 如果被取消或其他问题，继续循环以响应 terminate
                    pass

# astrbot_plugin_api_fetcher

定时拉取某 API 并将结果发送到 AstrBot 会话的插件示例。

功能
- 定时（可配置）拉取 `api_url`。
- 检测到新内容后主动发送到配置的 `target_session`（unified_msg_origin）。

安装与使用
1. 将本目录放到 AstrBot 的插件目录（通常是 `AstrBot/data/plugins`），或将仓库克隆到该目录。
2. 安装依赖（由 AstrBot 在安装插件时读取 `requirements.txt` 并安装）：
   - `httpx`（异步 HTTP 客户端）
3. 在 AstrBot 插件管理面板中启用插件，并在插件配置界面设置：
   - api_url: 要拉取的 API 地址
   - interval: 拉取间隔（秒）
   - target_session: 目标会话（unified_msg_origin）
   - message_template: 发送消息的模版，使用 `{data}` 占位 API 返回文本

示例配置
```
api_url: "https://api.example.com/latest"
interval: 1800
target_session: "aiocqhttp:group:123456"
message_template: "【API 更新】\n{data}"
```

每日固定时间示例（使用 schedule_type = daily）：
```
api_url: "https://api.example.com/latest"
schedule_type: "daily"
daily_time: "09:30"
target_session: "aiocqhttp:group:123456"
message_template: "【每日更新】\n{data}"
```

注意事项与扩展建议
- 当前实现只使用内存做去重（重启后会丢失）。建议在生产中将已发送的最新 id/hash 持久化到 AstrBot 的 `data` 目录或数据库。
- 如果 API 返回 JSON，建议在 `main.py` 中对 `raw` 做 json.loads 并按需格式化文本。
- 可以加入更复杂的去重策略（例如根据条目 id 去重）、失败重试、错误告警（发送到管理员）等。

License: MIT

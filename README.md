# AstrBot API定时获取插件

定时从指定API获取数据并推送到指定会话的AstrBot插件。

## 功能特性

- ✅ 定时自动获取API数据
- ✅ 支持GET和POST请求
- ✅ 自定义请求头和请求体
- ✅ 灵活的消息模板系统
- ✅ 多会话推送支持
- ✅ 手动触发和状态管理
- ✅ 完善的错误处理

## 安装方法

### 方法1: 通过插件市场安装(推荐)
1. 打开 AstrBot WebUI
2. 进入"插件市场"
3. 搜索 `api_fetcher` 或使用Github仓库链接安装

### 方法2: 手动安装
```bash
cd AstrBot/data/plugins
git clone https://github.com/yourusername/astrbot_plugin_api_fetcher
cd astrbot_plugin_api_fetcher
pip install -r requirements.txt
```

## 配置说明

安装插件后,在AstrBot管理面板中找到插件配置:

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `enabled` | 是否启用定时任务 | true |
| `api_url` | API地址 | `https://api.example.com/data` |
| `fetch_interval` | 获取间隔(秒) | 3600 (每小时) |
| `request_method` | 请求方法 | GET / POST |
| `headers` | 请求头(JSON) | `{"Authorization": "Bearer token"}` |
| `request_body` | 请求体(JSON,仅POST) | `{"key": "value"}` |
| `message_template` | 消息模板 | 见下方说明 |
| `target_sessions` | 推送目标会话 | 通过命令添加 |

### 消息模板说明

消息模板支持以下变量:

- `{content}` - API返回的完整JSON数据
- `{time}` - 数据获取时间
- API返回的任何字段,如 `{title}`, `{data}`, `{items}` 等

示例模板:
```
📢 热榜更新
⏰ 更新时间: {time}

{content}
```

或者如果API返回 `{"title": "标题", "data": [...]}`:
```
📢 {title}
⏰ {time}

{data}
```

## 使用指南

### 基础命令

| 命令 | 说明 |
|------|------|
| `/apifetch` | 手动获取API数据并显示 |
| `/apifetch status` | 查看插件运行状态 |
| `/apifetch start` | 启动定时任务 |
| `/apifetch stop` | 停止定时任务 |
| `/apifetch now` | 立即执行一次获取并推送 |
| `/apifetch addtarget` | 将当前会话添加为推送目标 |
| `/apifetch removetarget` | 将当前会话从推送目标移除 |

### 使用流程

1. **配置API地址**
   - 在管理面板配置 `api_url`
   - 如需认证,配置 `headers`

2. **添加推送目标**
   ```
   /apifetch addtarget
   ```
   在需要接收推送的群聊或私聊中执行此命令

3. **启动定时任务**
   ```
   /apifetch start
   ```
   或在配置中将 `enabled` 设为 `true` 后重载插件

4. **测试推送**
   ```
   /apifetch now
   ```
   手动触发一次推送,确认配置正确

## 使用示例

### 示例1: 获取微博热搜

配置:
```json
{
  "api_url": "https://weibo.com/ajax/side/hotSearch",
  "fetch_interval": 1800,
  "message_template": "🔥 微博热搜榜 (更新时间: {time})\n\n{content}"
}
```

### 示例2: 获取天气信息

配置:
```json
{
  "api_url": "https://api.weather.com/forecast",
  "fetch_interval": 3600,
  "headers": {
    "Authorization": "Bearer your_api_key"
  },
  "message_template": "🌤️ 天气预报\n时间: {time}\n\n{content}"
}
```

### 示例3: 监控服务状态

配置:
```json
{
  "api_url": "https://status.example.com/api/health",
  "fetch_interval": 300,
  "request_method": "POST",
  "request_body": {
    "service": "main"
  },
  "message_template": "📊 服务状态检查\n{time}\n\n状态: {status}\n详情: {message}"
}
```

## 常见问题

### Q: 如何获取会话ID?
A: 使用 `/apifetch addtarget` 命令即可自动添加当前会话,无需手动获取ID

### Q: 推送不生效?
A: 检查:
1. 定时任务是否启动 (`/apifetch status`)
2. API地址是否正确
3. 是否已添加推送目标
4. 查看AstrBot日志是否有错误

### Q: 如何自定义消息格式?
A: 修改 `message_template` 配置,使用大括号包裹变量名,如 `{title}`

### Q: 支持什么格式的API?
A: 目前仅支持返回JSON格式的API

## 开发与贡献

欢迎提交Issue和Pull Request!

仓库地址: https://github.com/yourusername/astrbot_plugin_api_fetcher

## 许可证

AGPL-3.0 License

## 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 优秀的聊天机器人框架
- 参考了 [astrbot_plugin_weibo_hot](https://github.com/wr0x00/astrbot_plugin_weibo_hot) 的实现
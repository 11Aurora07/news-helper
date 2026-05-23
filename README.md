# 通知助手

一个用于监控“校园墙/二手墙/表白墙”新帖的本地轮询工具。

当前版本先解决 4 件事：

1. 周期性拉取帖子数据
2. 用关键词筛选目标帖子
3. 对已通知帖子去重
4. 命中后发出通知

## 现在已经能做什么

你要蹲“电动车”相关帖子，工具会定时检查帖子列表，只要发现新的匹配帖子，就立刻在终端打印，并可选触发 Windows 弹窗或 webhook 通知。

当前项目已经支持：

- `sample_json`：读取本地样例数据，方便测试
- `http_json`：请求一个返回 JSON 的接口，适合接真实校园墙数据

## 小程序场景怎么理解

既然你的校园墙是微信小程序，重点就不是“写一个关键词匹配器”，而是“还原小程序真实请求”。

通常会遇到下面几种情况：

1. 小程序直接请求一个 JSON 接口
2. 接口需要携带固定请求头、Cookie、token 或用户标识
3. 接口需要分页参数，比如 `page=1`、`size=20`
4. 接口需要 POST 请求，甚至是表单或原始请求体
5. 接口带签名参数、时间戳、动态 token，这种就要进一步分析

这个项目现在已经支持：

- 自定义 URL 查询参数
- 自定义 headers
- `GET` / `POST`
- JSON 请求体
- 表单请求体
- 原始文本请求体
- 自定义 `json_path`
- 自定义字段映射 `field_map`

也就是说，只要你能抓到小程序真实接口，大概率不用改代码，只改配置就能接入。

## 快速开始

### 1. 进入目录

```powershell
cd "C:\Users\lenovo\Desktop\哈基翔的秘密基地\通知助手"
```

### 2. 运行样例模式

```powershell
python main.py --config config.sample.json --once
```

### 3. 持续监控

```powershell
python main.py --config config.sample.json
```

## Fiddler 辅助脚本

如果你已经装好了 Fiddler 和微信，可以直接运行：

```powershell
.\tools\run_fiddler_helper.bat
```

这个脚本会帮你：

1. 切换到 Fiddler
2. 清空当前会话列表
3. 切换回微信
4. 等你手动刷新校园墙列表
5. 再切回 Fiddler

它不是完整抓包自动化，只是把重复窗口切换和清理动作自动化，方便你更快定位目标接口。

## 配置文件

### 样例配置

```json
{
  "poll_interval_seconds": 30,
  "keywords": ["电动车", "电瓶车", "雅迪", "爱玛"],
  "source": {
    "type": "sample_json",
    "path": "data/sample_posts.json"
  },
  "notifiers": {
    "console": true,
    "windows_popup": false,
    "webhook": {
      "enabled": false,
      "url": ""
    }
  }
}
```

### 小程序 HTTP 配置模板

参考 [config.miniprogram.template.json](C:\Users\lenovo\Desktop\哈基翔的秘密基地\通知助手\config.miniprogram.template.json)。

示例：

```json
{
  "poll_interval_seconds": 20,
  "keywords": ["电动车", "电瓶车", "雅迪", "爱玛"],
  "source": {
    "type": "http_json",
    "url": "https://example.com/wall/posts",
    "method": "GET",
    "params": {
      "page": 1,
      "size": 20
    },
    "headers": {
      "User-Agent": "Mozilla/5.0",
      "Authorization": "Bearer your-token",
      "Cookie": "session=your-session"
    },
    "json_path": "data.list",
    "field_map": {
      "id": "postId",
      "title": "title",
      "content": "content",
      "url": "shareUrl",
      "created_at": "publishTime"
    }
  },
  "notifiers": {
    "console": true,
    "windows_popup": true,
    "webhook": {
      "enabled": false,
      "url": "",
      "method": "POST",
      "headers": {
        "Content-Type": "application/json"
      }
    }
  }
}
```

## `source` 字段说明

### `type`

- `sample_json`
- `http_json`

### `url`

真实接口地址。

### `method`

接口请求方式，例如 `GET` 或 `POST`。

### `params`

URL 查询参数。例如：

```json
{
  "params": {
    "page": 1,
    "size": 20,
    "type": "all"
  }
}
```

### `headers`

从抓包里复制过来的请求头。常见包括：

- `Authorization`
- `Cookie`
- `Referer`
- `User-Agent`
- `X-Token`
- `X-Sign`

### `body`

JSON 请求体。默认使用 JSON 编码。

### `body_mode`

可选值：

- `json`
- `form`
- `raw`

### `body_form`

表单请求体，会编码成 `application/x-www-form-urlencoded`。

### `body_raw`

原始请求体文本。

### `json_path`

接口响应中“帖子数组”的路径。

例如响应是：

```json
{
  "data": {
    "list": [
      {
        "postId": "123",
        "title": "转卖电动车"
      }
    ]
  }
}
```

那就写：

```json
{
  "json_path": "data.list"
}
```

### `field_map`

把真实接口字段映射成程序内部字段：

- `id`
- `title`
- `content`
- `url`
- `created_at`

支持点路径。例如：

```json
{
  "field_map": {
    "id": "post.id",
    "title": "post.title",
    "content": "post.detail.text",
    "url": "share.url",
    "created_at": "meta.publishTime"
  }
}
```

## 小程序抓包建议

你需要先拿到“帖子列表接口”的真实请求信息。通常可以用这些办法：

1. 微信开发者工具打开对应小程序，查看 `Network`
2. Android 模拟器或真机配合代理工具抓包
3. 如果小程序其实调用的是普通 HTTPS API，就把请求 URL、method、headers、body、响应 JSON 保存下来

你至少需要给我这些信息里的大部分：

1. 请求 URL
2. 请求方法
3. 请求头
4. 请求体
5. 响应 JSON 样例

有了这些，我就能帮你把模板配置改成真实可跑的版本。

## 去重机制

程序会把已经通知过的帖子记录到 `data/state.db`。

同一条帖子只通知一次。优先使用 `id` 去重；如果没有 `id`，则回退到 `title + content + url` 的哈希值。

## 当前限制

如果小程序接口存在下面这些特征，可能还要继续补代码：

1. 登录态会很快失效
2. 每次请求都要动态签名
3. 响应内容被加密
4. 帖子列表不是直接 JSON，而是更复杂的嵌套结构

前 1、2 种最常见。如果你抓到请求样本，我可以继续针对那个小程序做适配。

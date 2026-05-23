# 部署说明

这个项目本质上是一个常驻轮询进程，不适合部署成“每隔几分钟触发一次”的定时任务。

## 推荐顺序

1. `Linux 云服务器 + systemd`
2. `Railway` 或 `Render` 这类常驻 worker
3. 本机开机自启

如果你的目标是“电脑关机也继续跑”，优先选第 1 种。

## 方案零：GitHub Actions 每 5 分钟执行一次

这不是常驻进程，而是“每 5 分钟启动一次，跑完一轮就退出”。

适合：

- 接受 5 分钟级别延迟
- 不想买服务器
- 先低成本验证长期可用性

不适合：

- 想要 20 秒级近实时
- 强依赖本地持久文件

### 已提供文件

- `.github/workflows/campus-monitor.yml`
- `tools/build_github_actions_config.py`

### 需要的 GitHub Secrets

在仓库 `Settings > Secrets and variables > Actions` 中新增：

- `YS_SESSION_COOKIE`
  只填 cookie 值本身，不带 `ys7_ysxy_session=`
- `PUSHPLUS_TOKEN`

### 工作方式

1. Actions 每 5 分钟触发一次
2. 运行时从模板生成 `config.generated.json`
3. Cookie 和 PushPlus token 从 Secrets 注入
4. `data/` 目录通过 Actions cache 尽量保留 `state.db` 和 `session.json`

### 限制

- GitHub 官方只支持最短 5 分钟调度
- 调度可能延迟，不保证准点
- 缓存不是数据库，极端情况下可能丢失已通知记录
- Cookie 失效后，还是要更新 `YS_SESSION_COOKIE`

### 实际上线步骤

1. 在 GitHub 新建一个空仓库
2. 把当前项目目录上传到仓库
3. 确保这些文件已经在仓库里：
   - `.github/workflows/campus-monitor.yml`
   - `tools/build_github_actions_config.py`
   - `config.miniprogram.template.json`
   - `main.py`
   - `monitor/`
4. 在仓库 `Settings > Secrets and variables > Actions` 新增：
   - `YS_SESSION_COOKIE`
   - `PUSHPLUS_TOKEN`
5. 打开仓库 `Actions` 页面，允许 workflow 运行
6. 手动执行一次 `campus-monitor`
7. 确认收到通知后，再等定时调度自动运行

### 首次排查重点

- 如果报 `HTTP request failed`，先怀疑 Cookie 已失效
- 如果运行成功但没通知，先看这 5 分钟内是否真的有新帖
- 如果重复通知，通常是 Actions 缓存没有命中，导致 `data/state.db` 没恢复

## 方案一：Linux 云服务器

适合长期稳定运行，最接近你现在本地这套逻辑。

### 服务器要求

- Ubuntu 22.04 或类似 Linux
- Python 3.9+
- 能访问 `https://ys.qimiaoyuanfen.com`
- 能访问 `https://www.pushplus.plus`

### 部署步骤

1. 上传项目到服务器，例如放到 `/opt/campus-monitor`
2. 确认 `config.miniprogram.json` 里是可用 Cookie 和 PushPlus token
3. 赋予启动脚本执行权限

```bash
cd /opt/campus-monitor
chmod +x deploy/start_monitor.sh
```

4. 安装 systemd 服务

```bash
cp deploy/campus-monitor.service /etc/systemd/system/campus-monitor.service
systemctl daemon-reload
systemctl enable campus-monitor
systemctl start campus-monitor
```

5. 查看运行状态

```bash
systemctl status campus-monitor
journalctl -u campus-monitor -f
```

### 说明

- 服务会在服务器重启后自动拉起
- 进程异常退出后会自动重启
- `data/state.db` 和 `data/session.json` 会保留在服务器本地

## 方案二：Railway / Render

适合不想自己维护 Linux 服务，但接受平台可能休眠、重启或改计费规则。

### 关键点

- 要部署成 `worker` 或 `background worker`
- 不要部署成静态站点
- 不要依赖平台的 `cron` 来每 20 秒触发一次

### 需要的文件

项目里已经提供：

- `Procfile`
- `requirements.txt`

默认启动命令：

```bash
python main.py --config config.miniprogram.json
```

### 注意

- 你的 `data/state.db`、`data/session.json` 默认是本地文件
- 如果平台文件系统不是持久的，容器重建后会丢失已通知记录和 Cookie
- 这种情况下要么挂持久卷，要么后续把状态改到外部数据库

## 方案三：本机开机自启

适合先用最省事的方式，但前提是电脑必须开机。

可以用：

- Windows 计划任务
- 启动文件夹快捷方式

如果你要这条路，我下一步可以直接给你生成一个本机一键安装脚本。

## 现实维护项

不管本机还是云端，都还有一个现实问题不会消失：

- `ys7_ysxy_session` 过期后，需要重新抓包更新 Cookie

现在代码已经支持把新 `Set-Cookie` 写回 `data/session.json`，但前提是接口还愿意给你续期；如果彻底失效，还是要重新抓一次。

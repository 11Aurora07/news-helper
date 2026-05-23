# 部署说明

如果你的目标是“电脑关机后仍然继续监视”，本机方案全部不成立。

唯一靠谱的路线是：

1. 准备一台常在线 Linux 服务器
2. 把这个项目部署上去
3. 让 Web 管理界面和后台监控一起长期运行

## 推荐方案

推荐直接用：

- Ubuntu 22.04 轻量云服务器
- `systemd` 常驻运行
- 浏览器访问 Web 管理界面

不再推荐：

- GitHub Actions
- 本机开机自启
- 只靠手机网页前台保持运行

## 服务器要求

- Ubuntu 22.04 或类似 Linux
- Python 3.9+
- 能访问：
  - `https://ys.qimiaoyuanfen.com`
  - `https://www.pushplus.plus`
- 安全组放行 Web 端口，例如 `8000`

## 上传项目

把项目上传到服务器，例如：

```bash
/opt/notify-helper
```

## 安装依赖

```bash
cd /opt/notify-helper
python3 -m pip install -r requirements.txt
```

## 启动 Web 管理版

先手动验证：

```bash
cd /opt/notify-helper
python3 -m webui.serve
```

默认地址：

```text
http://服务器IP:8000
```

如果能打开，再配置 `systemd`。

## systemd 常驻运行

项目里已经提供服务文件：

- `deploy/notify-helper-web.service`

安装步骤：

```bash
cp deploy/notify-helper-web.service /etc/systemd/system/notify-helper-web.service
systemctl daemon-reload
systemctl enable notify-helper-web
systemctl start notify-helper-web
```

查看状态：

```bash
systemctl status notify-helper-web
journalctl -u notify-helper-web -f
```

## Web 管理界面

部署成功后，你可以在手机或电脑浏览器里直接管理：

- 关键词
- 分类
- PushPlus token
- Session Cookie
- 手动触发检查
- 查看命中记录
- 查看运行历史

## 持久化数据

当前项目默认把数据保存在：

- `data/app.db`
- `data/state.db`
- `data/session.json`

只要服务器磁盘还在，这些数据就会保留。

## 唯一绕不过去的维护项

无论本机还是服务器，都还有一个现实维护项：

- `ys7_ysxy_session` 失效后，需要重新抓包并更新 Cookie

现在 Web 管理界面已经能直接改 Cookie 值，所以服务器部署后，这个维护动作会简单很多。

## 最后结论

如果你现在要的是：

- 电脑关机也继续监视
- 手机上随时改关键词
- 通知持续可用

那就不要继续投入在本机方案上了，直接部署到 Linux 服务器。

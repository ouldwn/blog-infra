# 个人博客系统 · 独立开发与运维

线上地址：https://smzyg.xyz　|　技术栈：Ubuntu 22.04 / Docker Compose / Nginx / MySQL 8 / Flask / gunicorn / Prometheus / Grafana / Python

## 架构
公网 ──HTTPS──> Nginx(80/443) ──反代──> Flask+gunicorn(2 worker) ──> MySQL
│ 服务名 DNS 互访，仅 80/443/3000 对外
└─ /static/ 直接响应（7d 缓存）

旁路：crontab ×3（每日备份 / 5min 巡检+微信告警 / 每周证书续期）
监控：Prometheus ← node-exporter + cadvisor ；Grafana(3000) 可视化

## 已实现

- **安全基线**：非特权用户 + sudo、ufw 默认拒绝入站、SSH 密钥登录并禁用 root/密码
- **容器化**：7 服务 compose 编排；数据命名卷持久化；healthcheck + service_healthy 控制启动顺序；MySQL/应用端口不对公网暴露；镜像固定版本；容器日志 max-size 轮转
- **自动化**：mysqldump 备份（--single-transaction + gzip + 7 天保留 + 恢复演练）；Python 巡检（磁盘/内存/容器/HTTP 端到端/备份新鲜度）；PushPlus 微信告警（30min 冷却 + 恢复通知）；certbot webroot 自动续期
- **Web**：Nginx 反代 + HTTP→HTTPS 301 + Let's Encrypt；静态资源 Nginx 直出；XSS 转义；gunicorn 替代开发服务器；数据库连接 try/finally 归还

## 排错案例集

| # | 现象 | 定位过程 | 根因 | 修复 |
|---|------|---------|------|------|
| 1 | `up` 报 `volumes.app additional properties not allowed` | 报错路径含 `volumes.` | YAML 缩进把 app 放进了顶层 volumes 块 | 改缩进；养成 `docker compose config` 先验再启动 |
| 2 | prometheus 无限重启，日志 `prometheus.yml: no such file` | 日志→容器内路径→对比默认启动命令 | `command:` 是**替换**默认 CMD，把 `--config.file` 顶掉了 | command 写全参数；先 `docker inspect` 看镜像默认 Cmd |
| 3 | 域名 NXDOMAIN，但权威 DNS 能查到记录 | `whois` 看状态 + `dig NS` 委派为空 | 新域名实名后 NS 委派未同步（addPeriod） | 等同步；学会用 `dig @权威` 分层定位 |
| 4 | certbot 验证 404 | 手动放 probe.txt 走一遍验证链路 | 所有请求被 proxy_pass 给 Flask，ACME 路径没兜住 | 80 块加 `location /.well-known/acme-challenge/` 指共享卷 |
| 5 | certbot `EOFError` | 报错首行提示无终端 | cron/容器场景无交互，ToS 弹窗等不到输入 | `--non-interactive --agree-tos -m`；无人值守脚本必须全非交互 |
| 6 | https 不通：`Connection refused` | refused≠timeout → 排除防火墙；本机 curl localhost 也不通；容器内 443 在听 | **容器内监听 ≠ 宿主机端口可达**，compose 漏了 `443:443` 映射 | 加映射并重建；分层排查：容器→宿主机→ufw→安全组 |
| 7 | nginx 容器里没有 openssl/ps | — | alpine/slim 精简镜像无工具 | 宿主机 openssl 查证书、`docker top` 看进程；排查手段不依赖容器内 shell |
| 8 | heredoc 插数据报 `Access denied` | 密码提示"吃"了 SQL 行 | `mysql -p` 交互读密码与 stdin 管道冲突 | `sh -c '... -p"$MYSQL_PASSWORD"'`，密码从容器环境变量取 |
| 9 | 网站 500，但容器状态 Up | `logs app` 读 traceback 末行 | `NameError: escape`（import 漏写）；运行时才炸 | 改完 `py_compile` 预检；生产代码 review import |
| 10 | cron 告警日志出现 `SKIP notify`，手动跑正常 | 对比 cron 日志与手动输出 | cron 环境极简：source 的变量不 export 给子进程 | 脚本内自解析 .env（setdefault）；用 `env -i` 模拟 cron 验证 |
| 11 | HTTPS 上线后 http 检查恒为 301 误报 | 看 cron 日志 status 值 | 检查逻辑没跟上架构变更（80 已改跳转） | 检查改走 `https://localhost` + `-k`；**监控要随架构演进** |
| 12 | XSS：数据库标题被当 HTML 执行 | 插入 `<script>` 实测弹窗 | 输出未转义 | `markupsafe.escape`；同时修复 `with get_db()` 不 close 导致的连接泄漏 |

## 经验总结

- 排错口诀：**refused=没人听，timeout=被拦了**；本机通外网通不通→查防火墙/安全组；容器内通宿主机不通→查端口映射
- 备份的铁律：没做过恢复演练的备份等于没有；监控"产物是否产生"而不是"任务是否执行"
- 告警要冷却+分级，否则三周后必然告警疲劳
- 配置进仓库、密钥进 .env（gitignore）；改配置先静态校验（compose config / nginx -t / promtool / py_compile）再热生效

## 已知不足

备份与服务器同机（待同步 OSS）；无 CI/CD（手动 build）；单点无冗余；告警仅覆盖 5 项基础指标

## 快速复现

```bash
git clone <本仓库> && cd blog
cp .env.example .env   # 填入密码与 PUSHPLUS_TOKEN
docker compose up -d --build
# crontab -e 添加：备份(每日3点) / 巡检(5min) / certbot续期(每周一)


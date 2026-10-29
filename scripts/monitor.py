#!/usr/bin/env python3
"""服务器巡检 + 告警推送（含冷却与恢复通知）"""
import subprocess, shutil, time, os, glob, json
import urllib.request
from datetime import datetime

LOG = os.path.expanduser("~/blog/backups/monitor.log")
STATE = os.path.expanduser("~/blog/backups/monitor.state")
BACKUP_DIR = os.path.expanduser("~/blog/backups")
COOLDOWN = 1800          # 同一故障 30 分钟内只告警一次

def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def notify(title, content):
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        log("SKIP notify: PUSHPLUS_TOKEN 未注入")
        return
    body = json.dumps({"token": token, "title": title, "content": content}).encode()
    req = urllib.request.Request(
        "https://www.pushplus.plus/send", body,
        {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            log(f"NOTIFY -> {r.status} {r.read().decode()[:80]}")
    except Exception as e:
        log(f"NOTIFY failed: {e}")

def check(name, ok, detail, problems):
    log(f"{'OK  ' if ok else 'ALERT'} {name}: {detail}")
    if not ok:
        problems.append(f"{name}: {detail}")

def main():
    problems = []

    du = shutil.disk_usage("/")
    check("disk", du.used / du.total < 0.85,
          f"{du.used / du.total * 100:.1f}% used", problems)

    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k] = int(v.split()[0])
    mem = (1 - info["MemAvailable"] / info["MemTotal"]) * 100
    check("memory", mem < 90, f"{mem:.1f}% used", problems)

    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout.split()
    need = {"nginx", "mysql", "app", "prometheus", "grafana",
            "node-exporter", "cadvisor"}
    check("containers", need <= set(out),
          f"missing={sorted(need - set(out)) or 'none'}", problems)

    r = subprocess.run(["curl", "-ks", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "5", "https://localhost/"],
                       capture_output=True, text=True)
    check("http", r.stdout.strip() == "200", f"status={r.stdout.strip()}", problems)

    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "blog_*.sql.gz")))
    fresh = bool(files) and (time.time() - os.path.getmtime(files[-1])) < 25 * 3600
    check("backup", fresh,
          f"latest={os.path.basename(files[-1]) if files else 'NONE'}", problems)

    # ---- 告警逻辑：冷却 + 恢复通知 ----
    last = 0.0
    if os.path.exists(STATE):
        try:
            last = float(open(STATE).read().strip())
        except ValueError:
            last = 0.0

    if problems:
        if time.time() - last > COOLDOWN:
            notify(f"[ALERT] 博客服务器 {len(problems)} 项异常",
                   "主机: iZj6ccp283r53zufr3r6jaZ\n\n" + "\n".join(problems))
            open(STATE, "w").write(str(time.time()))
        else:
            log("告警冷却中，跳过重复推送")
    elif last:
        notify("[RECOVER] 博客服务器已恢复", "所有检查项恢复正常")
        os.remove(STATE)

if __name__ == "__main__":
    main()

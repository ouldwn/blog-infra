#!/usr/bin/env python3
"""服务器巡检：磁盘/内存/容器/HTTP/备份新鲜度，异常写 ALERT 日志"""
import subprocess, shutil, time, os, glob
from datetime import datetime

LOG = os.path.expanduser("~/blog/backups/monitor.log")
BACKUP_DIR = os.path.expanduser("~/blog/backups")

def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def check(name, ok, detail):
    log(f"{'OK  ' if ok else 'ALERT'} {name}: {detail}")
    return ok

def main():
    problems = 0

    # 1) 磁盘使用率
    used = shutil.disk_usage("/").used / shutil.disk_usage("/").total * 100
    problems += not check("disk", used < 85, f"{used:.1f}% used")

    # 2) 内存使用率
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k] = int(v.split()[0])
    mem = (1 - info["MemAvailable"] / info["MemTotal"]) * 100
    problems += not check("memory", mem < 90, f"{mem:.1f}% used")

    # 3) 三个容器都活着吗
    out = subprocess.run(["docker", "ps", "--filter", "name=nginx",
                          "--filter", "name=mysql", "--filter", "name=app",
                          "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout.split()
    need = {"nginx", "mysql", "app"}
    problems += not check("containers", need <= set(out),
                          f"running={out}")

    # 4) 网站真的能响应吗（端到端检查，比看进程强）
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "5", "http://localhost/"],
                       capture_output=True, text=True)
    problems += not check("http", r.stdout.strip() == "200",
                          f"status={r.stdout.strip()}")

    # 5) 备份新鲜度：最近 25 小时内必须有新备份（cron 挂了这里就报警）
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, "blog_*.sql.gz")))
    fresh = files and (time.time() - os.path.getmtime(files[-1])) < 25 * 3600
    problems += not check("backup", bool(fresh),
                          f"latest={files[-1] if files else 'NONE'}")

    if problems:
        log(f"SUMMARY: {problems} 项异常")

if __name__ == "__main__":
    main()


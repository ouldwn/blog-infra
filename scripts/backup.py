#!/usr/bin/env python3
"""MySQL 自动备份：mysqldump -> gzip -> 保留最近 7 天"""
import subprocess, datetime, gzip, os, glob

BACKUP_DIR = os.path.expanduser("~/blog/backups")
KEEP_DAYS = 7

def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = os.path.join(BACKUP_DIR, f"blog_{ts}.sql.gz")

    # 在 mysql 容器内执行 mysqldump，密码用容器自带的环境变量，脚本里零明文
    dump = subprocess.run(
        ["docker", "exec", "mysql", "sh", "-c",
         'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction blog'],
        capture_output=True, text=True,
    )
    if dump.returncode != 0:
        print("备份失败:", dump.stderr)
        raise SystemExit(1)

    with gzip.open(outfile, "wt") as f:
        f.write(dump.stdout)
    size = os.path.getsize(outfile)
    print(f"备份完成: {outfile} ({size} bytes)")

    # 清理过期备份
    cutoff = datetime.datetime.now() - datetime.timedelta(days=KEEP_DAYS)
    for path in glob.glob(os.path.join(BACKUP_DIR, "blog_*.sql.gz")):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        if mtime < cutoff:
            os.remove(path)
            print(f"已清理过期备份: {path}")

if __name__ == "__main__":
    main()

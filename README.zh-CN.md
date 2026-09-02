[English](README.md) | 简体中文

# guacamole_patch

这是针对 **Apache Guacamole 1.6.0** 的非官方下游补丁，重点改善浏览器切换标签页、页面长时间进入后台或恢复后出现的键盘与输入法失效问题。

本仓库不是 Apache Software Foundation 官方发布版本。

## 快速部署

拉取已经构建好的镜像：

```bash
docker pull ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2
```

在 Docker Compose 中使用：

```yaml
services:
  guacamole:
    image: ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2
```

只更新 Guacamole Web 容器：

```bash
docker compose pull guacamole
docker compose up -d --force-recreate --no-deps guacamole
docker compose ps
docker compose logs --tail=100 guacamole
```

Docker 会复用没有变化的镜像层，后续拉取通常只下载发生变化的部分。不要执行 `docker compose down -v`，也不要删除数据库卷。

## 镜像标签

- `1.6.0-recovery2`：本补丁包对应的当前具名恢复版本。
- `1.6.0-recovery1`：保留用于回滚的上一恢复版本。
- `1.6.0`：当前滚动发布镜像，每次正式构建都会更新这个标签。
- `main`：由 `main` 分支最新代码构建。
- `sha-<commit>`：对应特定源码提交的固定标签，适合精确部署和回滚。
- `dev`：由 `dev` 分支构建的开发镜像。

正式发布请选择 `main` 运行工作流。选择 `dev` 时也会更新共用的 `1.6.0` 标签。

## 修复内容

### 本机输入法 + Guacamole 文本输入

```text
远程 Windows：ENG
Guacamole 输入方式：文本输入
本机：中文输入法
```

补丁会处理浏览器遗漏的输入法合成结束事件，恢复当前远程连接的焦点以及文字、Backspace、Delete 的发送，并防止隐藏的原始键盘输入框抢占可见文本框焦点。

### 远程 Windows 微软拼音

```text
Guacamole 输入方式：无（None）
本机输入语言：ENG 或本机输入法
远程 Windows：微软拼音
RDP 键盘布局：en-us-qwerty
```

补丁会在页面隐藏时重置按键状态，返回页面后恢复键盘捕获，释放可能卡住的修饰键，处理长时间后台冻结和页面生命周期事件，并在首次操作时重建 Chromium 原生输入上下文。

仍可通过 `Ctrl+Alt+K` 或菜单中的“重新捕获键盘”进行手动恢复。

### 短暂网络提示

Guacamole 原本在大约 1.5 秒未收到隧道数据后就把连接标记为不稳定。补丁会额外确认 3 秒，只有页面可见且异常持续存在时才显示提示；页面隐藏期间不显示，返回页面后重新开始确认。

底层不稳定检测和 15 秒接收超时保持不变。真实且持续的网络或服务器故障仍会正常提示并断开连接。

发生过确认的网络异常后，网络数据稳定恢复 5 秒时会自动仅重建受影响的远程连接。短期内第二次异常使用 10 秒退避，连续自动尝试最多两次；稳定运行一分钟后重置尝试次数。

隧道再次不稳定、存在进行中的文件传输或用户选择“保留当前连接”时，会取消待执行的自动重连。达到自动尝试上限或控制仍然卡顿时仍可手动“重新连接”。Guacamole 登录态、页面地址和未受影响的平铺连接都会保留。

### 弱网下的鼠标响应

高频鼠标移动会以大约 30 Hz 合并为最新坐标。按下、松开、右键、滚轮和拖拽结束事件会先刷新最后坐标并立即发送，避免点击排在过期移动事件之后。连接被替换时会丢弃旧连接尚未发送的移动。

## GitHub Actions 构建

进入 **Actions → Build and publish Guacamole recovery image → Run workflow**，选择 `main` 后运行。

构建成功会发布：

```text
ghcr.io/trilogys/guacamole_patch:1.6.0
ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2
ghcr.io/trilogys/guacamole_patch:main
ghcr.io/trilogys/guacamole_patch:sha-<commit>
```

## 手动构建

需要：

```text
Docker
curl
patch
Python 3
tar
sha256sum
mktemp
```

克隆并构建：

```bash
git clone https://github.com/trilogys/guacamole_patch.git
cd guacamole_patch

IMAGE_NAME="ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2" \
bash ./build.sh
```

排错时可以使用较快的构建参数：

```bash
MAVEN_ARGUMENTS="-T 1C -Dmaven.test.skip=true" \
IMAGE_NAME="ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2" \
bash ./build.sh
```

`build.sh` 会验证补丁包和 Apache 源码压缩包、运行回归检查、试应用并正式应用补丁、使用官方 Dockerfile 构建镜像、检查镜像并执行 `initdb` 冒烟测试。

## 验证镜像

```bash
docker image inspect ghcr.io/trilogys/guacamole_patch:1.6.0-recovery2 \
  --format '{{index .Config.Labels "io.guacamole.recovery.patch-sha256"}}'
```

预期补丁 SHA-256：

```text
2ca476a390419888796cc589c16325f8aab8591e81eb04d71451b447eba82f80
```

## 验收测试

完整步骤见 [TEST_MATRIX.md](TEST_MATRIX.md)。至少验证：

- 本机中文输入法、远程 Windows 为 ENG 时的输入；
- 远程微软拼音的候选和选词；
- Chrome 和 Edge 中反复切换标签页；
- Ctrl、Shift、Alt 不会卡键；
- Backspace、Delete、方向键、Enter 和数字选词；
- 同一账号断开后重新连接；
- 能够回滚到已知正常镜像。

## 影响范围与限制

补丁不修改 `guacd`、PostgreSQL 数据结构和数据、Nginx、FRP、连接账号、录像或共享目录。

`Win+Space`、`Alt+Tab` 等快捷键可能被本机操作系统或浏览器拦截。正式部署前仍需在实际 Windows RDP 环境中完成验收。

## 许可证

本补丁包遵循 Apache License 2.0。Apache Guacamole 的版权和 NOTICE 要求保持不变。

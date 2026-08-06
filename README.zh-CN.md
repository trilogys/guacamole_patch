[English](README.md) | 简体中文

# Apache Guacamole 1.6.0 输入法修复 v7

这是针对 **Apache Guacamole 1.6.0** 的非官方下游补丁候选版，修复浏览器切换标签页后两类输入问题：

1. Guacamole“文本输入”模式中，中文停留在左下角、无法进入远程输入框，或 Backspace/Delete 失效；
2. Guacamole 输入方式为“无（None）”时，远程 Windows 微软拼音或普通键盘在切换标签页后失效。

> 请只使用镜像标签 `trilogys/guacamole:1.6.0`。

## 适用模式

### 模式 A：本机输入法 + Guacamole 文本输入

```text
远程 Windows：ENG
Guacamole 输入方式：文本输入
本机：中文输入法
```

处理内容：

- 浏览器遗漏 `compositionend` 后解除卡死；
- 兼容 `input` 与 `compositionend` 的不同事件顺序；
- 恢复当前远程连接的键盘焦点；
- 恢复文字、Backspace 和 Delete 的发送；
- 防止隐藏的原始键盘 `InputSink` 抢走左下角可见文本框焦点。

### 模式 B：远程 Windows 微软拼音

```text
Guacamole 输入方式：无（None）
本机输入语言：ENG 或本机输入法
远程 Windows：微软拼音
RDP 键盘布局：en-us-qwerty
```

处理内容：

- 禁止隐藏的原始键盘输入框接收本机输入法合成文本，由远程系统的中英文状态决定最终输入；
- 标签页隐藏时重置 Guacamole 记录的按键状态；
- 标签页返回时恢复当前远程连接的键盘焦点；
- 重新聚焦隐藏的原始键盘输入捕获器；
- 显式释放 AltGr、Shift、Ctrl、Alt、Meta、Windows/Super 和 Hyper；
- 合并短时间内重复发生的 `focus` 与 `visibilitychange`；
- 处理长时间后台冻结以及 `freeze`、`resume`、`pageshow` 页面生命周期；
- 在切回后的鼠标、触摸、点击或首次按键中同步重建 Chromium 原生输入上下文；
- 将 `Ctrl+Alt+Shift` 作为独立恢复入口并保持侧边菜单开关语义；
- 提供 `Ctrl+Alt+K` 和菜单“重新捕获键盘”手动恢复入口；
- 不抢占 Guacamole 登录框、设置框、按钮、链接和可编辑元素。

## 构建前提

服务器需要：

```text
Docker
curl
patch
Python 3
tar
sha256sum
mktemp
```

Node.js 不是必需项；存在时会额外执行修改文件的 JavaScript 语法检查。

## 构建

```bash
sudo apt-get update
sudo apt-get install -y curl patch python3

tar -xzf guacamole-ime-fix-v7-1.6.0.tar.gz
cd guacamole-ime-fix-v7
sha256sum -c ../guacamole-ime-fix-v7-1.6.0.tar.gz.sha256
./build.sh
```

默认镜像：

```text
trilogys/guacamole:1.6.0
```

`build.sh` 会：

1. 校验补丁包内部所有文件；
2. 锁定 Guacamole 版本为 1.6.0；
3. 运行作用域、模式隔离、竞态和状态回归检查；
4. 下载 Apache 官方源码并验证 SHA-256；
5. 在真实源码上执行 `patch --dry-run`；
6. 应用补丁并检查修改后的源文件；
7. 使用官方 Dockerfile 构建，默认运行上游 Maven/前端测试；
8. 检查镜像并执行 `initdb` 冒烟测试；
9. 输出镜像 ID 和补丁 SHA-256。

资源不足时可临时跳过上游测试，仅用于排错：

```bash
MAVEN_ARGUMENTS=-DskipTests=true ./build.sh
```

正式部署应使用默认值。

### 可选构建参数

```bash
IMAGE_NAME=trilogys/guacamole:1.6.0 ./build.sh
WORK_DIR=/var/tmp ./build.sh
KEEP_WORK_DIR=true ./build.sh
PULL_BASE_IMAGES=true ./build.sh
```

`WORK_DIR` 仅作为临时目录的父目录。脚本会在其中创建独立随机子目录，不会直接删除用户提供的目录。

默认不强制 `--pull`，避免每次重建都无意改变基础镜像。首次构建仍可能从镜像仓库获取官方 Dockerfile 指定的基础镜像，因此完整位级可复现性仍取决于基础镜像是否已固定到本地。

## 接入现有 Compose

将 `docker-compose.override.yml` 放到原 Compose 项目目录：

```yaml
services:
  guacamole:
    image: trilogys/guacamole:1.6.0
```

然后执行：

```bash
docker compose config
docker compose up -d --force-recreate guacamole
docker logs --tail=100 guacamole_compose
```

`docker-compose.override.yml` 是默认配置，始终使用 v7。官方 1.6.0 镜像保存在
`docker-compose.official.yml` 中，仅作为备用：

```bash
# Default: v7
docker compose up -d --force-recreate guacamole

# Fallback: official Apache Guacamole 1.6.0
docker compose -f docker-compose.yml -f docker-compose.official.yml \
  up -d --force-recreate guacamole
```

此补丁不修改：

```text
guacd
PostgreSQL 数据结构和数据
Nginx
FRP
连接账号
录像和共享目录
```

首次打开新镜像后执行一次强制刷新：

```text
Ctrl + F5
```

## 必做验收

详细步骤见 `TEST_MATRIX.md`。至少完成：

- Chrome/Edge 中两种输入模式各切换标签页 20 次；
- 按住 Ctrl、Shift、Alt 后切出，切回后确认远端没有卡键；
- 中文候选、数字选词、Backspace、Delete、方向键、Enter；
- Guacamole 菜单、登录框和设置框不会被抢焦点；
- 同一账号断开重连后仍正常；
- 回滚到官方镜像成功。

## 已知边界

- `Win+Space`、`Alt+Tab` 等快捷键可能被本机系统或浏览器截获；切换远程输入法建议点击远程任务栏语言图标。
- 尚未在你的真实 Windows RDP 会话中完成端到端验证。
- iframe、移动端 WebView、多连接同时选中、非 Chrome/Edge 浏览器需要单独验收。
- 此包未附带预构建镜像、镜像签名、SBOM 或漏洞扫描结果。

## 回滚

```yaml
services:
  guacamole:
    image: guacamole/guacamole:1.6.0
```

```bash
docker compose up -d --force-recreate guacamole
```

由于没有数据库迁移，回滚不需要恢复数据库。

## 许可证

本补丁包遵循 Apache License 2.0。Apache Guacamole 的版权和 NOTICE 要求保持不变。此包不是 Apache Software Foundation 官方发布。

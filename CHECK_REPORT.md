# Guacamole 输入法修复 v5 多角度审计报告

## 总体结论

v5 可以作为**受控环境部署候选版**，但在真实 Chrome/Edge → Guacamole → RDP → Windows 微软拼音链路验收通过前，不应称为已完成生产认证的正式版本。

## 对 v3 的新增发现

| 严重度 | 发现 | 影响 | v5 处理 |
| --- | --- | --- | --- |
| 高 | 全局隐藏 `InputSink` 不知道当前是否为“文本输入”模式 | 返回标签页时可能抢走左下角文本框焦点，导致两种修复互相干扰 | 新增焦点所有权事件；文本输入组件可阻止隐藏输入框接管并重新聚焦可见 textarea |
| 高 | `WORK_DIR` 被当成可直接删除的构建目录 | 用户误设环境变量时可能递归删除已有目录 | `WORK_DIR` 改为父目录，只清理 `mktemp` 创建的随机子目录 |
| 中 | 补丁头使用假的新 Git blob 哈希 | `git apply --index` 不可信，包的专业性和可审计性下降 | 删除所有伪造 `index` 行，保留标准 unified diff |
| 中 | 默认 `docker build --pull` | 相同源码和补丁在不同日期可能得到不同基础镜像 | 默认不强制拉取；可通过 `PULL_BASE_IMAGES=true` 显式启用 |
| 中 | 镜像使用 `guacamole/guacamole` 官方命名空间样式 | 容易误解为 Apache/官方镜像 | 默认改为 `local/guacamole` |
| 中 | 缺少 LICENSE 全文和完整修改声明 | 再分发合规信息不完整 | 加入 Apache License 2.0 和扩展 NOTICE |
| 低 | 构建脚本未主动验证包内文件 | 文件损坏可能到后续阶段才暴露 | 构建开始即验证 `SHA256SUMS` |
| 低 | 构建后没有镜像级冒烟检查 | 只知道 Docker build 返回成功 | 增加 image inspect 和 initdb 冒烟测试 |

## 功能与事件生命周期

### 文本输入模式

审计覆盖：

- `compositionstart` 后切换标签页且浏览器不发送 `compositionend`；
- `input` 先于 `compositionend`；
- `compositionend` 后正常 `input`，避免重复发送；
- 标签页返回时清空失效组合状态；
- Backspace/Delete 经统一输入处理函数发送；
- 文本 textarea 与隐藏 InputSink 的焦点所有权协调。

尚需真实浏览器确认：不同输入法版本是否存在跨任务延迟的最终 `input` 事件，从而产生极低概率重复提交。

### 远程微软拼音模式

审计覆盖：

- `window.blur` 缺失时使用 `visibilitychange`；
- 隐藏时取消待执行的恢复任务；
- `focus` 与 `visibilitychange` 同时触发时合并恢复；
- 恢复前后检查页面可见性、窗口焦点、登录状态、活动连接和本地表单焦点；
- 先恢复 ManagedClient 焦点，再释放远端修饰键；
- 文本模式拦截隐藏 InputSink 的焦点接管。

## Angular 作用域与事件可达性

上游 `index.html` 将 `indexController` 挂在整个 `<html>` 根节点，远程客户端位于其 `ng-view` 子树；“文本输入”组件通过 `ng-if="showTextInput"` 仅在文本模式下创建。因此：

- `indexController` 的 `$scope.$broadcast()` 可以向下到达当前远程页面和 `guacTextInput` 隔离作用域；
- 文本模式存在时会拦截焦点恢复事件；
- 输入方式为“无”时该组件不存在，隐藏 `InputSink` 正常接管；
- 后台连接面板只显示缩略图，不包含第二个 `guacTiledClients` 输入处理实例。

这消除了 v5 焦点所有权协议依赖错误作用域的风险。

## 多连接场景

`ManagedClientGroup.verifyFocus()` 只会在没有任何连接被选中时选择第一个连接。若用户有多个同时聚焦的连接，固定修饰键释放事件可能发往所有已聚焦连接。这通常是安全的，但多连接广播行为尚未进行真实 RDP 验证。

正式单用户部署建议每个页面只连接一台主机；多连接选择属于额外验收项。

## 浏览器与平台兼容

使用的 API：

```text
document.hidden
document.hasFocus()
visibilitychange
window focus
activeElement
getBoundingClientRect()
querySelector()
isContentEditable
setTimeout/clearTimeout
```

这些 API 在现代 Chrome、Edge 和 Firefox 中普遍存在。尚未验证：

```text
Safari
Android WebView
iOS WebView
iframe 嵌入
浏览器节能/冻结标签页
远程桌面全屏退出后的事件顺序
```

## 安全审计

运行时补丁：

- 不增加网络请求；
- 不读取账号、密码、剪贴板或远程画面内容；
- 不使用 `eval`、动态脚本或第三方运行时依赖；
- 只广播固定按键释放事件；
- 对本地可见表单和可编辑元素进行焦点保护。

构建链路：

- Apache 源码通过 HTTPS 下载，并使用固定 SHA-256 校验；
- 包内文件使用 SHA-256 清单检查；
- 基础容器镜像和 apt 软件包仍未固定到内容摘要，因此不是完全可复现构建；
- 未生成 SBOM、镜像签名或 CVE 扫描报告。

## 数据与回滚

补丁仅修改 Guacamole Web 客户端 JavaScript。它不执行数据库迁移，不修改 PostgreSQL、guacd、FRP 或连接配置。

回滚只需恢复官方 `guacamole/guacamole:1.6.0` 镜像并重建 `guacamole` 服务。数据库不需要回滚。

## 构建与包质量

已检查：

- Bash 严格模式与语法；
- 安全临时目录；
- 版本锁定；
- 包内完整性；
- 官方源码哈希；
- unified diff hunk 结构；
- 稀疏上游源码 dry-run 和实际应用；
- 修改后关键变量作用域；
- 文本/原始键盘模式隔离；
- Compose 覆盖文件；
- 许可证和 NOTICE；
- 镜像标签和 OCI 标签配置。

未在当前环境完成：

- 完整 Docker 构建；
- Maven/Firefox 上游测试实际执行；
- 镜像 initdb 冒烟实际执行；
- 真实 RDP 端到端输入法测试；
- 漏洞扫描、SBOM 和镜像签名。

这些步骤由 `build.sh` 在具备 Docker 和联网条件的服务器上继续执行。

## 发布判定

当前判定：

```text
代码审查：通过（存在端到端验证边界）
包结构：通过
构建脚本安全：通过静态检查
许可证信息：通过
运行时安全设计：通过静态检查
真实浏览器/RDP 验证：待完成
生产认证：未完成
```

---
name: init
description: 一键检查并修复 /bug 技能所需的三个 MCP（PingCode / Kibana / Yearning）。自动诊断"未安装 / 已安装未注册 / 认证过期"三种状态，引导用户完成 Cookie 刷新或首次安装。触发命令：/init
user-invocable: true
---

# init 技能

## 核心目标

让任何团队成员在一条指令内完成环境就绪，或快速定位哪个 MCP 的 Cookie 过期了。

---

## 执行流水线

### 总览

对三个 MCP 逐一执行"诊断 → 修复"循环，最后输出状态汇总。

```
/init
  ├── 诊断 PingCode MCP → 修复（如需）
  ├── 诊断 Kibana MCP   → 修复（如需）
  ├── 诊断 Yearning MCP → 修复（如需）
  └── 输出最终状态汇总
```

若任何步骤执行了 `claude mcp add`，**告知用户重启 Claude Code**，修复后重新执行 `/init` 验证。

---

## 诊断状态定义

每个 MCP 只有四种状态，对号入座：

| 状态 | 判断依据 | 处置 |
|------|---------|------|
| ✅ **正常** | 工具调用返回业务数据 | 跳过，继续下一个 |
| 🔐 **认证过期** | 工具调用返回 401/403/未授权/token invalid | 刷新 Cookie/Token（见各节） |
| ⚙️ **已编译未注册** | 编译产物存在，但工具不响应 | 执行 `claude mcp add`（见各节） |
| 📦 **未安装** | 编译产物不存在 | 执行安装流程（见各节） |

---

## 一、PingCode MCP 诊断与修复

### 1.1 诊断

```bash
# 检查编译产物
ls ~/.codex/mcpserver/pingcode/dist/index.js 2>/dev/null && echo "已编译" || echo "未编译"
```

再尝试调用工具：`pingcode_get_workitems`（传入任意 identifier，如 `SUN-1`）。

### 1.2 状态处置

#### 📦 未安装

```bash
cd ~/.codex/mcpserver
git clone https://github.com/shaunxu/pingcode-mcp-server.git pingcode
cd pingcode && npm install && npm run build
```

编译完成后，`src/util.ts` 已有 Cookie 补丁（支持 `PINGCODE_COOKIES` 环境变量）。若是全新克隆，需确认补丁已应用（检查 `request()` 函数是否读取 `process.env.PINGCODE_COOKIES`）。

#### ⚙️ 已编译未注册 / 🔐 认证过期

PingCode 自建版无法生成 Open API Token，需从浏览器 Network tab 获取 Bearer token：

**引导用户操作（AI 无法代劳）：**

```
1. 在 Chrome 打开已登录的 https://pingcode.dx268.com
2. F12 → Network 标签 → 勾选 XHR/Fetch
3. 刷新页面，点击任意工单
4. 找到任一 /open-api/v1/ 请求
5. Headers → 找 Authorization: Bearer <token>
6. 复制 Bearer 后面的完整 token 值，粘贴到下方命令后执行：
```

```bash
claude mcp remove pingcode 2>/dev/null
claude mcp add pingcode node -s user \
  -e PINGCODE_OPEN_API_ENDPOINT=https://pingcode.dx268.com/open-api/v1 \
  -e "PINGCODE_OPEN_API_ACCESS_TOKEN=<粘贴token>" \
  -- ~/.codex/mcpserver/pingcode/dist/index.js
```

> token 有效期约数小时至数天，过期时重复此操作即可。

---

## 二、Kibana MCP 诊断与修复

### 2.1 诊断

```bash
which mcp-server-kibana 2>/dev/null && echo "已安装" || echo "未安装"
```

再尝试调用工具：`mcp__kibana__get_status`。

### 2.2 状态处置

#### 📦 未安装

```bash
npm install -g @tocharianou/mcp-server-kibana
```

#### ⚙️ 已安装未注册 / 🔐 Cookie 过期

Kibana 使用 SSO Cookie 认证，需从 Chrome 提取。AI 执行以下步骤：

**步骤 1：获取 Chrome 加密密钥**

```bash
security find-generic-password -w -s "Chrome Safe Storage"
```

输出的字符串即为 AES 加密密钥的原材料。

**步骤 2：读取 Chrome Cookie 数据库**

macOS Cookie 数据库位置（按顺序尝试）：

```bash
ls ~/Library/Application\ Support/Google/Chrome/Default/Cookies
ls ~/Library/Application\ Support/Google/Chrome/Profile\ 1/Cookies
```

**步骤 3：提取并解密目标 Cookie**

需要两个 Cookie：
- **auth_pro**：来自 SSO 域（如 `.dxit999.com`）
- **sid**：来自 Kibana 域（如 `new-dev-eslog.dxit999.com`）

解密规范（Chrome v80+ AES-CBC 加密）：

```python
# 伪代码，AI 生成实际 Python 脚本执行
import sqlite3, hashlib, hmac
from Crypto.Cipher import AES

# 1. PBKDF2 派生密钥
key = hashlib.pbkdf2_hmac('sha1', password.encode(), b'saltysalt', 1003, dklen=16)

# 2. 从数据库读取 encrypted_value
# 3. 剥离前 3 字节前缀 "v10"
# 4. IV = b' ' * 16
# 5. AES-CBC 解密，去除 PKCS7 padding
# 6. 结果即为明文 Cookie 值
```

> **关键**：明文值前 32 字节是校验前缀，解密后须剥离，否则请求头含非法字符导致 401。

**步骤 4：注册**

```bash
claude mcp remove kibana 2>/dev/null
claude mcp add kibana mcp-server-kibana -s user \
  -e KIBANA_URL=https://new-dev-eslog.dxit999.com \
  -e "KIBANA_COOKIES=auth_pro=<解密值>; sid=<解密值>" \
  -e KIBANA_DEFAULT_SPACE=default \
  -e NODE_TLS_REJECT_UNAUTHORIZED=0
```

**验证**：重启后调用 `mcp__kibana__get_status`，返回 `status.overall.state: green` 即成功。

> Cookie 有效期通常 1～7 天，过期后重复步骤 1-4 即可。

---

## 三、Yearning MCP 诊断与修复

### 3.1 诊断

```bash
ls ~/.codex/mcpserver/yearning/dist/index.js 2>/dev/null && echo "已编译" || echo "未编译"
```

再尝试调用工具：`yearning_health_check`。

### 3.2 状态处置

#### 📦 未安装

向用户询问 zip 包路径，然后：

```bash
unzip <zip路径> -d ~/.codex/mcpserver/yearning
cd ~/.codex/mcpserver/yearning
npm install && npm run build
```

#### ⚙️ 已编译未注册

从 `~/.codex/config.toml` 读取 Yearning 配置（若存在），否则询问用户：

```bash
claude mcp remove yearning 2>/dev/null
claude mcp add yearning node -s user \
  -e YEARNING_URL=<值> \
  -e YEARNING_SOURCE_ID=<值> \
  -e YEARNING_USERNAME=<值> \
  -e YEARNING_PASSWORD=<值> \
  -- ~/.codex/mcpserver/yearning/dist/index.js
```

#### 🔐 认证过期（SSO Cookie）

若 Yearning 使用 SSO，需补充 `YEARNING_AUTH_PRO` Cookie：

1. 从 Chrome 提取 SSO 域的 `auth_pro`（同 Kibana 步骤 1-3，换域名）
2. 更新注册命令，追加 `-e YEARNING_AUTH_PRO=<解密值>`
3. 重新执行 `claude mcp add`

---

## 四、最终状态汇总输出

所有 MCP 处理完毕后，输出：

```
## 环境检查结果

| MCP        | 状态 | 备注 |
|------------|------|------|
| PingCode   | ✅ 正常 / 🔐 待刷新 / ⚙️ 待注册 / 📦 未安装 | ... |
| Kibana     | ✅ 正常 / ... | ... |
| Yearning   | ✅ 正常 / ... | ... |

<若有任何 mcp add 操作>
⚠️ 已更新 MCP 注册，请**重启 Claude Code**，然后重新执行 `/init` 确认生效。

<若全部正常>
✅ 环境就绪，可直接使用 `/bug <工单号或描述>` 开始排障。
```

---

## 约束

- `security find-generic-password` 输出的密钥不得打印到对话中
- Cookie 明文值不得出现在任何输出中（注册命令执行后立即清除变量）
- 解密脚本生成临时文件时，使用完毕后立即删除

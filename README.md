# 美的空调替换主板 SN 恢复插件

这是一个面向 Codex 的公开源码插件，用于在严格核对所有权、原机身份和实体换板证据后，离线生成“单设备、单维修事件、最多一条写请求”的 Windows 恢复包。

插件生成文件，但不会自动加入 Wi-Fi、连接空调或运行写入。真正的设备操作只能由设备所有者或获授权维修者在本机手动执行。

> [!IMPORTANT]
> 当前兼容性证据只覆盖空调型号 `KFR-26G/WXAA2@` 及本项目已审计的协议实现；即使型号相同，不同固件也可能不兼容。不要把“同样出现维修热点”视为其他型号、固件或产品类别也兼容。未验证组合只允许只读分析，不应生成写入包。SSID/BSSID 是现场绑定证据，不是设备的密码学认证。

> [!WARNING]
> 写入一旦被预留、开始发送或结果不明确，同一事件都不得重试。零响应、TCP 连接成功或 ACK 都不能证明写入成功或失败。

本项目不是美的官方售后工具，不隶属于或代表美的，也不能替代断电作业、电气安全、官方维修资格、云端绑定或售后服务。

## 适用范围

只有同时满足以下条件才可生成写入包：

1. 目标是本人拥有或明确获授权维修的美的空调。
2. 主板确实刚刚发生了一次新的实体更换。
3. 原机机身 SN 是可信来源提供的完整 22 位 ASCII 数字。
4. 当前新主板现场实时广播的热点精确匹配 `midea_test_<12 位十六进制字符>`。
5. 型号是当前公开版明确支持的型号，且换板证据能对应到这台空调。
6. 同一 SN 或热点如果有历史，必须引用最近一次事件 ID，并提供后来再次实体换板的新证据。

以下情况必须拒绝：仅给一个 SN、猜号、从 32 位 App 显示值自动截取、复制另一台机器身份、批量写入、克隆、绕过账号/云绑定、修改端点或加入写入重试。

## 隐私说明

公开仓库只包含明显的合成测试值，例如：

```text
SN:   1234567890123456789012
SSID: midea_test_a1b2c3d4e5f6
```

这些值只用于离线测试，绝不能写入真实设备。公开源码中没有预装任何客户维修事件；真实事件只保存在使用者本机的追加式账本与生成包中，并已被 `.gitignore` 排除。

不要把真实 SN、SSID、BSSID、设备标签/二维码、客服凭证、家庭信息、日志、`TARGET.json`、ZIP 或 JSONL 账本上传到 Issue、Pull Request 或公开提交。

## 环境要求

- Windows 10 或 Windows 11；
- Python 3.10 或更高版本；
- Windows PowerShell 5.1 或更高版本；
- 仅在最终人工运行恢复包时需要无线网卡；
- Codex（用于审查证据、调用生成器和解释结果）。

协议自检仅使用 Python 标准库和 Windows 自带 PowerShell；如果已安装 `cryptography`，会优先使用它完成 AES 自检。

## 获取源码

```powershell
git clone https://github.com/625373155/midea-sn-board-restore.git
Set-Location midea-sn-board-restore
```

这个仓库本身就是插件源码。已经使用 Codex 本地插件/个人 marketplace 的用户可把它作为 `midea-sn-board-restore` 的源码目录。也可以在 Codex 中使用 `$skill-installer`，从本仓库的 `skills/midea-sn-board-restore` 子目录安装单个技能。

安装或更新插件后，请新建一个 Codex 任务再调用技能，让新任务加载最新版本。

## 在 Codex 中使用

新建任务后输入：

```text
使用 $midea-sn-board-restore。我要为刚更换的美的空调主板恢复原机 SN。
请先核对所有权、型号、SN 来源、新主板证据、现场热点和既有事件，再决定是否生成。
```

随后提供：

- 所有权或维修授权说明；
- 精确型号；
- 完整 22 位原机机身 SN 及来源类型；
- 一行、不包含第二个 SN 的来源凭证说明；
- 当前操作系统实时显示的精确服务热点；
- 可选的当前 BSSID；
- 本次实体新主板的证据说明；
- 如有历史，最近事件 ID 和后来再次换板的新证据。

Codex 必须先读取技能内的资格、安全、协议和结果分类规则。证据不足时只能解释或做只读分析，不能生成写入包。

## 开发者离线检查

以下命令都不会连接设备：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
py -3 skills\midea-sn-board-restore\scripts\protocol_reference.py --self-test
py -3 scripts\public_release_check.py
py -3 C:\path\to\skill-creator\scripts\quick_validate.py skills\midea-sn-board-restore
py -3 C:\path\to\plugin-creator\scripts\validate_plugin.py .
```

生成器参数说明：

```powershell
py -3 skills\midea-sn-board-restore\scripts\new_restore_package.py --help
```

生成器必须由已完成证据审查的 Codex 或开发者调用。下面只展示参数形状，尖括号内容必须替换为本次已核验的信息：

```powershell
py -3 skills\midea-sn-board-restore\scripts\new_restore_package.py `
  --sn <22位原机SN> `
  --ssid <当前精确维修热点> `
  --model KFR-26G/WXAA2@ `
  --sn-source customer-service `
  --sn-source-reference "<一行来源凭证说明>" `
  --new-board-evidence "<一行本次实体换板证据说明>" `
  --ownership-confirmed `
  --trusted-source-confirmed `
  --new-physical-board-confirmed `
  --output <空的输出父目录>
```

`--sn-source` 只能是 `customer-service`、`original-label`、`old-app` 或 `old-board`。如果本地账本发现相同 SN 或热点，生成器会拒绝普通调用；只有确实又更换了另一块实体主板时，才允许在独立复核新证据后增加：

```powershell
--previous-incident-id <最近事件ID> --later-physical-board-event-confirmed
```

确认标志只是明确声明，不等于证据。不得靠改写一句证据文本来伪造“新事件”。

## 生成物

每次成功生成会得到：

- 一个不可覆盖的设备包目录；
- 同名 ZIP；
- ZIP 的 `.sha256` 文件；
- 本机追加式生成历史。

生成器会在未锁定的包对外可见之前，先永久追加 `PACKAGE_GENERATION_RESERVED`。因此生成中断、输出丢失或遗留的 `history.lock` 都可能让该事件保持被占用；这属于保守安全设计。不要自动删除或绕过锁，只能人工核对本地账本和文件系统后决定后续处置。

设备包中包含：

| 文件 | 作用 | 是否可写 |
|---|---|---:|
| `00_READ_ME_FIRST.txt` | 先读摘要与目标身份 | 否 |
| `00_self_test.cmd` | 离线自检 | 否 |
| `01_query_only.cmd` | 只读 SN 查询 | 否 |
| `03_raw_read_only_diagnostic.cmd` | 单次原始只读诊断 | 否 |
| `02_restore_once_and_verify.cmd` | 唯一写入入口，最多发送一条写请求 | 是 |
| `04_post_write_read_only_check.cmd` | 断电重启后的只读复查 | 否 |
| `TARGET.json` | 目标、协议、安全门禁和文件哈希 | 否 |
| `midea_sn_restore.ps1` | 固定目标的运行时 | 仅由生成器产生 |

生成后必须连同 ZIP 一起校验：

```powershell
py -3 skills\midea-sn-board-restore\scripts\validate_package.py <设备包目录> --require-archive
```

校验器会检查模板逐字节一致性、`TARGET.json`、文件与 ZIP 哈希、固定端点、启动器分离、写入调用数量和 PowerShell 离线自检。仅修改包内哈希不能让手改脚本通过校验。

通过校验只说明“包与这个源码版本的模板和内部哈希一致”，不证明所有权或换板证据真实，也不是代码签名、可信发布者证明或官方授权。

## 现场使用顺序

1. 在未连接空调热点时运行 `00_self_test.cmd`。
2. 核对 `TARGET.json` 中的完整 SN、型号、热点、来源和事件 ID。
3. 连接且仅连接包中固定的现场维修热点。
4. 先运行 `01_query_only.cmd`。
5. 若完整性校验后的回复已是精确目标 SN，立即停止，不写。
6. 若收到可解码且有效的其他 SN，或完整性通过但无法解码的 SN 载荷，立即建立对应永久停止标记，不覆盖；后者交由授权维修复核。
7. 只有查询没有可用响应时才运行 `03_raw_read_only_diagnostic.cmd`；零响应只能说明“没有收到字节”，不能证明主板为空。
8. 所有证据仍成立时，写入口只运行一次，并逐字输入事件专用确认语。
9. 一旦创建写入预留或开始发送，无论 ACK、超时、报错还是零响应，都不得再次运行写入口。
10. 完全断电后再上电，运行只读复查并使用官方 App 验证。

## 结果如何解释

| 现象 | 能证明什么 | 下一步 |
|---|---|---|
| TCP 已连接 | 只证明建立了连接 | 继续按只读/一次性流程 |
| `RAW_RECEIVED_BYTES=0` | 没收到字节 | 不能据此判断空板或写入失败 |
| 收到 ACK | 只是一条确认数据 | 不能据此宣布成功 |
| 精确、完整性通过的目标 SN 读回 | 协议读回已验证 | 停止，永久不重写 |
| 冷启动后官方 App 显示匹配且控制正常 | 可支持 App 验证结果 | 保存证据，永久不重写 |
| `WRITE_RESULT_UNKNOWN` | 可能已写入，结果未知 | 只做只读复查，绝不重试 |
| 有效但不同的 SN | 身份冲突 | 停止并转官方/授权维修复核 |
| 完整性通过但 SN 无法解码 | 设备回复与已审计身份格式不一致 | 建立永久停止标记，不写，转授权维修复核 |

详细状态定义见 `skills/midea-sn-board-restore/references/outcome-classification.md`。

## 常见问题

### 为什么不能只给 SN？

因为 SN 本身不能证明所有权、目标设备、当前换板事件或现场主板。插件必须同时绑定可信来源、机型、实时热点和实体换板证据。

### App 显示 32 位数字怎么办？

不要自动去掉前后数字，也不要截取中间 22 位。App 表示关系可能随型号/固件变化；写入输入必须来自可信来源的原始 22 位机身码。

### 第一次没返回，能再运行写入吗？

不能。无响应无法证明请求没到达主板。一次事件的写入预留或发送发生后，必须按结果未知处理，只能冷启动、只读检查或找授权售后。

### 换了下一块新主板还能用吗？

可以把它作为全新的维修事件，但必须保留旧事件，提供后来实体换板的新证据、当前新热点和最近事件 ID。不能删除锁或复制旧包解锁。

### 本地锁是否绝对防篡改？

不是。它是减少误操作的本机软件保护，不是跨电脑的硬件 DRM。复制/修改公开源码可以绕开软件限制，因此授权、证据审核和“不重试”纪律仍然是核心安全边界。

## 安全边界

- 端点固定为 `192.168.1.1:6444`，产品类型固定为空调 `0xAC`。
- 只读入口在结构上不能构造 `0x41` 写操作。
- 写入口先创建包内和本机全局永久标记，再打开 TCP。
- 已校验但不可解码的身份回复会永久禁止该事件进入写入。
- 每个事件最多一个静态写调用，验证阶段只有只读查询。
- 包内目标不可作为运行时参数替换。
- 公开测试数据全部是合成身份；隐私扫描是发布阻断项。

完整规则见 [SECURITY.md](SECURITY.md)。

## 仓库结构

```text
.codex-plugin/plugin.json
.github/workflows/ci.yml
scripts/public_release_check.py
skills/midea-sn-board-restore/
├── SKILL.md
├── agents/openai.yaml
├── assets/package-template/
├── references/
└── scripts/
```

## 许可证

当前仓库尚未附加开源许可证。公开可见不等于自动授予再分发、商用或衍生作品许可；仓库所有者可在确定许可证后另行添加。

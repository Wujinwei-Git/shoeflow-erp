# ShoeFlow ERP Agent 第二阶段增量更新说明

本阶段把 Agent 从“只读查询”升级为“销售预览 + 人工确认执行”。用户用自然语言描述一笔销售后，系统自动匹配 SKU、读取库存和成本、计算销售额与毛利润；只有用户显式确认，才会创建正式销售单并扣减库存。

## 一、本阶段已经实现什么

- 继续支持 SKU、条码、实时库存和成本查询。
- 支持单个 SKU 的自然语言销售指令。
- 自动计算成交金额、销售成本、毛利润和扣减后库存。
- 生成可持久化的待确认操作，默认 15 分钟有效。
- 只有创建该操作的登录账号能够查看、确认或取消。
- 确认时再次锁定并核对库存、预留量和平均成本。
- 预览后数据一旦变化，旧预览失效，必须重新生成。
- 重复点击确认不会生成第二张销售单，也不会重复扣库存。
- 最终执行复用 ERP 原有销售服务，不允许模型直接写数据库。

目前没有向 Agent 开放入库、退货、库存校正、删除或直接改库存。聊天里输入“确认”也不会执行，必须调用确认接口；以后移动端会把这个接口接到确认按钮。

## 二、一次性合并和启动

先关闭正在运行的后端。把增量包内容复制到 `D:\shoeflow-erp`：文件夹选择“合并”，遇到同名文件选择“替换目标中的文件”。这不会删除原 `app` 目录里的其他文件，只会增加新文件并更新列出的同名文件。

不要删除或覆盖现有 `.env`。增量包中的 `.env.example` 只是配置示例。你的现有 `.env` 可以继续使用原数据库密码、JWT 密钥和 DeepSeek Key；可选地追加：

```env
AGENT_ACTION_EXPIRE_MINUTES=15
```

然后在 PyCharm 项目终端一次执行：

```powershell
cd D:\shoeflow-erp
.venv\Scripts\activate
alembic upgrade head
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

这次 `alembic upgrade head` 必须执行，因为新增了保存待确认操作的 `agent_actions` 表。测试正常时应看到 72 项通过；少量第三方弃用警告不代表测试失败。

## 三、在 Swagger 完整测试一笔销售

注意：预览不会改数据，但“确认”会在你当前 MySQL 数据库中生成真实销售记录并扣库存。请选择专门的测试 SKU，数量建议先用 1 双。

1. 打开 `http://127.0.0.1:8000/docs`。
2. 调用 `POST /api/v1/auth/login`，复制 `access_token`。
3. 点击右上角 `Authorize`，填写 `Bearer 空格 access_token`。Token 不要发截图或公开。
4. 调用 `POST /api/v1/agent/chat`，例如：

```json
{
  "message": "今天卖出货号 DD1391-100 的 42 码 1 双，每双 800 元"
}
```

正常响应应包含：

- `tools_used` 中有 `preview_sale`；
- `pending_action.status` 为 `pending`；
- `pending_action.requires_confirmation` 为 `true`；
- `preview` 中能看到商品、数量、单价、成本、销售额、毛利润和扣减后库存；
- 此时库存仍未改变。

复制 `pending_action.action_id`，再调用：

```text
POST /api/v1/agent/actions/{action_id}/confirm
```

该接口不需要请求体。成功后：

- 状态变成 `confirmed`；
- `result.sale` 中出现正式销售单号；
- 库存扣减；
- 库存流水新增一条 `sale`；
- 再次确认同一 `action_id` 只返回原销售单，不重复扣库存。

如果不想执行某个预览，调用：

```text
POST /api/v1/agent/actions/{action_id}/cancel
```

查看某个操作状态可调用：

```text
GET /api/v1/agent/actions/{action_id}
```

## 四、常见拦截结果

| 返回代码 | 含义 | 处理方式 |
|---|---|---|
| `SKU_NOT_FOUND` | 没找到商品 | 核对货号、尺码、条码 |
| `SKU_AMBIGUOUS` | 匹配到多个 SKU | 补充货号、尺码或条码 |
| `INSUFFICIENT_STOCK` | 可用库存不足 | 降低数量或先处理库存 |
| `AGENT_ACTION_EXPIRED` | 预览已超过有效期 | 重新说一遍销售指令 |
| `AGENT_PREVIEW_STALE` | 预览后库存或成本发生变化 | 重新生成预览并核对 |
| `AGENT_ACTION_CANCELLED` | 操作已经取消 | 重新生成新预览 |
| `AGENT_ACTION_NOT_FOUND` | 操作不存在或不属于当前账号 | 使用创建它的账号和正确 ID |

## 五、验收标准

以下全部成立，即可认为第二阶段完成：

- 原有后端、网页和手机端仍能正常登录、查询和操作。
- 普通查询仍只读取数据。
- 销售自然语言能返回准确的预览和利润。
- 预览阶段库存不变。
- 确认阶段只扣减一次库存，并生成一张销售单和一条销售流水。
- 取消、过期、跨账号确认、库存变化、库存不足都被拦截。
- DeepSeek 获得的工具中没有 `confirm_sale`、`create_sale` 或直接库存修改工具。

# ShoeFlow ERP 后端

ShoeFlow AI V1.0 的 ERP 后端基础工程。ERP 是库存、成本、销售和利润的唯一真实数据源；后续 Agent 只能通过 ERP 业务能力执行操作，不直接修改数据库。

## 当前已完成

- FastAPI 应用与 `/docs` 接口文档
- 版本化 API 路由
- 统一成功响应与异常响应
- Pydantic Settings 环境配置
- SQLAlchemy 2 数据库会话
- Alembic 数据库迁移框架
- 健康检查接口
- 基础自动化测试
- DeepSeek Tool Calling 经营 Agent
- 自然语言 SKU 与实时库存查询
- 自然语言销售出库预览、销售额/成本/毛利润计算
- 持久化待确认操作，人工确认后调用原销售服务扣库存
- 重复确认防重、15 分钟过期、库存变化时强制重新预览

## 技术栈

- Python 3.12
- FastAPI
- SQLAlchemy 2
- Alembic
- MySQL 8（正式开发）
- Pytest
- DeepSeek API（OpenAI 兼容接口）

## Windows 启动步骤

在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

在 MySQL 中创建数据库：

```sql
CREATE DATABASE shoeflow
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

然后修改 `.env` 中的 `DATABASE_URL`，执行：

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

如需启用 AI 经营助手，还需要在 `.env` 中填写仅供后端使用的：

```env
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
AGENT_ACTION_EXPIRE_MINUTES=15
```

不要把 DeepSeek API Key 写入移动端代码，也不要提交 `.env`。

浏览器访问：

- Swagger 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>
- Agent 对话：`POST /api/v1/agent/chat`（需要 Bearer Token）
- 操作详情：`GET /api/v1/agent/actions/{action_id}`（需要 Bearer Token）
- 确认执行：`POST /api/v1/agent/actions/{action_id}/confirm`（需要 Bearer Token）
- 取消操作：`POST /api/v1/agent/actions/{action_id}/cancel`（需要 Bearer Token）

## Agent 安全写入流程

用户可以说：

```text
今天卖出货号 DD1391-100 的 42 码 2 双，每双 800 元
```

Agent 先匹配唯一 SKU，读取实时库存与平均成本，计算销售额、销售成本、毛利润和扣减后库存，并生成 `pending_action`。这一步不会改库存。

只有登录用户显式调用该操作的 `confirm` 接口后，后端才会调用既有销售服务，在同一事务中创建销售单、库存流水并扣减库存。模型本身没有确认或直接改库存的工具。

待确认操作默认 15 分钟过期。如果预览后库存数量、预留量或平均成本发生变化，旧预览不能执行，必须重新生成。对同一个操作重复确认只返回首次结果，不会再次扣库存。

## 运行测试

```powershell
pytest
```

测试环境会自动使用 SQLite，不依赖本机 MySQL 服务。

## 目录结构

```text
shoeflow-erp/
├── app/
│   ├── api/v1/          # V1 API 路由
│   ├── core/            # 配置、异常和响应
│   ├── db/              # 数据库基础设施
│   ├── models/          # SQLAlchemy 模型
│   ├── schemas/         # Pydantic 请求/响应模型
│   └── main.py          # FastAPI 入口
├── alembic/             # 数据库迁移
├── tests/               # 自动化测试
├── .env.example
├── alembic.ini
└── requirements*.txt
```

当前 Agent 已完成第二阶段的单 SKU 销售安全写入。入库、退货、库存校正和删除仍未向模型开放；后续可沿用同一套“预览 → 人工确认 → 业务服务执行”机制逐项增加。

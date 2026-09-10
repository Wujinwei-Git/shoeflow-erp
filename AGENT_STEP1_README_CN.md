# ShoeFlow ERP Agent 第一阶段增量更新说明

本更新包只增加 DeepSeek 只读 Agent，不会替换整个 ERP 项目，也不会修改数据库结构。

## 本阶段能力

- 使用自然语言查询 SKU 档案。
- 使用自然语言查询实时库存、可用库存、平均成本和库存金额。
- Agent 必须登录后才能使用。
- 后端只向模型开放 `search_skus` 和 `query_inventory` 两个只读工具。
- 入库、销售、退货、库存调整、删除等写操作均未开放。
- 即使模型尝试调用未授权工具，后端白名单也会拒绝执行。

## 一、合并文件

先关闭正在运行的后端，然后打开这个增量包，将其中的 `.env.example`、`requirements.txt`、`README.md`、`app` 和 `tests` 复制到现有项目根目录：

```text
D:\shoeflow-erp
```

Windows 询问时，选择合并文件夹并覆盖同名文件。这个包不包含 `.env`，所以不会覆盖你的数据库密码、JWT 密钥等现有配置。

修改的旧文件：

```text
.env.example
README.md
requirements.txt
app/api/v1/router.py
app/core/config.py
```

新增文件：

```text
app/api/v1/routes/agent.py
app/schemas/agent.py
app/services/agent_service.py
app/services/agent_tools.py
app/services/deepseek_service.py
tests/test_agent.py
```

## 二、安装新增依赖

在 PyCharm 已激活 `.venv` 的终端里执行：

```powershell
python -m pip install -r requirements-dev.txt
```

## 三、配置 DeepSeek

不要新建或覆盖 `.env`。只在现有 `.env` 文件末尾追加下面四行，并把第一行换成你自己在 DeepSeek 平台创建的 API Key：

```env
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=30
```

API Key 只能保存在后端 `.env`，不要写入手机端、截图、聊天记录或 Git 仓库。

## 四、验证并启动

本阶段没有新增数据表，因此不需要执行 Alembic 数据库迁移。

先运行测试：

```powershell
pytest -q
```

预期结果：

```text
63 passed
```

再启动后端：

```powershell
uvicorn app.main:app --reload --host 0.0.0.0
```

## 五、在 Swagger 测试 Agent

1. 打开 `http://127.0.0.1:8000/docs`。
2. 先调用 `POST /api/v1/auth/login` 登录并复制返回的 `access_token`。
3. 点击页面右上方 `Authorize`，粘贴 access token 后确认。
4. 找到“AI 经营助手”，调用 `POST /api/v1/agent/chat`。
5. 请求示例：

```json
{
  "message": "查询货号 DD1391-100 42 码还有多少库存"
}
```

如果返回 `AGENT_NOT_CONFIGURED`，说明后端尚未读取到 DeepSeek API Key；保存 `.env` 后重启后端即可。

## 下一阶段

待只读查询实机验证通过后，再增加“销售/入库指令预览 → 用户点确认 → 调用现有业务服务执行”的写操作闭环。写操作不会允许模型直接改数据库。

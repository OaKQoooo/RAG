# 前端原型说明

这套代码基于 [`plan.md`](D:/code/RAG/v4.0/v4.0/plan.md) 和 [`table.md`](D:/code/RAG/v4.0/v4.0/table.md) 搭建，当前包含：

- `frontend/index.html`：入口页，含登录/注册切换与角色入口
- `frontend/user.html`：用户端页面，包含对话、个人文档、设置
- `frontend/admin.html`：管理员端页面，包含总览、文档库管理、用户管理
- `frontend/assets/css/styles.css`：公共样式
- `frontend/assets/js/common.js`：公共交互
- `frontend/assets/js/user.js`：用户端交互
- `frontend/assets/js/admin.js`：管理员端交互

## 页面与数据表的对应关系

### 用户端

- 对话区对应：
  - `qa_conversation`
  - `qa_message`
- 原文溯源区依赖：
  - Chroma 中 Document metadata
  - `kb_clause.page`
  - `kb_clause.bbox_json`
- 个人文档区对应：
  - `kb_document`

### 管理员端

- 文档库管理对应：
  - `kb_document`
  - `kb_clause`
  - `kb_chunk`
- 用户管理对应：
  - `sys_user`


## 接口

### 用户端

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/conversations`
- `GET /api/conversations/{id}/messages`
- `POST /api/chat`
- `GET /api/documents/my`
- `POST /api/documents/upload`

### 管理员端

- `GET /api/admin/documents`
- `POST /api/admin/documents/upload`
- `DELETE /api/admin/documents/{id}`
- `GET /api/admin/users`
- `PATCH /api/admin/users/{id}/status`

## 预览方式

直接在浏览器中打开以下文件即可：

- `code/frontend/index.html`
- `code/frontend/user.html`
- `code/frontend/admin.html`

## 后端联通方式

本次后端拆成两层：

- `rag_service.py`：Python RAG 服务，负责 PDF 入库、Chroma 检索、DashScope 生成、PDF 原文截图。
- `spring-backend/`：Spring Boot 业务服务，负责登录注册、会话、消息、文档管理、管理员接口，并调用 Python RAG 服务。

Windows 下建议启动顺序：

```powershell
cd D:\code\RAG\v4.0\v4.0\code
$env:DASHSCOPE_API_KEY="你的 DashScope Key"
uvicorn rag_service:app --host 127.0.0.1 --port 8000
```

另开一个 PowerShell：

```powershell
cd D:\code\RAG\v4.0\v4.0\code\spring-backend
$env:JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-17.0.17.10-hotspot"
mvn spring-boot:run
```

然后打开：

- `code/frontend/index.html`
- `code/frontend/user.html`
- `code/frontend/admin.html`

前端默认请求 `http://localhost:8080/api`，Spring 默认请求 Python RAG 服务 `http://127.0.0.1:8000`。

## 数据库配置

Spring 后端默认使用 MySQL，适合多台电脑连接同一个业务数据库。首次使用前先在 MySQL 中创建数据库：

```sql
CREATE DATABASE dam_rag DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认连接配置如下：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=dam_rag
MYSQL_USERNAME=root
MYSQL_PASSWORD=root
```

如果多台电脑要访问同一个数据库，把 `MYSQL_HOST` 改成 MySQL 所在电脑或服务器的 IP，例如：

```powershell
$env:MYSQL_HOST="192.168.1.20"
$env:MYSQL_PORT="3306"
$env:MYSQL_DATABASE="dam_rag"
$env:MYSQL_USERNAME="root"
$env:MYSQL_PASSWORD="你的MySQL密码"
mvn spring-boot:run
```

如果只是本地临时测试 H2，可以切换 profile：

```powershell
mvn spring-boot:run -Dspring-boot.run.profiles=h2
```

## 字段核实结果

`table.md` 中原始字段能支持最基础流程，但不足以完整满足需求。已在 Spring 实体中补充：

- `sys_user.contact/avatar_url/theme/created_at/updated_at`：对应注册联系方式、头像、界面偏好。
- `kb_document.visibility/created_at/updated_at`：区分管理员公共文档和用户私有文档。
- `qa_message.reference_json`：历史会话恢复时可重新显示右侧原文截图和引用依据。
- `kb_clause.page_width/page_height`：保存 PDF 页面尺寸，便于后续前端按比例绘制高亮框。
- `kb_clause.bbox_json`、`kb_chunk.bbox_json` 改为大字段：原 `varchar(255)` 对多行 bbox 或复杂表格定位偏短。

## 问答检索策略

RAG 服务采用“向量召回 + 本地关键词召回 + DashScope rerank + 本地融合排序”的流程。新入库向量会同时索引规范名称、标准层级、完整章节路径、条款号和正文，以改善规范编号、章节和条款类问题的召回效果。

融合排序会将标准层级作为小幅加分项。默认顺序为：强制性国家标准、推荐性国家标准、行业标准、地方标准、团体标准、企业或公司标准、项目文件、未识别层级。该顺序仅用于检索排序，不代表系统自动作出法律效力或适用性判断。用户明确提到“国标”“行标”“公司标准”或具体标准编号时，对应候选会获得额外加分。

可通过环境变量调整主要参数：

```text
RAG_INITIAL_RETRIEVAL_K=40
RAG_LEXICAL_RETRIEVAL_K=20
RAG_RERANK_TOP_N=20
RAG_RERANK_THRESHOLD=0.05
RAG_PRIORITY_NATIONAL_MANDATORY=1.00
RAG_PRIORITY_NATIONAL_RECOMMENDED=0.90
RAG_PRIORITY_INDUSTRY=0.75
RAG_PRIORITY_LOCAL=0.65
RAG_PRIORITY_GROUP=0.50
RAG_PRIORITY_ENTERPRISE=0.40
RAG_PRIORITY_PROJECT=0.30
```

更新检索策略后，需要重新入库或执行全量重建，已有向量才能获得完整的索引元数据。管理端调试检索结果中的 `_vector_score`、`_rerank_score`、`_lexical_score` 和 `_fused_score` 可用于分析排序效果。

建议维护一份人工标注的检索评测集，例如：

```json
[
  {
    "question": "施工导流有哪些基本规定？",
    "expected_clause_ids": ["4.1.1", "4.1.2"]
  }
]
```

模型服务可用时，执行以下命令检查 `Hit@K` 和 `MRR`：

```powershell
python evaluate_retrieval.py retrieval_eval.json --top-k 10
```

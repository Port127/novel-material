.PHONY: help db-up db-down db-init db-shell db-reset ingest full analyze finalize search ingest-material import-material delete-material lint validate docker-prune

PYTHON := python

# ── 默认目标 ──────────────────────────────────────────────
help:
	@echo "Novel Material V2 - 项目管理"
	@echo ""
	@echo "Docker 数据库:"
	@echo "  db-up          启动 PostgreSQL + pgAdmin"
	@echo "  db-down        停止数据库容器"
	@echo "  db-init        初始化数据库表（首次使用）"
	@echo "  db-shell       进入 psql 交互终端"
	@echo ""
	@echo "流水线:"
	@echo "  ingest FILE=   入库流水线（格式清洗+章节切分）"
	@echo "  full FILE=     完整流水线（入库→分析→向量→精调→同步）"
	@echo "  analyze ID=    分析流水线（章级→大纲→世界观→人物→标签）"
	@echo "  finalize ID=   收尾流水线（精调+同步数据库）"
	@echo ""
	@echo "素材管理:"
	@echo "  import-material ID=  导入外部素材"
	@echo "  delete-material ID=  删除素材及所有关联数据"
	@echo ""
	@echo "检索:"
	@echo "  search TYPE=<world|outline|detail|chapter|character|event> ARGS=..."
	@echo ""
	@echo "维护:"
	@echo "  validate       校验所有 YAML 数据格式"
	@echo "  db-reset       重置数据库（删除+重建，危险操作）"
	@echo "  docker-prune   清理未使用的 Docker 镜像和容器"

# ── Docker 数据库 ─────────────────────────────────────────
db-up:
	@echo "▶ 启动数据库..."
	docker compose up -d
	@echo "  PostgreSQL: localhost:5432"
	@echo "  pgAdmin:    http://localhost:5050"

db-down:
	@echo "▶ 停止数据库..."
	docker compose down

db-init:
	@echo "▶ 初始化数据库表..."
	$(PYTHON) scripts/core/init_db.py

db-shell:
	@echo "▶ 进入 psql..."
	docker exec -it novel-material-pg psql -U admin -d novel_material

db-reset:
	@echo "⚠  警告：即将删除所有数据库数据！"
	@echo "▶ 停止并清理容器..."
	docker compose down -v
	@echo "▶ 重启容器..."
	docker compose up -d
	@echo "▶ 等待数据库就绪..."
	@sleep 3
	@echo "▶ 初始化数据库..."
	$(PYTHON) scripts/core/init_db.py

# ── 流水线 ────────────────────────────────────────────────
ifeq ($(strip $(FILE)),)
ingest:
	@echo "用法: make ingest FILE=<文件路径>"
	@echo "示例: make ingest FILE=./data/novels/my-novel.txt"
else
ingest:
	$(PYTHON) scripts/pipeline.py ingest $(FILE)
endif

ifeq ($(strip $(FILE)),)
full:
	@echo "用法: make full FILE=<文件路径>"
	@echo "示例: make full FILE=./data/novels/my-novel.txt"
else
full:
	$(PYTHON) scripts/pipeline.py full $(FILE)
endif

ifeq ($(strip $(ID)),)
analyze:
	@echo "用法: make analyze ID=<material_id>"
	@echo "示例: make analyze ID=nm_novel_20260503_abcd"
else
analyze:
	$(PYTHON) scripts/pipeline.py analyze $(ID)
endif

ifeq ($(strip $(ID)),)
finalize:
	@echo "用法: make finalize ID=<material_id>"
	@echo "示例: make finalize ID=nm_novel_20260503_abcd"
else
finalize:
	$(PYTHON) scripts/pipeline.py finalize $(ID)
endif

# ── 素材管理 ──────────────────────────────────────────────
ifeq ($(strip $(ID)),)
import-material:
	@echo "用法: make import-material ID=<material_id>"
else
import-material:
	$(PYTHON) scripts/utils/material_import.py --id $(ID)
endif

ifeq ($(strip $(ID)),)
delete-material:
	@echo "用法: make delete-material ID=<material_id>"
else
delete-material:
	$(PYTHON) scripts/utils/material_delete.py --id $(ID)
endif

# ── 检索 ──────────────────────────────────────────────────
search:
	@echo "用法示例:"
	@echo "  世界观: make search-type-world TYPE=faction GENRE=修仙 LIMIT=10"
	@echo "  大纲:   make search-type-outline GENRE=修仙 QUERY='废柴逆袭'"
	@echo "  细节:   make search-type-detail GENRE=悬疑 ACT=2"
	@echo "  章节:   make search-type-chapter QUERY='开局困境写法' LIMIT=10"
	@echo "  人物:   make search-type-character ARCHETYPE=导师 GENRE=修仙"
	@echo "  事件:   make search-type-event QUERY='雨中告别的写法' LIMIT=10"
	@echo ""
	@echo "或者直接用脚本:"
	@echo "  python scripts/search/search_world.py --type faction --genre 修仙 --limit 10"
	@echo "  python scripts/search/search_outline.py --genre 修仙 --query '废柴逆袭'"
	@echo "  python scripts/search/search_detail.py --genre 悬疑 --act 2"
	@echo "  python scripts/search/search_chapter.py '开局困境写法' --limit 10"
	@echo "  python scripts/search/search_character.py --archetype 导师 --genre 修仙"
	@echo "  python scripts/search/search_event.py '雨中告别的写法' --limit 10"

# ── 维护 ──────────────────────────────────────────────────
validate:
	@echo "▶ 校验 YAML 数据格式..."
	$(PYTHON) scripts/utils/schema_validator.py

docker-prune:
	@echo "▶ 清理未使用的 Docker 资源..."
	docker system prune -f

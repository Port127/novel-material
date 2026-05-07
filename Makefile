.PHONY: help db-up db-down db-init db-shell db-reset docker-prune

# ── 默认目标 ──────────────────────────────────────────────
help:
	@echo "Docker 数据库管理"
	@echo ""
	@echo "容器管理:"
	@echo "  db-up          启动 PostgreSQL + pgAdmin"
	@echo "  db-down        停止数据库容器"
	@echo "  db-shell       进入 psql 交互终端"
	@echo "  db-reset       重置数据库（删除+重建，危险操作）"
	@echo "  docker-prune   清理未使用的 Docker 资源"
	@echo ""
	@echo "数据库初始化:"
	@echo "  db-init        初始化表结构 + 基础数据"
	@echo ""
	@echo "其他操作请使用 CLI:"
	@echo "  nm pipeline ingest <file>      # 入库"
	@echo "  nm pipeline full <file>        # 完整流水线"
	@echo "  nm pipeline refine <id>        # 精调"
	@echo "  nm material import <dir>       # 导入素材"
	@echo "  nm material delete --id <id>   # 删除素材"
	@echo "  nm tags stats                  # 标签统计"
	@echo "  nm search outline --genre <g>  # 搜索大纲"
	@echo "  nm validate --all              # 校验数据"

# ── Docker 容器管理 ─────────────────────────────────────────
db-up:
	@echo "▶ 启动数据库..."
	docker compose up -d
	@echo "  PostgreSQL: localhost:5432"
	@echo "  pgAdmin:    http://localhost:5050"

db-down:
	@echo "▶ 停止数据库..."
	docker compose down

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
	nm storage init-db
	nm storage init-data

db-init:
	@echo "▶ 初始化数据库..."
	nm storage init-db
	nm storage init-data

docker-prune:
	@echo "▶ 清理未使用的 Docker 资源..."
	docker system prune -f
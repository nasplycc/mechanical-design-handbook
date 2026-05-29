#!/bin/bash
# 机械设计手册检索系统 - 启动入口
# 用法: ./run.sh [web|mcp|cli|reindex]

DIR="/vol2/1000/working/机械设计原理"
cd "$DIR" || exit 1

case "${1:-web}" in
  web)
    echo "🌐 启动 Web 界面: http://localhost:5231"
    python3 web_ui.py
    ;;
  mcp)
    echo "🔧 启动 MCP stdio server"
    python3 mcp_server.py
    ;;
  cli)
    shift
    query="${*:-}"
    if [ -z "$query" ]; then
      echo "🔍 交互模式"
      python3 search.py -i
    else
      python3 search.py "$query"
    fi
    ;;
  reindex)
    echo "📄 重建页码索引 (PDF)..."
    python3 pdf_annotate.py
    echo "✅ 完成"
    ;;
  status)
    echo "📊 系统状态:"
    echo "  知识库: $(find 机械设计知识库 -name '*.md' | wc -l) 个文件"
    echo "  卷: 5卷 (2017+1693+1640+1316+1846=8512页)"
    echo "  MCP: mcporter call mechanical-design.mechanical_search query=\"test\""
    echo "  Web: http://localhost:5231"
    echo "  CLI: python3 search.py \"查询词\""
    ;;
  *)
    echo "用法: ./run.sh [web|mcp|cli|reindex|status]"
    echo "  web     — 启动 Web 界面 (http://localhost:5231)"
    echo "  mcp     — 启动 MCP stdio server"
    echo "  cli     — CLI 查询 (如: ./run.sh cli 齿轮齿条)"
    echo "  reindex — 重建PDF页码索引"
    echo "  status  — 显示系统状态"
    ;;
esac
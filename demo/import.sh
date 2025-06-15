#!/bin/bash

# === 配置部分 ===
CSV_DIR="./output"                      # CSV 文件目录
IMPORT_DIR="/var/lib/neo4j/import"      # Neo4j import 目录
TAG="$1"
START_DATE="$2"
END_DATE="$3"

# 从 stdin 读取密码
read -s PASSWORD

# === 文件名构建 ===
BASENAME="tweets_${TAG}_${START_DATE}_${END_DATE}"
NODES_FILE="${BASENAME}_nodes.csv"
RELS_FILE="${BASENAME}_relationships.csv"

# === 检查文件存在 ===
if [ ! -f "${CSV_DIR}/${NODES_FILE}" ]; then
  echo "❌ 节点文件不存在: ${CSV_DIR}/${NODES_FILE}"
  exit 1
fi

if [ ! -f "${CSV_DIR}/${RELS_FILE}" ]; then
  echo "❌ 关系文件不存在: ${CSV_DIR}/${RELS_FILE}"
  exit 1
fi

# === 拷贝文件 ===
echo "📂 拷贝文件到 Neo4j import 目录..."
echo "$PASSWORD" | sudo -S cp "${CSV_DIR}/${NODES_FILE}" "${IMPORT_DIR}/"
echo "$PASSWORD" | sudo -S cp "${CSV_DIR}/${RELS_FILE}" "${IMPORT_DIR}/"

echo "✅ 已成功复制至: ${IMPORT_DIR}"
echo

# === 提示 Cypher 导入语句 ===
echo "📌 请在 Neo4j Browser 中运行以下语句导入节点与关系："
echo "
-- 导入节点
LOAD CSV WITH HEADERS FROM 'file:///${NODES_FILE}' AS row
MERGE (t:Tweet {id: row.tweet_id})
SET t.username = row.username,
    t.timestamp = row.timestamp,
    t.date = row.date,
    t.content = row.content,
    t.url = row.url,
    t.level = toInteger(row.level);

-- 导入关系
LOAD CSV WITH HEADERS FROM 'file:///${RELS_FILE}' AS row
MATCH (a:Tweet {id: row.start_id})
MATCH (b:Tweet {id: row.end_id})
MERGE (a)-[:REPLIED_TO {level: toInteger(row.level), type: row.type}]->(b);
"


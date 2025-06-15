from flask import Flask, render_template, request, Response, stream_with_context
from datetime import datetime
from scrape import run_scraper
from Dataprocessing import run_processing
from neo4j import GraphDatabase
import os
import subprocess
import time
import queue
import threading

app = Flask(__name__)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = ""

# 线程安全的消息队列用来传日志
log_queue = queue.Queue()

def log(msg):
    print(msg)  # 控制台打印
    log_queue.put(msg)  # 放入队列供 SSE 发送

def generate_log_stream():
    while True:
        try:
            msg = log_queue.get(timeout=0.1)
            yield f"data: {msg}\n\n"
        except queue.Empty:
            # 为了避免断开连接，发送心跳
            yield "data: \n\n"
            time.sleep(0.1)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stream")
def stream():
    return Response(stream_with_context(generate_log_stream()), mimetype="text/event-stream")

@app.route("/run", methods=["POST"])
def run():
    tag = request.form["tag"]
    start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()

    def task():
        try:
            log("🔄 Step 1：正在爬取推文...")
            json_path = run_scraper(
                tag_to_search=tag,
                start_date=start_date,
                end_date=end_date,
                max_scrolls=1,
                batch_size=2,
                save_dir="./output"
            )
            log(f"✅ 爬取完成，保存路径：{json_path}")

            log("🔄 Step 2：正在处理数据生成 CSV...")
            base_filename = os.path.splitext(os.path.basename(json_path))[0]
            output_prefix = os.path.join("./output", base_filename)
            nodes_csv, rels_csv = run_processing(json_path, output_prefix)
            log("✅ 数据处理完成，生成 CSV：")
            log(f"   - {nodes_csv}")
            log(f"   - {rels_csv}")

            log("🔄 Step 3：将 CSV 拷贝到 Neo4j import 目录...")
            subprocess.run(["cp", nodes_csv, "/var/lib/neo4j/import/"], check=True)
            subprocess.run(["cp", rels_csv, "/var/lib/neo4j/import/"], check=True)
            log("✅ CSV 文件已复制至 Neo4j import 目录")

            log("🔄 Step 4：连接 Neo4j，清空旧数据并导入新数据...")

            driver = GraphDatabase.driver(NEO4J_URI, auth=None)
            basename = os.path.basename(nodes_csv).replace("_nodes.csv", "")

            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                log("🧹 已清空旧图数据")

                session.run(f"""
                LOAD CSV WITH HEADERS FROM 'file:///{basename}_nodes.csv' AS row
                WITH row WHERE row.tweet_id IS NOT NULL
                MERGE (t:Tweet {{tweet_id: row.tweet_id}})
                SET t.username = row.username,
                    t.timestamp = row.timestamp,
                    t.date = row.date,
                    t.content = row.content,
                    t.url = row.url,
                    t.level = toInteger(row.level)
                """)

                session.run(f"""
                LOAD CSV WITH HEADERS FROM 'file:///{basename}_relationships.csv' AS row
                MATCH (start:Tweet {{tweet_id: row.start_id}})
                MATCH (end:Tweet {{tweet_id: row.end_id}})
                CALL apoc.merge.relationship(start, row.type, {{level: toInteger(row.level)}}, {{}}, end) YIELD rel
                RETURN count(*)
                """)

                session.run("""
                MATCH (n:Tweet {tweet_id: 'ROOT', content: 'Virtual root node'})
                DETACH DELETE n
                """)
                log("🗑️ 已删除虚拟根节点")

            log("✅ 图数据已成功导入 Neo4j")
            log("🎉 任务完成！你可以打开 Neo4j 浏览器查看图谱。")

        except Exception as e:
            log(f"❌ 出错了：{e}")

    threading.Thread(target=task).start()
    return "任务开始，日志将在页面实时显示。"

if __name__ == "__main__":
    app.run(debug=True, threaded=True)

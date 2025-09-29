#主文件只负责协调各模块。
import asyncio
import json
import logging
import os
import sys
from typing import Optional, Dict, List, Any
from text_processor import process_json_chunk, reset_database, close_resources, process_json_files
from config import Config
from neo4j_connection import Neo4jConnection
from knowledge_graph_updater import KnowledgeGraphUpdater
from time_converter import convert_to_now_time
import time
from datetime import datetime
from conflict_experiment import run_conflict_resolution_experiment

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_DIR, 'app.log.txt')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def print_help():
    """打印帮助信息"""
    print("\n使用方法:")
    print("  python langchain_neo4j_test.py [命令]")
    print("\n可用命令:")
    print("  无参数    - 执行默认流程（处理数据并更新知识图谱）")
    print("  /help     - 显示此帮助信息")
    print("  /run_experiment - 运行冲突解决策略实验评估")
    print("\n示例:")
    print("  python langchain_neo4j_test.py /run_experiment")

async def main():
    # 处理命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "/help":
            print_help()
            return
        elif command == "/run_experiment":
            print("\n正在运行冲突解决策略实验评估...")
            run_conflict_resolution_experiment()
            return
        else:
            print(f"未知命令: {command}")
            print_help()
            return
    
    start_time = time.perf_counter()
    logger.info(f"程序开始运行: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    neo4j_conn = None
    try:
        logger.info(f"当前工作目录: {os.getcwd()}")
        logger.info(f"日志文件路径: {LOG_FILE}")

        neo4j_config = Config.get_neo4j_config()
        neo4j_conn = Neo4jConnection(
            uri=neo4j_config["uri"],
            user=neo4j_config["user"],
            password=neo4j_config["password"]
        )
        neo4j_conn.verify_connectivity()
        logger.info(f"成功连接到 Neo4j: {neo4j_config['uri']}, 用户: {neo4j_config['user']}")

        neo4j_conn.clear_database()
        logger.info("数据库已清空")

        await reset_database(neo4j_conn)
        logger.info("数据库重置完成，开始处理数据")

        json_file_path = os.path.join(PROJECT_DIR, "data", "lhasa_knowledge_graph.json")
        crawl_timestamp = "2025-06-19T20:46:39.861593"
        source_type = "crawler"
        metrics = {"ratings": 4.0}

        updater = KnowledgeGraphUpdater(neo4j_conn)  # Pass neo4j_conn
        try:
            logger.info(f"开始处理 JSON 文件: {json_file_path}")
            result = await process_json_files(
                neo4j_conn=updater.crud,
                json_file_path=json_file_path,
                crawl_timestamp=crawl_timestamp,
                source_type=source_type,
                metrics=metrics
            )
            logger.info(f"处理结果: {result}")
            
            total_processed = result.get("processed", 0)
            total_failed = result.get("failed", 0)
            logger.info(f"处理完成，共处理 {total_processed} 个景点，失败 {total_failed} 个")
        except Exception as e:
            logger.error(f"主程序错误: {e}", exc_info=True)
        finally:
            updater.close()

        conflict_queue_path = os.path.join(PROJECT_DIR, 'conflict_queue.json')
        with open(conflict_queue_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        logger.info(f"已清空 {conflict_queue_path}")

        try:
            with open(conflict_queue_path, 'r', encoding="utf-8") as f:
                conflict_queue = json.load(f)
            if conflict_queue:
                logger.info(f"发现冲突队列: {conflict_queue}")
                from conflict_resolution import resolve_from_queue
                await resolve_from_queue(neo4j_conn, source_type="crawler", metrics={"ratings": 4.0})
            else:
                logger.info("未发现冲突队列，队列为空")
        except json.JSONDecodeError:
            logger.error("conflict_queue.json 格式错误，已初始化为空数组")
            with open(conflict_queue_path, 'w', encoding="utf-8") as f:
                json.dump([], f)
        except FileNotFoundError:
            logger.info("未发现冲突队列，创建空文件")
            with open(conflict_queue_path, 'w', encoding="utf-8") as f:
                json.dump([], f)

    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
    finally:
        if neo4j_conn:
            neo4j_conn.close()
        await close_resources()
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        logger.info(f"程序结束运行: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"总运行时间: {duration:.2f} 秒")

if __name__ == "__main__":
    asyncio.run(main())
动态知识图谱自适应演化项目
一、项目概述
本项目基于 Neo4j 构建动态知识图谱，结合 LangChain 和大模型（LLM，调用 SiliconFlow API）处理西藏旅游数据，实现自适应更新与冲突解决。当前聚焦于景点数据的抽取、关系推断和冲突管理。
二、主要模块与功能
1. config.py
作用：集中管理所有配置（Neo4j、API 密钥、LLM 设置），通过静态方法获取，便于灵活配置。
主要方法：
get_neo4j_config()：获取 Neo4j 连接信息。
get_deepseek_api_key()：获取 DeepSeek API 密钥。
get_llm_config()：获取 LLM 相关设置。
validate_config()：校验配置有效性。
2. neo4j_crud.py
作用：封装 Neo4j 的 CRUD 操作，便于节点和关系的创建、读取、更新、删除。
主要方法：
create_node / read_node / update_node / delete_node
create_relationship / delete_relationship
3. langchain_neo4j_test.py
作用：主流程，处理旅游文本，调用 DeepSeek 提取结构化数据，推断类别并更新知识图谱。
主要方法：
update_knowledge_graph：更新图谱节点和关系。
process_chunk：异步处理文本块，结构化数据。
call_deepseek_with_retry：带重试的 LLM 调用。
process_tourism_text：整体流程编排。
4. conflict_resolution.py
作用：冲突解决模块，基于时间戳、来源权重和规则自动或辅助解决冲突。
相关文件：
conflict_queue.json：记录未解决冲突。
rules.txt：定义冲突解决规则。
GUI（tkinter）：可视化冲突处理界面。
三、接口用法示例
1. 直接传递字符串数据
Apply to README.md
2. 传递文件路径
Apply to README.md
返回值为景点字典列表，如：[{"name": "纳木错", "category": "自然风光", ...}]
四、运行环境与依赖
Python 3.x
依赖库：langchain, langchain-openai, neo4j, tkinter, tenacity
Neo4j 数据库已配置
API 密钥在 config.py 设置
五、运行步骤
清理 Neo4j 数据
Apply to README.md
运行主程序
Apply to README.md
检查结果
日志无报错，conflict_queue.json 正常生成
GUI 解决冲突，Neo4j 查询：
Apply to README.md
六、注意事项
确保 config.py 配置正确（API 密钥、Neo4j 连接）。
数据需为 UTF-8 编码的纯文本。
如遇问题，查看日志并反馈。
七、后续计划
验证冲突记录与解决流程
优化 GUI（高亮差异、字段级合并）
性能测试与瓶颈分析
考虑增加图谱可视化功能


所需要的文件其中需要包含的字段名
pub_timestamp：
Description: Timestamp of when the data was published or crawled, in ISO format.
Usage: Stored as a property of the Attraction node to track data freshness.
简单来讲就是这个数据出现在网上的时间


config.py: 定义配置类 Config，管理 Neo4j 数据库连接和 LLM API 的配置（如 DeepSeek API）。提供默认值、环境变量读取、以及配置验证功能。

conflict_resolution.py: 处理知识图谱更新中的数据冲突，通过时间戳、来源权重和规则（如优先政府数据）决定合并策略，并记录冲突到 conflict_queue.json。

langchain_neo4j_test.py: 主程序，协调各模块，负责数据库初始化、JSON 数据处理、冲突解决等，使用异步方式调用 LLM 和更新知识图谱。

knowledge_graph_updater.py: 实现知识图谱的更新逻辑，创建或更新景点（Attraction）和城市（City）节点，建立关系（如 LOCATED_IN、CULTURALLY_RELATED）。

neo4j_crud.py: 提供 Neo4j 数据库的增删改查（CRUD）操作，管理节点和关系的创建、更新、删除，以及变更日志的记录。

neo4j_connection.py: 封装 Neo4j 数据库连接，验证连接、清空数据库、执行查询等。

rules.txt: 定义优先级规则，例如优先采用政府来源的数据。

time_converter.py: 处理时间戳转换，统一转换为北京时间（UTC+8）。

utils.py: 提供工具函数，如计算语义相似度（使用 SentenceTransformer）。

text_processor.py: 负责文本处理和 LLM 管道逻辑，包括 JSON 数据处理、生成最佳评论、数据验证、位置规范化等。
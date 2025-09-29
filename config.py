import os

# 配置类
class Config:
    # 默认值
    DEFAULT_NEO4J_URI = "bolt://localhost:7687"
    DEFAULT_NEO4J_USER = "neo4j"
    DEFAULT_NEO4J_PASSWORD = "neo4j"
    DEFAULT_MODEL1 = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    DEFAULT_MODEL2 = "Qwen/Qwen3-8B"
    DEFAULT_MODEL3 = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
    DEFAULT_API_BASE = "https://api.siliconflow.cn/v1/chat/completions"
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 5

    # Neo4j数据库配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "neo4j"  # 请修改为您的实际密码

    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = "knowledge_graph.log"

    @staticmethod
    def get_neo4j_config():
        """获取Neo4j配置"""
        return {
            "uri": os.getenv("NEO4J_URI", Config.DEFAULT_NEO4J_URI),
            "user": os.getenv("NEO4J_USER", Config.DEFAULT_NEO4J_USER),
            "password": os.getenv("NEO4J_PASSWORD", Config.DEFAULT_NEO4J_PASSWORD),
        }

    @staticmethod
    def get_deepseek_api_key():
        """获取DeepSeek API密钥"""
        return "sk-mpztnjpfxpbjwfoctubxttmtbancoppzdfbpzxesomaqbvby"

    def get_ollama_api_key():
        return os.getenv("ollama_api_key",None)

    @staticmethod
    def get_llm_config(model_name: str = "default"):
        """获取LLM配置"""
        llm_configs = {
            "default": {
                "api_key": "sk-mpztnjpfxpbjwfoctubxttmtbancoppzdfbpzxesomaqbvby",  # Use hardcoded API key
                "model": os.getenv("MODEL_NAME", Config.DEFAULT_MODEL1),
                "api_base": os.getenv("API_BASE", Config.DEFAULT_API_BASE),
                "timeout": int(os.getenv("TIMEOUT", Config.DEFAULT_TIMEOUT)),
                "max_retries": int(os.getenv("MAX_RETRIES", Config.DEFAULT_MAX_RETRIES)),
            },
            "llm1": {
                "api_key": "sk-mpztnjpfxpbjwfoctubxttmtbancoppzdfbpzxesomaqbvby",
                "model": os.getenv("MODEL_NAME_LLM1", Config.DEFAULT_MODEL1),
                "api_base": os.getenv("API_BASE_LLM1", Config.DEFAULT_API_BASE),
                "timeout": int(os.getenv("TIMEOUT_LLM1", Config.DEFAULT_TIMEOUT)),
                "max_retries": int(os.getenv("MAX_RETRIES_LLM1", Config.DEFAULT_MAX_RETRIES)),
            },
            "llm2": {
                "api_key": "sk-mpztnjpfxpbjwfoctubxttmtbancoppzdfbpzxesomaqbvby",
                "model": os.getenv("MODEL_NAME_LLM2", Config.DEFAULT_MODEL2),
                "api_base": os.getenv("API_BASE_LLM2", Config.DEFAULT_API_BASE),
                "timeout": int(os.getenv("TIMEOUT_LLM2", Config.DEFAULT_TIMEOUT)),
                "max_retries": int(os.getenv("MAX_RETRIES_LLM2", Config.DEFAULT_MAX_RETRIES)),
            },
            "conflict_llm": {
                "api_key": "sk-mpztnjpfxpbjwfoctubxttmtbancoppzdfbpzxesomaqbvby",
                "model": os.getenv("MODEL_NAME_LLM3", Config.DEFAULT_MODEL3),
                "api_base": os.getenv("API_BASE_LLM3", Config.DEFAULT_API_BASE),
                "timeout": int(os.getenv("TIMEOUT_LLM3", Config.DEFAULT_TIMEOUT)),
                "max_retries": int(os.getenv("MAX_RETRIES_LLM3", Config.DEFAULT_MAX_RETRIES)),
            }
        }
        return llm_configs.get(model_name, llm_configs["default"])
    
    @staticmethod
    def validate_config():
        """验证配置是否有效"""
        if not Config.get_deepseek_api_key():
            raise ValueError("DEEPSEEK_API_KEY环境变量未设置，请在运行前配置。")
        if not Config.get_neo4j_config()["uri"].startswith("bolt://"):
            raise ValueError("NEO4J_URI必须以'bolt://'开头。")
        return True

if __name__ == "__main__":
    # 示例用法
    try:
        Config.validate_config()
        print("Neo4j配置:", Config.get_neo4j_config())
        print("DeepSeek API密钥:", "已设置" if Config.get_deepseek_api_key() else "未设置")
        print("LLM配置 (default):", Config.get_llm_config())
        print("LLM配置 (llm1):", Config.get_llm_config("llm1"))
        print("LLM配置 (llm2):", Config.get_llm_config("llm2"))
    except ValueError as e:
        print(f"配置错误: {e}")
"""文本向量化工具：把文字转换成数字向量。"""
from dotenv import load_dotenv
import os

load_dotenv()

from novel_material.infra.logging_config import get_embedding_logger
logger = get_embedding_logger()


def load_embedding_config():
    """从 .env 加载向量化配置。"""
    return {
        "embedding": {
            "provider": os.getenv("EMBEDDING_PROVIDER", "ollama"),
            "model": os.getenv("EMBEDDING_MODEL", "qwen3-embedding"),
            "dimension": int(os.getenv("EMBEDDING_DIMENSION", "4096")),
            "base_url": os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434"),
            "api_key": os.getenv("EMBEDDING_API_KEY", ""),
        }
    }


def get_embedding(text, config=None):
    """获取单个文本的向量。

    参数：
        text：要向量化的文字
        config：配置字典（可选，默认从 .env 加载）

    返回：
        list：向量数字列表
    """
    if config is None:
        config = load_embedding_config()

    provider = config["embedding"]["provider"]
    model = config["embedding"]["model"]

    if provider == "openai":
        # OpenAI API（在线）
        from openai import OpenAI
        client = OpenAI(
            api_key=config["embedding"]["api_key"],
            base_url=config["embedding"].get("base_url")
        )
        response = client.embeddings.create(
            model=model,
            input=text
        )
        return response.data[0].embedding

    elif provider == "ollama":
        # Ollama（本地部署）
        import requests
        base_url = config["embedding"].get("base_url", "http://localhost:11434")
        response = requests.post(
            f"{base_url}/api/embed",
            json={
                "model": model,
                "input": text
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    elif provider == "bge":
        # BGE 本地模型（需要 transformers）
        from transformers import AutoTokenizer, AutoModel
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model)
        model_obj = AutoModel.from_pretrained(model)

        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = model_obj(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]

        return embeddings[0].numpy().tolist()

    else:
        raise ValueError(f"不支持的 embedding provider: {provider}")


def get_embeddings_batch(texts, config=None):
    """批量获取多个文本的向量。"""
    if config is None:
        config = load_embedding_config()

    embeddings = []
    for text in texts:
        embedding = get_embedding(text, config)
        embeddings.append(embedding)
    return embeddings


if __name__ == "__main__":
    # 测试向量化功能
    config = load_embedding_config()
    text = "这是一个测试文本"
    embedding = get_embedding(text, config)
    logger.debug(f"维度: {len(embedding)}")
    logger.debug(f"前 10 个值: {embedding[:10]}")
    print(f"测试成功: 维度={len(embedding)}")
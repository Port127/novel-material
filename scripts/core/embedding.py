#!/usr/bin/env python
"""Embedding 工具：将文本转换为向量。"""
import sys
import yaml
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.paths import CONFIG_DIR

def load_embedding_config():
    with open(CONFIG_DIR / "embedding.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_embedding(text, config=None):
    """获取文本的 embedding 向量。"""
    if config is None:
        config = load_embedding_config()

    provider = config["embedding"]["provider"]
    model = config["embedding"]["model"]

    if provider == "openai":
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

    elif provider == "bge":
        # 本地 BGE 模型
        from transformers import AutoTokenizer, AutoModel
        import torch

        tokenizer = AutoTokenizer.from_pretrained(model)
        model_obj = AutoModel.from_pretrained(model)

        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = model_obj(**inputs)
            # 使用 [CLS] 向量或 mean pooling
            embeddings = outputs.last_hidden_state[:, 0, :]

        return embeddings[0].numpy().tolist()

    else:
        raise ValueError(f"不支持的 embedding provider: {provider}")

def get_embeddings_batch(texts, config=None):
    """批量获取 embedding。"""
    if config is None:
        config = load_embedding_config()

    embeddings = []
    for text in texts:
        embedding = get_embedding(text, config)
        embeddings.append(embedding)
    return embeddings

if __name__ == "__main__":
    config = load_embedding_config()
    text = "这是一个测试文本"
    embedding = get_embedding(text, config)
    print(f"维度: {len(embedding)}")
    print(f"前 10 个值: {embedding[:10]}")

import os

os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.1-flash-lite")
os.environ.setdefault("GLM_MODEL", "glm-4-flash")
os.environ.setdefault("OPENROUTER_MODEL", "deepseek/deepseek-chat")
os.environ.setdefault("DEEPSEEK_MODEL", "deepseek-chat")
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:1.5b")

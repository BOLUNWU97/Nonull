# LLM Setup / LLM 配置

Nonull can use any OpenAI-compatible LLM API. The default is OpenAI, but
the same code works with Anthropic (via proxy), DeepSeek, MiniMax, Kimi,
Ollama (local), vLLM, or any custom endpoint.

## Configuration

Set these environment variables (in `.env` or your shell):

```bash
NONULL_LLM_API_KEY=sk-your-key-here
NONULL_LLM_PROVIDER=openai  # openai | anthropic | deepseek | ollama | custom
NONULL_LLM_MODEL=gpt-4o
NONULL_LLM_API_BASE=https://api.openai.com/v1  # override for custom endpoints
```

## Provider-specific notes

### OpenAI (default)
```bash
NONULL_LLM_API_KEY=sk-...
NONULL_LLM_PROVIDER=openai
NONULL_LLM_MODEL=gpt-4o
```

### Anthropic (via OpenAI-compatible proxy)
```bash
NONULL_LLM_API_KEY=sk-ant-...
NONULL_LLM_PROVIDER=custom
NONULL_LLM_API_BASE=https://api.anthropic.com/v1
NONULL_LLM_MODEL=claude-sonnet-4
```

### DeepSeek
```bash
NONULL_LLM_API_KEY=sk-...
NONULL_LLM_PROVIDER=deepseek
NONULL_LLM_MODEL=deepseek-chat
```

### MiniMax / MiniMax / Kimi
```bash
NONULL_LLM_API_KEY=your-key
NONULL_LLM_PROVIDER=custom
NONULL_LLM_API_BASE=https://your-endpoint/v1
NONULL_LLM_MODEL=your-model
```

### Ollama (local)
```bash
# First: ollama serve
NONULL_LLM_API_KEY=ollama  # any non-empty value
NONULL_LLM_PROVIDER=ollama
NONULL_LLM_MODEL=llama3
```

## Verifying the setup

```bash
# Quick check: imports work
python -c "from core import Nonull; print('OK')"

# Real call: ask the agent something
python -c "from core import Nonull; print(Nonull().run_sync('Hi').get('status'))"
# Should print: ok (with a valid key) or no_llm (without)
```

## Security

- `.env` is gitignored
- Never commit your API key
- Use environment-specific keys for different deployment environments
- For CI/CD, use secret management (GitHub Secrets, etc.)

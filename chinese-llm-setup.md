# Chinese LLM Setup Guide

This guide helps you configure and use Chinese LLM providers in Corvos.

---

## Supported Providers

Corvos now supports the following Chinese LLMs:

- **DeepSeek** - High-performance AI models
- **Alibaba Qwen** - Alibaba Cloud Qwen large language models
- **Moonshot Kimi** - Moonshot AI Kimi large language models
- **Zhipu AI GLM** - Zhipu AI GLM series models
- **MiniMax** - MiniMax large models (M2.5 series, 204K context)

---

## Quick Start

### General Configuration Steps

1. Log in to the Corvos Dashboard
2. Go to **Settings** -> **API Keys** (or **LLM Configurations**)
3. Click **Add Model**
4. Select your Chinese LLM provider from the **Provider** dropdown
5. Fill in the required fields (see provider-specific details below)
6. Click **Save**

---

## 1. DeepSeek Configuration

### Get Your API Key

1. Visit the [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up and log in
3. Go to the **API Keys** page
4. Click **Create New API Key**
5. Copy the generated API key (format: `sk-xxx`)

### Configure in Corvos

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | `DeepSeek Chat` | Custom name of your choice |
| **Provider** | `DEEPSEEK` | Select DeepSeek |
| **Model Name** | `deepseek-chat` | Recommended; also available: `deepseek-coder` |
| **API Key** | `sk-xxx...` | Your DeepSeek API key |
| **API Base URL** | `https://api.deepseek.com` | DeepSeek API endpoint |
| **Parameters** | _(leave empty)_ | Uses default parameters |

### Example Configuration

```
Configuration Name: DeepSeek Chat
Provider: DEEPSEEK
Model Name: deepseek-chat
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://api.deepseek.com
```

### Available Models

- **deepseek-chat**: General-purpose conversation model (recommended)
- **deepseek-coder**: Code-specialized model

### Pricing
- Visit the [DeepSeek pricing page](https://platform.deepseek.com/pricing) for the latest rates

---

## 2. Alibaba Qwen Configuration

### Get Your API Key

1. Visit the [Alibaba Cloud DashScope Platform](https://dashscope.aliyun.com/)
2. Log in with your Alibaba Cloud account
3. Enable the DashScope service
4. Go to **API Key Management**
5. Create and copy your API key

### Configure in Corvos

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | `Qwen Max` | Custom name of your choice |
| **Provider** | `ALIBABA_QWEN` | Select Alibaba Qwen |
| **Model Name** | `qwen-max` | Recommended; also available: `qwen-plus`, `qwen-turbo` |
| **API Key** | `sk-xxx...` | Your DashScope API key |
| **API Base URL** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Alibaba Cloud API endpoint |
| **Parameters** | _(leave empty)_ | Uses default parameters |

### Example Configuration

```
Configuration Name: Qwen Max
Provider: ALIBABA_QWEN
Model Name: qwen-max
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
```

### Available Models

- **qwen-max**: Best performance, suited for complex tasks
- **qwen-plus**: Great value, suited for everyday use (recommended)
- **qwen-turbo**: Fast speed, suited for simple tasks

### Pricing
- Visit the [Alibaba Cloud DashScope pricing page](https://help.aliyun.com/zh/model-studio/getting-started/billing) for the latest rates

---

## 3. Moonshot Kimi Configuration

### Get Your API Key

1. Visit the [Moonshot AI Platform](https://platform.moonshot.cn/)
2. Sign up and log in
3. Go to **API Key Management**
4. Create a new API key
5. Copy the API key

### Configure in Corvos

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | `Kimi` | Custom name of your choice |
| **Provider** | `MOONSHOT` | Select Moonshot Kimi |
| **Model Name** | `moonshot-v1-32k` | Recommended; also available: `moonshot-v1-8k`, `moonshot-v1-128k` |
| **API Key** | `sk-xxx...` | Your Moonshot API key |
| **API Base URL** | `https://api.moonshot.cn/v1` | Moonshot API endpoint |
| **Parameters** | _(leave empty)_ | Uses default parameters |

### Example Configuration

```
Configuration Name: Kimi 32K
Provider: MOONSHOT
Model Name: moonshot-v1-32k
API Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://api.moonshot.cn/v1
```

### Available Models

- **moonshot-v1-8k**: 8K context (basic)
- **moonshot-v1-32k**: 32K context (recommended)
- **moonshot-v1-128k**: 128K context (long-text tasks)

### Pricing
- Visit the [Moonshot AI pricing page](https://platform.moonshot.cn/pricing) for the latest rates

---

## 4. Zhipu AI GLM Configuration

### Get Your API Key

1. Visit the [Zhipu AI Platform](https://open.bigmodel.cn/)
2. Sign up and log in
3. Go to **API Management**
4. Create a new API key
5. Copy the API key

### Configure in Corvos

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | `GLM-4` | Custom name of your choice |
| **Provider** | `ZHIPU` | Select Zhipu AI |
| **Model Name** | `glm-4` | Recommended; also available: `glm-4-flash`, `glm-3-turbo` |
| **API Key** | `xxx.yyy...` | Your Zhipu API key |
| **API Base URL** | `https://open.bigmodel.cn/api/paas/v4` | Zhipu API endpoint |
| **Parameters** | _(leave empty)_ | Uses default parameters |

### Example Configuration

```
Configuration Name: GLM-4
Provider: ZHIPU
Model Name: glm-4
API Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxx
API Base URL: https://open.bigmodel.cn/api/paas/v4
```

### Available Models

- **glm-4**: GLM-4 flagship model (recommended)
- **glm-4-flash**: Fast inference variant
- **glm-3-turbo**: Cost-effective variant

### Pricing
- Visit the [Zhipu AI pricing page](https://open.bigmodel.cn/pricing) for the latest rates

---

## 5. MiniMax Configuration

### Get Your API Key

1. Visit the [MiniMax Platform](https://platform.minimaxi.com/)
2. Sign up and log in
3. Go to the **API Keys** page
4. Create a new API key
5. Copy the API key

### Configure in Corvos

| Field | Value | Notes |
|-------|-------|-------|
| **Configuration Name** | `MiniMax M3` | Custom name of your choice |
| **Provider** | `MINIMAX` | Select MiniMax |
| **Model Name** | `MiniMax-M3` | Recommended; also available: `MiniMax-M2.7`, `MiniMax-M2.7-highspeed` |
| **API Key** | `eyJ...` | Your MiniMax API key |
| **API Base URL** | `https://api.minimax.io/v1` | MiniMax API endpoint |
| **Parameters** | `{"temperature": 1.0}` | Note: temperature must be in (0.0, 1.0] range, cannot be 0 |

### Example Configuration

```
Configuration Name: MiniMax M3
Provider: MINIMAX
Model Name: MiniMax-M3
API Key: eyJxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
API Base URL: https://api.minimax.io/v1
```

### Available Models

- **MiniMax-M3**: Flagship model with 512K context window (recommended)
- **MiniMax-M2.7**: Previous-generation general model with 204K context window
- **MiniMax-M2.7-highspeed**: Previous-generation fast inference variant with 204K context window

### Important Notes

- **Temperature parameter**: MiniMax requires temperature to be in the (0.0, 1.0] range; it cannot be set to 0. Using 1.0 is recommended.
- M3 supports a 512K ultra-long context; the M2.7 series retains 204K. Choose based on your needs.

### Pricing
- Visit the [MiniMax pricing page](https://platform.minimaxi.com/document/Price) for the latest rates

---

## Advanced Configuration

### Custom Parameters

You can add custom parameters in the **Parameters** field (JSON format):

```json
{
  "temperature": 0.7,
  "max_tokens": 2000,
  "top_p": 0.9
}
```

### Common Parameter Reference

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `temperature` | Controls output randomness; higher = more random | 0.7 | 0.0 - 1.0 |
| `max_tokens` | Maximum number of output tokens | Model default | 1 - model limit |
| `top_p` | Nucleus sampling parameter | 1.0 | 0.0 - 1.0 |

---

## Troubleshooting

### Common Issues

#### 1. Error: "Invalid API Key"
- Check that the API key was copied correctly (no extra spaces)
- Confirm the API key is activated
- Check that your account balance is sufficient

#### 2. Error: "Connection timeout"
- Confirm the API Base URL is correct
- Check your network connection
- Confirm your firewall allows access to the endpoint

#### 3. Error: "Model not found"
- Confirm the model name is spelled correctly
- Check that the model is enabled on your account
- Refer to the available model names listed above

#### 4. Document processing stuck (IN_PROGRESS)
- Check for extra spaces in the model name
- Confirm the API key is valid and has quota
- Check backend logs: `docker compose logs backend`

### Viewing Logs

```bash
# View backend logs
docker compose logs backend --tail 100

# View logs in real time
docker compose logs -f backend

# Search for errors
docker compose logs backend | grep -i "error"
```

---

## Best Practices

### 1. Model Selection Guide

| Task Type | Recommended Model | Notes |
|-----------|-------------------|-------|
| **Document summarization** | Qwen-Plus, GLM-4 | Balance performance and cost |
| **Code analysis** | DeepSeek-Coder | Code-specialized |
| **Long-text processing** | Kimi 128K, MiniMax-M3 (512K) | Ultra-long context |
| **Fast responses** | Qwen-Turbo, GLM-4-Flash, MiniMax-M2.7-highspeed | Speed-first |

### 2. Cost Optimization

- **Long Context LLM**: Use Qwen-Plus or GLM-4 (document summarization)
- **Fast LLM**: Use Qwen-Turbo or GLM-4-Flash (quick conversations)
- **Strategic LLM**: Use Qwen-Max or DeepSeek-Chat (complex reasoning)

### 3. API Key Security

- Do not hard-code API keys in public code
- Rotate API keys regularly
- Create separate keys for different purposes
- Set reasonable quota limits

---

## Resources

### Official Documentation

- [DeepSeek Docs](https://platform.deepseek.com/docs)
- [Alibaba Cloud DashScope Docs](https://help.aliyun.com/zh/model-studio/)
- [Moonshot AI Docs](https://platform.moonshot.cn/docs)
- [Zhipu AI Docs](https://open.bigmodel.cn/dev/api)
- [MiniMax Docs](https://platform.minimaxi.com/document/Guides)

### Corvos Documentation

- [Installation Guide](../README.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md)

---

## Need Help?

If you run into issues, you can get help through:

- [GitHub Issues](https://github.com/HafizMMoaz/Corvos/issues)
- [Discord Community](https://discord.gg/Ggf9PxDNQ2)
- Email: [project maintainer email]

---

## Changelog

- **2025-01-12**: Initial release; added DeepSeek, Qwen, Kimi, GLM support

---

**Happy coding with Chinese LLMs!**

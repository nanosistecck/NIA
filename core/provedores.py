# -*- coding: utf-8 -*-
"""Catálogo de provedores de IA — portado do FreeLLMAPI.

O usuario escolhe o provedor no cadastro de chaves e adiciona quantas chaves
quiser do mesmo provedor ou de varios. Cada entrada traz:

    nome     -> rotulo amigavel exibido na UI
    base_url -> endpoint (vazio = o usuario informa a URL no cadastro)
    keyless  -> funciona sem chave
    tipo     -> "llm" | "busca" | "voz" | "imagem"
    modelos  -> modelos conhecidos do provedor

O motor do JARVIS (core/llm_router.py) so chama os adaptadores que existem
hoje: Gemini, OpenAI, OpenRouter e Codex. Os demais ficam catalogados para o
cadastro e para os adaptadores genericos OpenAI-compat.
"""
from __future__ import annotations

PROVEDORES: dict[str, dict] = {
    "aclide": {
        "nome": "Aclide",
        "base_url": "https://aclide.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "agnes": {
        "nome": "Agnes AI",
        "base_url": "https://apihub.agnes-ai.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "aihorde": {
        "nome": "AI Horde",
        "base_url": "https://oai.aihorde.net/v1",
        "keyless": True,
        "tipo": "imagem",
        "modelos": [],
    },
    "ainative": {
        "nome": "AINative Studio",
        "base_url": "https://api.ainative.studio/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "aion": {
        "nome": "Aion Labs",
        "base_url": "https://api.aionlabs.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "airforce": {
        "nome": "Api.Airforce",
        "base_url": "https://api.airforce/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "anyapi": {
        "nome": "AnyAPI",
        "base_url": "https://api.anyapi.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "apinex": {
        "nome": "APINex",
        "base_url": "https://api.apinex.bond/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "bai": {
        "nome": "B.AI",
        "base_url": "https://api.b.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "bazaarlink": {
        "nome": "BazaarLink",
        "base_url": "https://bazaarlink.ai/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "beatapi": {
        "nome": "BeatAPI",
        "base_url": "https://api.beatapi.io/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "blaze": {
        "nome": "BlazeAPI",
        "base_url": "https://api.blazeapi.org/paid/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "blockrun": {
        "nome": "BlockRun",
        "base_url": "https://api.blockrun.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "brave": {
        "nome": "Brave Search",
        "base_url": "https://api.search.brave.com/res/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "cerebras": {
        "nome": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["qwen-3-coder-480b", "llama-4-maverick-17b-128e-instruct", "qwen3-235b", "gpt-oss-120b", "llama3.1-8b"],
    },
    "clod": {
        "nome": "CLOD",
        "base_url": "https://api.clod.io/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "cloudflare": {
        "nome": "Cloudflare Workers AI",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["@cf/meta/llama-3.1-70b-instruct", "@cf/openai/gpt-oss-120b", "@cf/zai-org/glm-4.7-flash", "@cf/meta/llama-4-scout-17b-16e-instruct", "@cf/moonshotai/kimi-k2.5", "@cf/qwen/qwen3-30b-a3b-fp8", "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", "@cf/moonshotai/kimi-k2.6", "@cf/ibm-granite/granite-4.0-h-micro", "@cf/nvidia/nemotron-3-120b-a12b", "@cf/google/gemma-4-26b-a4b-it"],
    },
    "cohere": {
        "nome": "Cohere",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["command-r-plus-08-2024", "command-a-03-2025", "command-a-reasoning-08-2025", "command-r-08-2024"],
    },
    "custom": {
        "nome": "Endpoint customizado",
        "base_url": "",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "dreamprompting": {
        "nome": "DreamPrompting",
        "base_url": "https://dreamprompting.com/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "electronhub": {
        "nome": "ElectronHub",
        "base_url": "https://api.electronhub.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "exa": {
        "nome": "Exa",
        "base_url": "https://api.exa.ai",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "experiential": {
        "nome": "Experiential Labs",
        "base_url": "https://api.experientiallabs.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "firecrawl": {
        "nome": "Firecrawl",
        "base_url": "https://api.firecrawl.dev/v2",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "freeai": {
        "nome": "Free.ai",
        "base_url": "https://api.free.ai",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "freeinference": {
        "nome": "FreeInference",
        "base_url": "https://freeinference.org/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "freemodel": {
        "nome": "FreeModel",
        "base_url": "https://freemodel.in/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "freetts": {
        "nome": "FreeTTS",
        "base_url": "",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "github": {
        "nome": "GitHub Models",
        "base_url": "https://models.github.ai/inference",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["openai/gpt-5", "openai/gpt-4.1"],
    },
    "gizmo": {
        "nome": "Gizmo",
        "base_url": "https://api.gizmoplatforms.com/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "google": {
        "nome": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemma-4-31b-it", "gemma-4-26b-a4b-it"],
    },
    "groq": {
        "nome": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["llama-3.3-70b-versatile", "llama-4-scout-17b-16e-instruct", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b", "llama-3.1-8b-instant", "groq/compound", "groq/compound-mini", "openai/gpt-oss-safeguard-20b"],
    },
    "halx": {
        "nome": "HAL-X (keyless)",
        "base_url": "",
        "keyless": True,
        "tipo": "busca",
        "modelos": [],
    },
    "huggingface": {
        "nome": "HuggingFace Router",
        "base_url": "https://router.huggingface.co/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["accounts/fireworks/models/llama-v3p3-70b-instruct", "deepseek-ai/DeepSeek-V4-Flash", "moonshotai/Kimi-K2.6", "Qwen/Qwen3-Coder-Next"],
    },
    "inferbase": {
        "nome": "Inferbase",
        "base_url": "https://api.inferbase.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "iteracompute": {
        "nome": "IteraCompute",
        "base_url": "https://api.iteracompute.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "jamai": {
        "nome": "JamAI Base",
        "base_url": "https://api.jamaibase.com/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "keenable": {
        "nome": "Keenable",
        "base_url": "https://api.keenable.ai/v1",
        "keyless": True,
        "tipo": "busca",
        "modelos": [],
    },
    "kenari": {
        "nome": "Kenari",
        "base_url": "https://kenari.id/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "kilo": {
        "nome": "Kilo Gateway",
        "base_url": "https://api.kilo.ai/api/gateway/v1",
        "keyless": True,
        "tipo": "llm",
        "modelos": ["nvidia/nemotron-3-super-120b-a12b:free", "poolside/laguna-m.1:free", "poolside/laguna-xs.2:free", "stepfun/step-3.7-flash:free"],
    },
    "kiosapi": {
        "nome": "KiosAPI",
        "base_url": "https://api.kiosapi.id/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "linkup": {
        "nome": "Linkup",
        "base_url": "https://api.linkup.so/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "llm7": {
        "nome": "LLM7",
        "base_url": "https://api.llm7.io/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["gpt-oss-20b", "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "codestral-latest", "ministral-8b-2512", "GLM-4.6V-Flash"],
    },
    "llmtr": {
        "nome": "LLMTR",
        "base_url": "https://llmtr.com/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "logfare": {
        "nome": "Logfare",
        "base_url": "https://logfare.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "longcat": {
        "nome": "LongCat",
        "base_url": "https://api.longcat.chat/openai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "lucidity": {
        "nome": "Lucidity Composite",
        "base_url": "https://composite.lucidity.sh/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "meldport": {
        "nome": "Meldport",
        "base_url": "https://api.meldport.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "minimax": {
        "nome": "MiniMax",
        "base_url": "https://api.minimax.io/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["MiniMax-M1"],
    },
    "mistral": {
        "nome": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["mistral-large-latest", "magistral-medium-latest", "codestral-latest", "devstral-latest", "mistral-medium-latest", "mistral-small-latest", "ministral-8b-latest"],
    },
    "modelscope": {
        "nome": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "moondream": {
        "nome": "Moondream",
        "base_url": "https://api.moondream.ai/v1",
        "keyless": False,
        "tipo": "imagem",
        "modelos": [],
    },
    "moonshot": {
        "nome": "Moonshot",
        "base_url": "https://api.moonshot.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["kimi-latest"],
    },
    "nabh": {
        "nome": "nabh.cloud",
        "base_url": "https://api.nabh.cloud/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "nara": {
        "nome": "NaraRouter",
        "base_url": "https://router.bynara.id/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "navy": {
        "nome": "NavyAI",
        "base_url": "https://api.navy/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "novai": {
        "nome": "Novai",
        "base_url": "https://aiapi-pro.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "nvidia": {
        "nome": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["meta/llama-3.1-70b-instruct", "meta/llama-3.3-70b-instruct", "meta/llama-4-maverick-17b-128e-instruct", "deepseek-ai/deepseek-v4-pro", "mistralai/mistral-large-3-675b-instruct-2512", "minimaxai/minimax-m2.7", "nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3-nano-30b-a3b", "google/gemma-4-31b-it", "moonshotai/kimi-k2.6", "deepseek-ai/deepseek-v4-flash", "z-ai/glm-5.1", "qwen/qwen3-coder-480b-a35b-instruct"],
    },
    "ollama": {
        "nome": "Ollama",
        "base_url": "https://ollama.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["qwen3-coder:480b", "mistral-large-3:675b", "deepseek-v3.2", "cogito-2.1:671b", "kimi-k2-thinking", "glm-4.7", "gpt-oss:120b", "devstral-2:123b", "gpt-oss:20b", "gemma4:31b", "qwen3-coder-next"],
    },
    "onomeo": {
        "nome": "Onomeo",
        "base_url": "https://onomeo.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "openai": {
        "nome": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["gpt-5.6-luna", "gpt-4o-mini", "gpt-4o"],
    },
    "opencode": {
        "nome": "OpenCode Zen",
        "base_url": "https://opencode.ai/zen/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["big-pickle", "deepseek-v4-flash-free", "mimo-v2.5-free", "nemotron-3-super-free", "nemotron-3-ultra-free", "minimax-m3-free"],
    },
    "openrouter": {
        "nome": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["deepseek/deepseek-v3.1:free", "moonshotai/kimi-k2:free", "qwen/qwen3-coder:free", "z-ai/glm-4.5-air:free", "nvidia/nemotron-3-super-120b-a12b:free", "qwen/qwen3-next-80b-a3b-instruct:free", "minimax/minimax-m2.5:free", "google/gemma-4-31b-it:free", "inclusionai/ling-2.6-flash:free", "arcee-ai/trinity-large-preview:free", "nvidia/nemotron-3-nano-30b-a3b:free", "openai/gpt-oss-120b:free", "openai/gpt-oss-20b:free", "meta-llama/llama-3.3-70b-instruct:free", "liquid/lfm-2.5-1.2b-instruct:free", "inclusionai/ling-2.6-1t:free", "tencent/hy3-preview:free", "poolside/laguna-m.1:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "poolside/laguna-xs.2:free", "nvidia/nemotron-nano-9b-v2:free", "liquid/lfm-2.5-1.2b-thinking:free", "arcee-ai/trinity-large-thinking:free", "baidu/cobuddy:free", "openrouter/owl-alpha", "nousresearch/hermes-3-llama-3.1-405b:free", "moonshotai/kimi-k2.6:free", "nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-nano-12b-v2-vl:free", "meta-llama/llama-3.2-3b-instruct:free", "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"],
    },
    "orcarouter": {
        "nome": "OrcaRouter",
        "base_url": "https://api.orcarouter.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "outcrawl": {
        "nome": "Outcrawl",
        "base_url": "https://api.outcrawl.ai/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "ovh": {
        "nome": "OVH AI Endpoints",
        "base_url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        "keyless": True,
        "tipo": "llm",
        "modelos": [],
    },
    "parallel": {
        "nome": "Parallel",
        "base_url": "https://api.parallel.ai/v1",
        "keyless": True,
        "tipo": "busca",
        "modelos": [],
    },
    "plugsky": {
        "nome": "Plugsky",
        "base_url": "https://plugsky.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "pollinations": {
        "nome": "Pollinations",
        "base_url": "https://gen.pollinations.ai/v1",
        "keyless": False,
        "tipo": "imagem",
        "modelos": ["openai-fast"],
    },
    "powertokens": {
        "nome": "PowerTokens",
        "base_url": "https://api.powertokens.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "qianfan": {
        "nome": "Baidu Qianfan",
        "base_url": "https://qianfan.baidubce.com/v2",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "radeon": {
        "nome": "AMD Radeon Cloud",
        "base_url": "https://developer.amd.com.cn/radeon/api/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "reka": {
        "nome": "Reka",
        "base_url": "https://api.reka.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "requesty": {
        "nome": "Requesty",
        "base_url": "https://router.requesty.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "rime": {
        "nome": "RIME",
        "base_url": "https://users.rime.ai/v1",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "router9": {
        "nome": "Router9",
        "base_url": "https://api.router9.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "routeway": {
        "nome": "Routeway",
        "base_url": "https://api.routeway.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "sail": {
        "nome": "Sail Research",
        "base_url": "https://api.sailresearch.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "sambanova": {
        "nome": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["Meta-Llama-3.3-70B-Instruct", "DeepSeek-V3.1", "DeepSeek-V3.2", "Llama-4-Maverick-17B-128E-Instruct", "gpt-oss-120b", "DeepSeek-V3.1-cb", "gemma-3-12b-it", "chutes"],
    },
    "sealion": {
        "nome": "SEA-LION",
        "base_url": "https://api.sea-lion.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "septor": {
        "nome": "Septor Labs",
        "base_url": "https://api.septorlabs.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "serpsearch": {
        "nome": "SerpSearch",
        "base_url": "https://api.serpsearch.com/api/v1",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "siliconflow": {
        "nome": "SiliconFlow",
        "base_url": "https://api.siliconflow.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "silvr": {
        "nome": "SilvR AI",
        "base_url": "https://api.silvrai.net/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "simplellm": {
        "nome": "SimpleLLM",
        "base_url": "https://api.simplellm.eu/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "speechflow": {
        "nome": "SpeechFlow",
        "base_url": "https://api.speechflow.io",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "speechify": {
        "nome": "Speechify",
        "base_url": "https://api.speechify.ai/v1",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "speka": {
        "nome": "Speka",
        "base_url": "https://speka.me/v1",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "tavily": {
        "nome": "Tavily",
        "base_url": "https://api.tavily.com",
        "keyless": False,
        "tipo": "busca",
        "modelos": [],
    },
    "typecast": {
        "nome": "Typecast",
        "base_url": "https://api.typecast.ai",
        "keyless": False,
        "tipo": "voz",
        "modelos": [],
    },
    "typhoon": {
        "nome": "Typhoon",
        "base_url": "https://api.opentyphoon.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "unorouter": {
        "nome": "UnoRouter",
        "base_url": "https://api.unorouter.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "varosity": {
        "nome": "Varosity",
        "base_url": "https://varosity.ai/api",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "volcengine": {
        "nome": "Volcengine Ark",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "waterfall": {
        "nome": "Waterfall",
        "base_url": "https://api.getwaterfall.org/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "xfyun": {
        "nome": "iFlytek Spark",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "xkiro": {
        "nome": "xKiro",
        "base_url": "https://api.xkiro.com/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
    "zhipu": {
        "nome": "Zhipu AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "keyless": False,
        "tipo": "llm",
        "modelos": ["glm-4.5-flash", "glm-4.7-flash", "glm-4.6v-flash"],
    },
    "zro": {
        "nome": "ZRO",
        "base_url": "https://zro.moonmath.ai/v1",
        "keyless": False,
        "tipo": "llm",
        "modelos": [],
    },
}


def nome_do_provedor(provedor: str) -> str:
    """Nome amigavel do provedor (ou o proprio id se desconhecido)."""
    spec = PROVEDORES.get(provedor)
    return str(spec.get("nome") if spec else None) or str(provedor or "").upper()


def modelos_do_provedor(provedor: str) -> list[str]:
    """Modelos conhecidos do provedor (lista vazia se desconhecido)."""
    spec = PROVEDORES.get(provedor) or {}
    return list(spec.get("modelos") or [])


def base_url_do_provedor(provedor: str) -> str:
    """Endpoint do provedor ("" quando o usuario precisa informar)."""
    spec = PROVEDORES.get(provedor) or {}
    return str(spec.get("base_url") or "")


def aceita_chave(provedor: str) -> bool:
    """True quando o provedor exige chave (nao e keyless)."""
    spec = PROVEDORES.get(provedor) or {}
    return not bool(spec.get("keyless"))


def provedores_por_tipo(tipo: str = "llm") -> list[str]:
    """Ids dos provedores de um tipo ("llm", "busca", "voz", "imagem")."""
    return [p for p, s in PROVEDORES.items() if str(s.get("tipo") or "llm") == tipo]

# -*- coding: utf-8 -*-
"""Cérebro GENÉRICO — qualquer provedor OpenAI-compatível do catálogo.

Por que existe
--------------
O catálogo (`core/provedores.py`) lista ~99 provedores, mas o motor só sabia
falar com Gemini, OpenAI, OpenRouter e Codex. Na prática, uma chave da Groq,
Cerebras, Mistral, SambaNova, NVIDIA, Together, DeepInfra etc. ficava guardada no
banco sem nunca ser usada — o cadastro prometia e o motor não entregava.

Quase todos esses provedores falam o MESMO dialeto: `POST {base_url}/chat/
completions` com o corpo da OpenAI. Então não é preciso um adaptador por
provedor: é um só, apontado para o `base_url` de cada um.

Contrato (igual aos outros cérebros do NIA)
----------------------------------------------
    responder(mensagens, ferramentas_openai, executor, forcar_ferramenta, timeout)
        -> {"texto": str, "chamou_ferramenta": bool}

    escrever_longo(instrucao, pedido, max_tokens, timeout) -> str

Troca de MODELO dentro do provedor
----------------------------------
Se o modelo configurado não existir mais (404 / "does not exist" / "not found"),
o próximo da lista do catálogo é tentado antes de desistir do provedor. É o
"troca entre modelos" do pedido original: a chave pode estar ótima e só o nome
do modelo ter saído do ar.

Erros viram `RuntimeError` com o texto do provedor, porque é esse texto que
`core.llm_router.classificar_erro` lê para decidir cooldown e fallback.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import time

from core import provedores as _catalogo
from core.http_seguranca import abrir, validar_endpoint, sanitizar

# Uma conexão viva por processo: o aperto de mão TLS custa ~0,4 s por chamada
# (mesma medição que está documentada em `cerebro_openai`). Se `requests`
# faltar, cai no `urlopen` e nada quebra.
_SESSAO = None
_FALHAS_MODELO = {}


def _sessao():
    global _SESSAO
    if _SESSAO is None:
        try:
            import requests  # noqa: PLC0415
            _SESSAO = requests.Session()
        except Exception:
            _SESSAO = False
    return _SESSAO or None


# Modelos que indicam "esse nome de modelo não existe mais aqui".
_ERRO_DE_MODELO = ("does not exist", "not found", "no such model", "invalid model",
                   "model_not_found", "unknown model", "unsupported model",
                   "model is not supported", "decommissioned")


def _e_erro_de_modelo(texto: str) -> bool:
    t = str(texto or "").lower()
    return "404" in t or any(x in t for x in _ERRO_DE_MODELO)


class CerebroGenerico:
    """Fala o dialeto OpenAI com o provedor que o catálogo indicar."""

    def __init__(self, provedor: str, chave: str | None = None, modelo: str | None = None,
                 router=None, base_url: str | None = None) -> None:
        self.provedor = str(provedor or "").strip().lower()
        self._gerenciada = not bool(chave)
        self._router = router
        self._modelo_override = modelo
        self._url_override = base_url
        if not self.provedor:
            raise RuntimeError("provedor nao informado")
        self._registro = None
        if self._gerenciada:
            from core.llm_router import resolver_conexao
            self._registro = resolver_conexao(self.provedor, router)
            if self._registro is not None:
                chave = self._registro.chave
                modelo = modelo or self._registro.modelo
                base_url = base_url or self._registro.base_url
        self.chave = str(chave or "").strip()
        self.url = str(base_url or _catalogo.base_url_do_provedor(self.provedor) or "").strip()
        if not self.url:
            raise RuntimeError(
                f"provedor '{self.provedor}' sem base_url no catalogo: "
                f"informe a URL no cadastro de chaves")
        self.url = validar_endpoint(self.url)
        if not self.chave and _catalogo.aceita_chave(self.provedor):
            raise RuntimeError(f"provedor '{self.provedor}' sem chave cadastrada")
        # Lista de modelos tentados em ordem: o pedido, depois o catálogo.
        self.modelos: list[str] = []
        for m in [modelo] + _catalogo.modelos_do_provedor(self.provedor):
            m = str(m or "").strip()
            if m and m not in self.modelos:
                self.modelos.append(m)
        if not self.modelos:
            raise RuntimeError(
                f"nenhum modelo conhecido para '{self.provedor}': "
                f"informe o modelo no cadastro")
        self.modelo = self.modelos[0]
        self.ultimo_uso = {"tokens": 0}

    # ── HTTP ──────────────────────────────────────────────────────────────
    def _anotar_falha(self, texto: str) -> None:
        """A chave/provedor falhou: entra no castigo do roteador (18/11/2026).

        Sem isto, um provedor com 429 era tentado de novo a cada frase, e a
        chave nunca saia da fila — o rodizio/castigo so' funcionava nos
        cerebros nativos.
        """
        try:
            from core.llm_router import anotar_falha  # noqa: PLC0415
            if _e_erro_de_modelo(texto):
                return
            anotar_falha(self.provedor, texto, self.chave)
        except Exception:
            pass

    def _anotar_sucesso(self) -> None:
        try:
            from core.llm_router import anotar_sucesso  # noqa: PLC0415
            anotar_sucesso(self.provedor, self.chave)
        except Exception:
            pass

    def _postar(self, corpo: dict, timeout: float) -> dict:
        dados = json.dumps(corpo).encode("utf-8")
        cabeca = {"Content-Type": "application/json"}
        if self.chave:
            cabeca["Authorization"] = f"Bearer {self.chave}"
        alvo = f"{self.url}/chat/completions"
        ses = _sessao()
        if ses is not None:
            r = ses.post(alvo, data=dados, headers=cabeca, timeout=timeout, allow_redirects=False)
            if r.status_code >= 300:
                detalhe = ""
                try:
                    corpo_erro = r.json()
                    detalhe = (corpo_erro.get("error", {}) or {}).get("message", "") \
                        if isinstance(corpo_erro, dict) else ""
                except Exception:
                    detalhe = r.text[:180]
                erro = f"{self.provedor} {r.status_code}: {sanitizar(detalhe, self.chave)[:200]}"
                self._anotar_falha(erro)
                raise RuntimeError(erro) from None
            self._anotar_sucesso()
            return r.json()
        req = urllib.request.Request(alvo, data=dados, headers=cabeca)
        try:
            with abrir(req, timeout=timeout) as resp:
                dados_ok = json.loads(resp.read())
            self._anotar_sucesso()
            return dados_ok
        except urllib.error.HTTPError as e:
            detalhe = ""
            try:
                corpo_erro = json.loads(e.read())
                detalhe = (corpo_erro.get("error", {}) or {}).get("message", "") \
                    if isinstance(corpo_erro, dict) else ""
            except Exception:
                pass
            erro = f"{self.provedor} {e.code}: {sanitizar(detalhe, self.chave)[:200]}"
            self._anotar_falha(erro)
            raise RuntimeError(erro) from None
        except urllib.error.URLError as e:
            erro = f"{self.provedor} timeout: conexão indisponível"
            self._anotar_falha(erro)
            raise RuntimeError(erro) from None

    # ── conversão de mensagens ────────────────────────────────────────────
    @staticmethod
    def _mensagens(mensagens: list) -> list:
        """Mensagens do NIA -> formato chat/completions.

        O caminho da Gemini usa `system` uma vez só; aqui a lista já vem no
        formato certo, então só filtramos o que não é texto.
        """
        saida = []
        for m in mensagens or []:
            if not isinstance(m, dict):
                continue
            papel = str(m.get("role") or "user")
            texto = m.get("content")
            if papel == "tool":
                continue
            if texto is None:
                continue
            saida.append({"role": papel, "content": texto if isinstance(texto, str)
                          else json.dumps(texto, ensure_ascii=False)})
        return saida

    def _chamar(self, mensagens: list, ferramentas: list, forcar: bool,
                timeout: float, max_tokens: int, operacao='conversa') -> dict:
        """Faz a chamada tentando os modelos em ordem (rotação por modelo)."""
        if self._gerenciada:
            from core.llm_router import resolver_conexao
            registro = resolver_conexao(self.provedor, self._router)
            if registro is None and _catalogo.aceita_chave(self.provedor):
                raise RuntimeError('Provedor sem credencial disponível')
            if registro is not None:
                self._registro = registro
                self.chave = registro.chave
                self.url = validar_endpoint(self._url_override or registro.base_url or _catalogo.base_url_do_provedor(self.provedor))
                self.modelos = list(dict.fromkeys(filter(None, [self._modelo_override or registro.modelo] + _catalogo.modelos_do_provedor(self.provedor))))
        ultimo = ""
        for indice, modelo in enumerate(self.modelos):
            from hashlib import sha256
            identidade = sha256(self.chave.encode()).hexdigest()
            falha_id = (self.provedor, identidade, self.url, modelo,
                        operacao + ('_ferramentas' if ferramentas else ''))
            if _FALHAS_MODELO.get(falha_id, 0) > time.monotonic():
                continue
            corpo: dict = {
                "model": modelo,
                "messages": mensagens,
                "max_tokens": int(max_tokens),
                "temperature": 0.7,
            }
            if ferramentas:
                corpo["tools"] = ferramentas
                corpo["tool_choice"] = "required" if forcar else "auto"
            try:
                dados = self._postar(corpo, timeout)
            except Exception as exc:
                ultimo = str(exc)
                if _e_erro_de_modelo(ultimo):
                    _FALHAS_MODELO[falha_id] = time.monotonic() + 60
                # Modelo fora do ar: tenta o próximo ANTES de culpar a chave.
                if indice + 1 < len(self.modelos) and _e_erro_de_modelo(ultimo):
                    continue
                raise
            self.modelo = modelo
            from core.llm_client import registrar_resposta_conversa  # noqa: PLC0415
            registrar_resposta_conversa(self.provedor, modelo)
            try:
                gastos = int((dados.get("usage") or {}).get("total_tokens") or 0)
                self.ultimo_uso["tokens"] = gastos
                if gastos > 0 and self._registro is not None:
                    self._registro.uso_tokens = int(self._registro.uso_tokens) + gastos
                    if getattr(self._registro, "id", 0):
                        from core.db_chaves import registrar_uso  # noqa: PLC0415
                        registrar_uso(self._registro.id, gastos)
            except Exception:
                pass
            return dados
        raise RuntimeError(ultimo or f"{self.provedor}: sem resposta")

    @staticmethod
    def _resposta(dados: dict) -> dict:
        escolhas = dados.get("choices") or []
        if not escolhas:
            raise RuntimeError("resposta vazia do provedor")
        return escolhas[0].get("message") or {}

    # ── contrato dos cérebros ─────────────────────────────────────────────
    def responder(self, mensagens: list, ferramentas_openai: list, executor,
                  forcar_ferramenta: bool = False, timeout: float = 60.0) -> dict:
        """Conversa com ferramentas — teto de 3 rodadas, igual aos outros cérebros.

        Sem o teto, um modelo confuso pede ferramenta para sempre e o dono espera
        calado. É a mesma trava que já existe em `cerebro_openai` e
        `cerebro_openrouter`.
        """
        conversa = self._mensagens(mensagens)
        ferramentas = list(ferramentas_openai or [])
        chamou = False
        texto = ""
        forcar = bool(forcar_ferramenta)

        for _ in range(3):
            dados = self._chamar(conversa, ferramentas, forcar, timeout, 700)
            msg = self._resposta(dados)
            chamadas = msg.get("tool_calls") or []
            if not chamadas:
                texto = str(msg.get("content") or "").strip()
                break
            chamou = True
            forcar = False
            conversa.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": chamadas})
            for chamada in chamadas:
                funcao = (chamada or {}).get("function") or {}
                nome = str(funcao.get("name") or "")
                try:
                    argumentos = json.loads(funcao.get("arguments") or "{}")
                except Exception:
                    argumentos = {}
                try:
                    resultado = executor(nome, argumentos) if executor else "Ferramenta indisponivel."
                except Exception as exc:
                    resultado = f"A ferramenta falhou: {str(exc)[:160]}"
                conversa.append({"role": "tool",
                                 "tool_call_id": chamada.get("id"),
                                 "content": str(resultado)[:6000]})
        if chamou and not texto:
            texto = "Feito."
        return {"texto": texto, "chamou_ferramenta": chamou}

    def escrever_longo(self, instrucao: str, pedido: str, max_tokens: int = 9000,
                       timeout: float = 120.0) -> str:
        """Texto LONGO sem ferramenta (código inteiro, documento, plano)."""
        conversa = [{"role": "system", "content": str(instrucao)},
                    {"role": "user", "content": str(pedido)}]
        dados = self._chamar(conversa, [], False, timeout, int(max_tokens), operacao='texto')
        return str(self._resposta(dados).get("content") or "").strip()

# Falhas encontradas e classificadas

ID | Categoria | Sintoma | Causa real | Correção | Estado
---|---|---|---|---|---
L-001 | comprehension | Paráfrases de hora iam para o LLM no modo local | `_rede_do_relogio` ficava depois do ramo local em `_on_text_command` | movido para antes do cérebro local | corrigido
L-002 | comprehension | "me diga a hora", "horário atual" etc. não casavam | regex `_RE_SO_RELOGIO` incompleta | padrões adicionados | corrigido
L-003 | comprehension | "Como está meu computador?" ia para o modelo | rota determinística de status inexistente | `_responder_status_local` adicionada | corrigido
L-004 | fidelity | "Como está o tempo" / "pesquise..." não eram determinísticos | mesmo ramo local antecipado | `_responder_ferramenta_local` adicionada | corrigido
L-005 | automation | "Mude a reunião para as 15h" não era reconhecido | só aceitava data explícita | fallback para hoje com hora | corrigido
L-006 | automation | "Me avise antes da reunião" não era reconhecido | padrão ausente | padrão de aviso prévio adicionado | corrigido
L-007 | learning | "abra meu escritório" não recuperava associação | pontuação dividida pelo tamanho da frase e pontuação não removida | normalização e scoring ajustados | corrigido
L-008 | learning | "Agora X significa outra coisa" não era reconhecido | regex exigia fim sem pontuação | padrão aceita `.!?` | corrigido
L-009 | harness | painel com texto invisível | QLabel sem cor sob fundo escuro | tokens do tema aplicados | corrigido
B-001 | plugins | cenários de plugin dependem de `.niateck` real/upstream | dependência externa | registrados como bloqueados | bloqueado
B-002 | providers | fallback real exige credencial/roteador ao vivo | dependência externa controlada | bloqueado | bloqueado
B-003 | fidelity | planos/arquivos/whatsapp exigem decisão do modelo | não determinístico em modo local | bloqueado | bloqueado

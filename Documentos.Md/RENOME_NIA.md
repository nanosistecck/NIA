# Da troca de nome: JARVIS → NIA

Feito em 18/11/2026. Regra aplicada em todo o código: `JARVIS` → `NIA`,
`Jarvis` → `Nia`, `jarvis` → `nia`, `J.A.R.V.I.S` → `N.I.A` (maiúsculas e
minúsculas preservadas).

> Observação: o projeto usava `J.A.R.V.I.S` (com **R**), não `J.A.V.I.S`.
> Tratei a forma com R como a pretendida.

## O que mudou

- 100 arquivos de texto revisados (código Python, HTML/JS, JSON, config).
- Nomes de classes e símbolos internos: `JarvisUI` → `NiaUI`, `JarvisLive` →
  `NiaLive`, `shutdown_jarvis` → `shutdown_nia`, ícones, atalhos e títulos.
- Banco de chaves: `config/jarvis.db` → `config/nia.db` (cópia de segurança
  feita; o arquivo antigo ficou onde estava). Variável `NIA_DB_PATH` com
  compatibilidade com `JARVIS_DB_PATH`.
- Ícones versionados renomeados: `config/nia.ico` e
  `assets/icons/nia_installer_icon.ico`.
- **Compatibilidade preservada**: chaves, recados, perfis de navegador,
  pastas de projetos/resultados/uploads, token do painel, autostart e
  certificado continuam funcionando — o código reconhece o nome antigo onde
  ele já estava gravado no computador do cliente.

## O que NÃO foi mudado (e por quê)

### 1. Protocolo vivo com a VPS — muda só depois do servidor

Estes nomes são rotas/arquivos do servidor remoto. Mudá-los aqui antes de
atualizar a VPS quebra o relay e o Cowork imediatamente:

| Token | Onde | Por que ficou |
|---|---|---|
| `/jarvis-remote/`, `/jarvis-relay/device` | `dashboard/relay_client.py` | rotas HTTP/WS do servidor |
| `jarvis-cowork.js`, `jarvis-cerebro.js`, `jarvis-olhar.js`, `jarvis-ouvido.js` | comentários e contratos | arquivos na VPS (`central-bots/`) |
| `_jarvis_cowork/` | `actions/cowork.py` | nome da pasta no zip enviado ao worker |

### 2. Identidade criptográfica / sessões já gravadas

| Token | Motivo |
|---|---|
| `JARVIS-DASHBOARD-v1` (salt AES no Python e no HTML) | é a semente das chaves do painel; trocá-la invalida o pareamento de todos os celulares |
| `browser: ['JARVIS', 'Desktop', '1.0.40']` (`whatsapp_bridge/server.js`) | aparece como dispositivo pareado no WhatsApp; alterar pode derrubar a sessão |
| perfis Qt `jarvis_secretaria`, `jarvis_globo` | diretórios de perfil; trocar desloga o WhatsApp Web e perde cache do globo |
| `config/certs/jarvis.key` e `jarvis.crt` | certificado TLS já aceito nos aparelhos; o código prefere `nia.key/crt` se existirem |

### 3. Dados que não são do produto

- `globo/web/dados/estados.json` contém **Jarvis Island**, ilha real;
  `cidades.json` tem nomes geográficos parecidos.
- `globo/web/cesium/` é biblioteca de terceiros minificada — mexer nela
  corromperia o bundle.

### 4. Nomes antigos mantidos de propósito como *fallback*

Só entram em ação se o nome novo ainda não existe, para ninguém perder dados
na atualização:

- `config/jarvis.db`, `JARVIS_DB_PATH`, `config/certs/jarvis.key/crt`;
- `Documents/JARVIS Secretaria`, `~/.jarvis/reminders`, `~/.jarvis_profiles`,
  `Desktop/JarvisProjects`, `Desktop/JarvisResultados`, `Documents/JARVIS Cowork`,
  `~/Downloads|Documents/JARVIS Uploads`;
- valor `JARVIS CyberBot` no Registro do Windows, `jarvis-cyberbot.desktop`,
  `jarvis.sh`, `jarvis.png`, `JARVIS-CyberBot.exe`, mutex
  `Local\JARVIS-CyberBot-unico`, tranca `.jarvis-unico.lock`;
- chaves antigas do `localStorage`/`sessionStorage` (`jarvis_token`,
  `jarvis_key`, `jarvis_device_token`, `jarvis_quick_buttons`);
- marcadores `.jarvis_cowork/` e `.jarvis-cowork.json` dos projetos do Cowork.

### 5. Fora deste repositório

O aplicativo instalado em
`%LOCALAPPDATA%\Programs\JARVIS-CyberBot` (inclusive o que está rodando agora)
continua com o nome antigo até que um novo instalador/build seja gerado e
executado. O código aqui já procura `NIA-CyberBot.exe` **e** o nome antigo.

## Sugestões para evolir para NIA

1. **Servidor primeiro (VPS).** Publicar `/nia-remote/` e `/nia-relay/device`
   mantendo as rotas antigas por uma versão; renomear os `jarvis-*.js` para
   `nia-*.js` e o `_jarvis_cowork/` para `_nia_cowork/`, com aliases. Só então
   trocar as strings no cliente e remover os aliases.
2. **Pareamento.** Fazer uma janela de transição em que o painel lê o salt
   antigo e grava o novo; avisar os usuários para re-aceitar o certificado e
   parear de novo. Depois trocar `JARVIS-DASHBOARD-v1` e o descritor do
   WhatsApp para `['NIA', 'Desktop', ...]`.
3. **Perfis.** Script de migração que copia `~/.jarvis_profiles` →
   `.nia_profiles`, `~/.jarvis/reminders` → `~/.nia/reminders`,
   `JARVIS Secretaria` → `NIA Secretaria`, etc. Rodar com o aplicativo fechado.
4. **Build/instalador.** Renomear `JARVIS-CyberBot.exe` → `NIA-CyberBot.exe`,
   `jarvis.sh` → `nia.sh`, `jarvis.png` → `nia.png`, e revisar o `.iss`
   (AppName, ícones, chave de desinstalação). Atualizar o registro/atalhos na
   primeira execução, apagando os valores antigos.
5. **Limpeza.** Depois de uma versão inteira com os fallbacks ativos, medir
   quem ainda usa os nomes antigos (log) e remover o código de compatibilidade.
6. **Guarda-chuva de teste.** Manter uma suíte que falha se aparecer `jarvis`
   fora de uma lista de permissões (este arquivo, protocolo VPS e fallbacks).
   Ela impede que a troca de nome se desfaça aos poucos.

# Safe Evolution Mode

Este diretorio registra o contexto persistente da evolucao segura. Arquivos existentes nunca sao substituidos pelo instalador. Atualize-os a cada etapa, sem armazenar segredos ou dados privados.

Comando: `/evoluir-seguro <ideia>`; sem argumentos, retomar apenas depois de conferir o estado real do Git e dos testes.

O agente nao tem permissao automatica para operacoes destrutivas, push, deploy, migracoes ou mudancas em producao.

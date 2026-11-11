"""Enriquece o estado do LuzIA com a rubrica de Propriedade Intelectual (P1-P4),
o Observador de Sessão no Harness e o Roteiro Detalhado de 90 dias, 6 meses e 12 meses."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ST_PATH = ROOT / 'outputs' / 'sem2' / 'career_state.json'


def enrich() -> None:
    state = json.loads(ST_PATH.read_text(encoding='utf-8'))
    plan = state['plano']

    plan['preferencias_intervencao'] = {
        'intervencao_ativa_no_harness': True,
        'nivel_intervencao': 'Proativo ao detectar conceitos do plano (DDD, Arquitetura, Débito Técnico)',
        'bloquear_commit_sem_defesa_critica': False,
    }

    plan['oportunidades_tarefa_atual'] = [
        {
            'gatilho_detectado': 'Atividade no repositório: Integração Jev para classificação de anexos (12 arquivos C#/.NET)',
            'skill_alvo': 'Domain-Driven Design (DDD) · Subdomínios Principal, de Suporte e Genérico (Cap. 1)',
            'alerta_do_observador': (
                'Olha, aqui nesta atividade entrou exatamente a sua dúvida do Capítulo 1 de DDD registrada no Obsidian: '
                'classificar anexos via Jev é um Subdomínio de Suporte ou Genérico?'
            ),
            'teoria_na_pratica': (
                'Pelo critério de Khononov/Evans que você anotou no vault: como a classificação via Jev usa um serviço externo '
                'para apoiar a operação hospitalar sem ser o diferencial competitivo central do agendamento cirúrgico, ela deve '
                'ficar isolada atrás de uma Anti-Corruption Layer (ACL), sem vazar enums/DTOs da Jev para as entidades do domínio principal.'
            ),
            'como_praticar_com_agente': (
                'Peça ao Claude Code para extrair uma interface de domínio limpa (ex.: IClassificadorAnexo) antes de chamar o '
                'cliente HTTP da Jev, mantendo a regra de negócio desacoplada do fornecedor.'
            ),
            'evitar_delegacao_cega': (
                'Não aceite que o agente espalhe tipos específicos da API externa dentro das classes de domínio ou controllers '
                'legados (isso gera débito técnico imediato de acoplamento).'
            ),
        },
        {
            'gatilho_detectado': 'Atividade no repositório: Notificação de e-mail para clínica de agulhamento (+476/-16 linhas)',
            'skill_alvo': 'Arquitetura .NET / Clean Architecture · Desacoplamento e Responsabilidade Única (SOLID)',
            'alerta_do_observador': (
                'Oportunidade detectada na sessão: o disparo de e-mail dentro do fluxo de salvamento do pedido exercita '
                'desacoplamento arquitetural e prevenção de débito técnico rumo a Pleno.'
            ),
            'teoria_na_pratica': (
                'Misturar montagem de template HTML e chamada SMTP (Brevo) diretamente no fluxo de persistência do pedido '
                'viola o Single Responsibility Principle e arrisca derrubar a gravação do pedido se o servidor de e-mail falhar.'
            ),
            'como_praticar_com_agente': (
                'Oriente o agente a separar a persistência do pedido do serviço de notificação e a centralizar o template HTML '
                'em um único ponto reutilizável entre Web e API.'
            ),
            'evitar_delegacao_cega': (
                'Revise onde o agente posicionou o tratamento de exceções do envio de e-mail para garantir que falhas de rede '
                'não afetem a transação principal.'
            ),
        },
        {
            'gatilho_detectado': 'Atividade no repositório: Refatoração do bate-mapa (+551/-1071 linhas em C#, JS e Razor)',
            'skill_alvo': 'Testes e Qualidade / Redução de Débito Técnico em Sistemas Legados',
            'alerta_do_observador': (
                'Você está removendo mais de 1.000 linhas de fluxo legado no bate-mapa com ajuda da IA — momento ideal para '
                'praticar testes de caracterização e proteção de regras de negócio.'
            ),
            'teoria_na_pratica': (
                'Em legados ASP.NET MVC 5 com lógica mista em C# e JavaScript, grandes remoções feitas por agentes podem apagar '
                'regras silenciosas (como cálculo de risco de atraso ou visibilidade do acionamento da diretoria).'
            ),
            'como_praticar_com_agente': (
                'Antes de aplicar a refatoração do agente, peça para ele listar todas as invariantes de negócio do módulo e gerar '
                'testes unitários XUnit cobrindo o cálculo de atraso.'
            ),
            'evitar_delegacao_cega': (
                'Não valide refatorações extensas apenas pelo layout visual; confira cada condicional de negócio removida no diff.'
            ),
        },
    ]

    plan['tarefas_recentes'] = [
        {
            'tarefa': 'refactor: reutiliza padrão de descrição dos enums Jev (3 arquivos, +18/-5)',
            'skills': ['Back-end C# / .NET e Integrações', 'Arquitetura .NET / Clean Architecture'],
            'propriedade': 'alta',
            'indice_propriedade': 84,
            'risco_debito_tecnico': 'Baixo (eliminou duplicação deixada na entrega anterior)',
            'parametros': {
                'p1_rastro_prompt': {
                    'nome': 'P1 · Direção no Prompt vs. Delegação',
                    'nota': 85,
                    'detalhe': 'Ação conduzida de forma direcionada após revisão para unificar o padrão de leitura de enums.',
                },
                'p2_granularidade_commit': {
                    'nome': 'P2 · Granularidade e Coesão do Commit',
                    'nota': 92,
                    'detalhe': 'Commit atômico e cirúrgico (+18/-5 em 3 arquivos), com escopo único e sem ruído.',
                },
                'p3_conexao_estudo': {
                    'nome': 'P3 · Conexão com Estudo / Vault Autoral',
                    'nota': 78,
                    'detalhe': 'Converge com boas práticas de Clean Code e consistência do modelo.',
                },
                'p4_defesa_tecnica': {
                    'nome': 'P4 · Defesa de Decisão e Trade-offs',
                    'nota': 80,
                    'detalhe': 'Escolha consciente de reutilizar o helper do projeto em vez de manter lógica paralela.',
                },
            },
            'por_que': (
                'Commit focado e intencional atendendo code review, mostrando controle sobre como os enumeradores '
                'são expostos e mantendo baixo débito técnico.'
            ),
            'pergunta_do_lider': (
                'Por que centralizar a leitura de DescriptionAttribute dos enums evita divergência quando novas '
                'classificações da Jev forem adicionadas?'
            ),
        },
        {
            'tarefa': 'fix(bate-mapa): corrige alerta, status e filtro de regime (8 arquivos, +167/-49)',
            'skills': ['Back-end C# / .NET e Integrações', 'Front-end (JS / Razor / React)'],
            'propriedade': 'media',
            'indice_propriedade': 62,
            'risco_debito_tecnico': 'Médio (regra de status distribuída entre C# e JavaScript)',
            'parametros': {
                'p1_rastro_prompt': {
                    'nome': 'P1 · Direção no Prompt vs. Delegação',
                    'nota': 72,
                    'detalhe': 'Investigação guiada pela desenvolvedora em cima de defeito real do fluxo cirúrgico.',
                },
                'p2_granularidade_commit': {
                    'nome': 'P2 · Granularidade e Coesão do Commit',
                    'nota': 58,
                    'detalhe': 'Agrupou três ajustes distintos (alerta, status e filtro de regime) no mesmo commit.',
                },
                'p3_conexao_estudo': {
                    'nome': 'P3 · Conexão com Estudo / Vault Autoral',
                    'nota': 65,
                    'detalhe': 'Toca regras de um subdomínio operacional importante sem separar ainda a lógica de UI.',
                },
                'p4_defesa_tecnica': {
                    'nome': 'P4 · Defesa de Decisão e Trade-offs',
                    'nota': 52,
                    'detalhe': 'Falta explicitar a fronteira entre o cálculo no back-end C# e a manipulação no JS.',
                },
            },
            'por_que': (
                'Você diagnosticou o problema de negócio, mas o commit misturou três correções em 8 arquivos '
                'C#/JS/Razor sem teste automatizado para blindar regressões.'
            ),
            'pergunta_do_lider': (
                'Se a regra de cálculo de status mudar amanhã, você precisará alterar apenas o back-end C# '
                'ou também o JavaScript da tela do bate-mapa?'
            ),
        },
        {
            'tarefa': 'feat: adiciona Jev como alternativa para classificação de anexos (12 arquivos, +384/-15)',
            'skills': ['Back-end C# / .NET e Integrações', 'Domain-Driven Design (DDD)'],
            'propriedade': 'baixa',
            'indice_propriedade': 35,
            'risco_debito_tecnico': 'Alto (+384 linhas em 12 arquivos seguidas de 3 commits corretivos no mesmo dia)',
            'parametros': {
                'p1_rastro_prompt': {
                    'nome': 'P1 · Direção no Prompt vs. Delegação',
                    'nota': 45,
                    'detalhe': 'Histórico mostra geração de plano e implementação extensa em bloco pelo agente.',
                },
                'p2_granularidade_commit': {
                    'nome': 'P2 · Granularidade e Coesão do Commit',
                    'nota': 25,
                    'detalhe': 'Despejo grande (+384/-15 em 12 arquivos) que exigiu 3 fixes seguidos (respostas inválidas, revisão e enums).',
                },
                'p3_conexao_estudo': {
                    'nome': 'P3 · Conexão com Estudo / Vault Autoral',
                    'nota': 40,
                    'detalhe': 'Oportunidade direta do Cap. 1 de DDD (fronteira com serviço externo) ainda não registrada no vault.',
                },
                'p4_defesa_tecnica': {
                    'nome': 'P4 · Defesa de Decisão e Trade-offs',
                    'nota': 30,
                    'detalhe': 'Pendente responder à Pergunta da LuzIA para comprovar domínio sobre o contrato e tratamento de erros.',
                },
            },
            'por_que': (
                'O volume de código gerado de uma só vez (+384 linhas) seguido de correções imediatas para tratar '
                'respostas inválidas sinaliza que o agente codou antes de todas as invariantes estarem sob seu domínio.'
            ),
            'pergunta_do_lider': (
                'Como você estruturou o contrato entre o domínio principal e a API da Jev, e o que acontece se '
                'a Jev devolver um payload inválido ou ficar indisponível?'
            ),
        },
        {
            'tarefa': 'feat(pedido-simplificado): envia e-mail para clínica de agulhamento (+476/-16)',
            'skills': ['Back-end C# / .NET e Integrações', 'Arquitetura .NET / Clean Architecture'],
            'propriedade': 'baixa',
            'indice_propriedade': 38,
            'risco_debito_tecnico': 'Alto (acoplamento de template HTML e envio de e-mail em múltiplos projetos)',
            'parametros': {
                'p1_rastro_prompt': {
                    'nome': 'P1 · Direção no Prompt vs. Delegação',
                    'nota': 50,
                    'detalhe': 'Delegação da criação de rotina completa e templates HTML ao agente.',
                },
                'p2_granularidade_commit': {
                    'nome': 'P2 · Granularidade e Coesão do Commit',
                    'nota': 30,
                    'detalhe': '+476 linhas seguidas de commits extras para incluir template na API/Web e corrigir logo cortada.',
                },
                'p3_conexao_estudo': {
                    'nome': 'P3 · Conexão com Estudo / Vault Autoral',
                    'nota': 42,
                    'detalhe': 'Caso clássico de separação entre subdomínio de suporte e infraestrutura de notificação.',
                },
                'p4_defesa_tecnica': {
                    'nome': 'P4 · Defesa de Decisão e Trade-offs',
                    'nota': 30,
                    'detalhe': 'Pendente explicar por que o template precisou ser adicionado em projetos separados.',
                },
            },
            'por_que': (
                'A funcionalidade foi entregue rápido com IA, mas os commits seguintes corrigindo inclusão de '
                'template em diferentes .csproj mostram acoplamento estrutural.'
            ),
            'pergunta_do_lider': (
                'Por que o template HTML de agulhamento precisou ser incluído tanto no projeto Web quanto no '
                'projeto da API, e como você desacoplaria esse envio?'
            ),
        },
    ]

    plan['plano'] = [
        {
            'horizonte': '90 dias',
            'titulo': 'Fundação Conceitual aplicada ao Legado: Domínios, Subdomínios e Fim dos Commits Monolíticos',
            'acao': (
                'Conectar a leitura de Aprenda DDD (Vlad Khononov) diretamente aos módulos em que você atua '
                '(Agendamentos, Bate-Mapa, Integrações Jev/Tasy) e assumir o controle arquitetural antes de o agente gerar código.'
            ),
            'passos_detalhados': [
                '1. Mapear no Obsidian 3 fluxos reais do seu trabalho (Filtro de Aviso Alfanumérico, Bate-Mapa e Classificação Jev) classificando cada parte em Subdomínio Principal, de Suporte ou Genérico.',
                '2. Antes de pedir código ao Claude Code/Codex em tarefas > 50 linhas, exigir que o agente gere apenas as assinaturas de interfaces/DTOs e validar você mesma onde ficará cada regra.',
                '3. Fracionar entregas assistidas por IA em commits pequenos e explicáveis: (a) domínio/contratos, (b) infraestrutura/integração, (c) view Razor/JS, (d) testes.',
                '4. Responder às perguntas técnicas do LuzIA nas entregas com propriedade baixa ou média até elevar seu Índice de Propriedade médio acima de 70%.',
            ],
            'intervencao_LuzIA_no_harness': (
                'Sempre que você iniciar uma tarefa que toque em múltiplos projetos (.Domain, .App, .Api), o LuzIA '
                'intervém na sessão perguntando qual parte da mudança é regra de negócio e qual parte é detalhe de infraestrutura.'
            ),
            'uso_educado_da_ia': (
                'Fluxo em 2 etapas no agente: 1º pedir análise de impacto e 2 alternativas de design; 2º escolher a '
                'alternativa, justificar em uma frase e só então autorizar a geração de código.'
            ),
            'sinal_de_progresso': (
                'Redução visível de commits corretivos pós-entrega, mapa de subdomínios do sistema registrado no Obsidian '
                'e Índice de Propriedade Intelectual >= 70% nas tarefas do trimestre.'
            ),
        },
        {
            'horizonte': '6 meses',
            'titulo': 'Modelagem Tática de DDD, Desacoplamento de Integrações e Testes de Caracterização',
            'acao': (
                'Atuar com repertório de Pleno na evolução de integrações críticas (Tasy, MV, Jev, Brevo), isolando '
                'serviços externos com Anti-Corruption Layer (ACL) e protegendo regras de negócio com testes XUnit.'
            ),
            'passos_detalhados': [
                '1. Encapsular pelo menos uma integração externa atrás de uma camada anticorrupção (ACL), garantindo que mudanças na API terceira não quebrem o domínio.',
                '2. Escrever testes automatizados com XUnit para toda regra de negócio nova ou refatorada (ex.: cálculo de atraso no bate-mapa, validação de guias e normalização hospitalar) antes de abrir o PR.',
                '3. Registrar no vault compartilhado pequenas decisões arquiteturais (problema -> opções sugeridas pela IA -> decisão tomada e débito técnico evitado).',
                '4. Usar o agente como revisor adversarial antes do PR para caçar acoplamento, queries SQL sem índice e vazamento de responsabilidade entre Controller e View.',
            ],
            'intervencao_LuzIA_no_harness': (
                'Quando detectar alterações em serviços de negócio ou consultas SQL sem cobertura de teste no mesmo branch, '
                'o LuzIA aponta na sessão quais cenários de borda precisam ser exercitados em XUnit.'
            ),
            'uso_educado_da_ia': (
                'Você define os cenários de negócio e invariantes que não podem quebrar; o agente gera o esqueleto dos '
                'testes XUnit e mocks, e você audita cada asserção.'
            ),
            'sinal_de_progresso': (
                'Pull requests complexos aprovados sem retrabalho arquitetural, suíte de testes unitários cobrindo as '
                'regras que você mantém e domínio prático de Entities, Value Objects e ACL.'
            ),
        },
        {
            'horizonte': '12 meses',
            'titulo': 'Consolidação como Desenvolvedora Plena: Autonomia Arquitetural e Liderança com Agentes',
            'acao': (
                'Conduzir demandas complexas ponta a ponta — do refinamento técnico à entrega em produção — unindo '
                'arquitetura .NET/DDD sólida, baixo débito técnico e alta alavancagem com programação agêntica.'
            ),
            'passos_detalhados': [
                '1. Liderar o desenho técnico de uma funcionalidade ou refatoração estrutural completa, defendendo os trade-offs em reuniões técnicas e code reviews.',
                '2. Criar e evoluir skills, hooks e guardrails de agentes para o próprio fluxo do time (como validação pré-PR, leitura segura de banco e padrões de especificação).',
                '3. Atacar proativamente pontos de débito técnico em módulos legados ASP.NET MVC 5 / SQL, entregando ganhos medidos de manutenção e confiabilidade.',
                '4. Consolidar seu dossiê de evolução técnica no LuzIA (skills em 4/5 e histórico de propriedade alta) para embasar a promoção formal de Júnior 3 para Plena.',
            ],
            'intervencao_LuzIA_no_harness': (
                'Modo par sênior (Design Review): o LuzIA reduz alertas básicos e passa a desafiar suas escolhas '
                'sob a ótica de escalabilidade, resiliência em produção e manutenibilidade de longo prazo.'
            ),
            'uso_educado_da_ia': (
                'Orquestração madura de múltiplos agentes (Claude Code, Codex, Antigravity) sob sua direção intelectual, '
                'com 100% de propriedade sobre cada linha que sobe para produção.'
            ),
            'sinal_de_progresso': (
                'Atuação reconhecida como referência técnica no time, níveis 4/5 atingidos no mapa de skills (DDD, '
                'Arquitetura .NET, Back-end, Front-end e Testes) e transição consolidada para Desenvolvedora Plena.'
            ),
        },
    ]

    ST_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print('career_state.json atualizado com sucesso!')


if __name__ == '__main__':
    enrich()

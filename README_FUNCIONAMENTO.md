# Sistema de Controle de Fábrica - Funcionamento Completo

## 📋 Visão Geral

Sistema automatizado de classificação e separação de caixas para Factory I/O. O sistema integra múltiplos subsistemas que trabalham em conjunto:

1. **Sistema de Medição de Altura** - Detecta o tamanho das caixas usando sensores de feixe
2. **Sistema de Transferência** - Move caixas entre esteiras paralelas
3. **Sistema Turntable** - Classifica e separa caixas por tamanho usando plataforma giratória
4. **Controle de Esteiras** - Gerencia o fluxo de produção
5. **Interface de Controle** - Botões START/STOP/ESTOP e Stack Light

## 🎮 Controle do Sistema

### Botões de Controle

- **START (Verde)** 🟢
  - Inicia o sistema de produção
  - Liga todas as esteiras, emissores e loads
  - Stack Light fica verde
  - Sistema entra em modo operacional

- **STOP (Vermelho)** 🔴
  - Para todo o sistema imediatamente
  - Desliga todos os atuadores
  - Limpa a fila de caixas
  - Stack Light apaga

- **ESTOP (Emergência)** 🚨
  - Parada de emergência
  - Trava o sistema completamente
  - Requer pressionar START novamente para liberar
  - Usado em situações de segurança

### Stack Light (Indicadores de Status)

| Cor | Estado | Significado |
|-----|--------|-------------|
| 🟢 Verde | IDLE / LOADING | Sistema pronto, aguardando ou carregando |
| 🟡 Amarelo | POSICIONADO / GIRANDO / RETORNANDO | Sistema processando |
| 🔴 Vermelho | EJETANDO | Caixa sendo ejetada |
| ⚫ Apagado | PARADO | Sistema desligado |

## 🏭 Subsistemas

### 1. Sistema de Medição de Altura

**Componentes:**
- 8 sensores de feixe (Beam 1 a Beam 8) empilhados verticalmente
- 2 emissores de feixe (Emitter 1 e Emitter 2)

**Funcionamento:**
1. Caixas passam pelos feixes
2. Sistema conta quantos feixes são bloqueados
3. Número de feixes bloqueados = tamanho da caixa
4. Tamanho é adicionado à fila de processamento

**Exemplo:**
- Caixa pequena (altura 1) → bloqueia 1 feixe
- Caixa média (altura 3) → bloqueia 3 feixes
- Caixa grande (altura 5) → bloqueia 5 feixes

### 2. Sistema de Transferência (Transfer 2→1)

**Componentes:**
- Chain Transfer 1 (Transfer left/right 1)
- Chain Transfer 2 (Transfer left/right 2)
- Sensores: At entry 1, At transfer 1, At transfer 2, At exit

**Funcionamento:**
1. Sistema monitora continuamente:
   - Caixa no transfer 2 (`at_transfer_2 = 1`)
   - Saída livre (`at_exit = 0`)
   - Entry 1 livre (`at_entry_1 = 0`)

2. Quando condições são atendidas:
   - Para esteiras 1 e 2
   - Para emissores
   - Ativa Transfer left 1 e 2
   - Caixa é empurrada da esteira 2 para esteira 1

3. Aguarda caixa chegar em transfer 1 (`at_transfer_1 = 1`)

4. Finaliza:
   - Desativa transfers
   - Aguarda 0.3s
   - Religa esteiras e emissores

**Propósito:** Convergir duas linhas de produção em uma única linha antes do turntable.

### 3. Sistema Turntable (Classificação Principal)

O turntable é o coração do sistema. Ele classifica caixas por tamanho e as direciona para diferentes destinos.

#### 3.1. Estados da Máquina

```
[INÍCIO] → IDLE → LOADING → POSICIONADO → GIRANDO → EJETANDO → RETORNANDO → IDLE
```

##### **Estado 1: IDLE** 🟢 Verde
- **Descrição:** Sistema pronto, aguardando próxima caixa
- **Stack Light:** Verde
- **Esteiras:** LIGADAS
- **Emissores:** LIGADOS
- **Turntable:** Parado na posição 0°
- **Condição de Saída:** Sensor Diffuse 10 detecta caixa (valor = 1)

##### **Estado 2: LOADING** 🟢 Verde
- **Descrição:** Puxando caixa para o turntable
- **Stack Light:** Verde
- **Roll+:** LIGADO (puxa a caixa)
- **Esteiras:** LIGADAS inicialmente
- **Comportamento Especial:**
  - Quando **Back sensor = 1** (caixa subiu no turntable):
    - PARA todas as esteiras (Conveyor 1, 2, Roller 6M 1)
    - PARA Load 1
    - Impede novas caixas de entrar
  - Roll+ CONTINUA ligado até Front Limit
- **Condição de Saída:** Front Limit sensor = 1 (caixa posicionada)

##### **Estado 3: POSICIONADO** 🟡 Amarelo
- **Descrição:** Caixa posicionada, definindo direção
- **Stack Light:** Amarelo
- **Esteiras:** DESLIGADAS (desde LOADING)
- **Roll+:** DESLIGADO
- **Lógica de Decisão:**
  ```
  SE tamanho == 1:
      direção = DIREITA (Roll+, sensor Diffuse 12)
  SENÃO:
      direção = ESQUERDA (Roll-, sensor Diffuse 11)
  ```
- **Ação:** Liga TURN (motor de rotação)
- **Condição de Saída:** Imediata (passa para GIRANDO)

##### **Estado 4: GIRANDO** 🟡 Amarelo
- **Descrição:** Rotacionando turntable 90°
- **Stack Light:** Amarelo
- **TURN:** LIGADO (girando)
- **Roll:** PARADO
- **Esteiras:** DESLIGADAS (mantém)
- **Rotação:**
  - De 0° para 90°
  - Direciona caixa para esteira lateral escolhida
- **Condição de Saída:** Limit 90° sensor = 1 (rotação completa)

##### **Estado 5: EJETANDO** 🔴 Vermelho
- **Descrição:** Empurrando caixa para esteira de destino
- **Stack Light:** Vermelho
- **TURN:** MANTIDO LIGADO (segura posição 90°!)
- **Roll:** Dependendo da direção:
  - DIREITA → Roll+ ligado
  - ESQUERDA → Roll- ligado
- **Esteiras:** DESLIGADAS (mantém)
- **Monitoramento:** Relê sensores a CADA ciclo:
  - Front Limit
  - Back Limit
  - Sensor de saída (Diffuse 11 ou 12)
- **Condição de Saída (CRÍTICA):**
  ```
  Front Limit = 0 AND
  Back Limit = 0 AND
  Sensor_saída = 0
  ```
  (Todos os 3 sensores devem estar desativados)
- **Por que 3 sensores?** Garante que caixa saiu COMPLETAMENTE do turntable

##### **Estado 6: RETORNANDO** 🟡 Amarelo
- **Descrição:** Voltando à posição inicial 0°
- **Stack Light:** Amarelo
- **TURN:** DESLIGADO
- **Roll:** PARADO
- **Esteiras:** DESLIGADAS (ainda)
- **Mecanismo:** Retorna por mola/gravidade (sem motor)
- **Condição de Saída:** Limit 0° sensor = 1 (posição inicial)
- **Ação Final:**
  - RELIGA todas as esteiras
  - RELIGA Load 1
  - Sistema pronto para próxima caixa
  - Volta ao IDLE

#### 3.2. Sensores do Turntable

| Sensor | Endereço | Função |
|--------|----------|--------|
| Diffuse 10 | Input 12 | Detecta caixa chegando |
| Turntable Front | Input 29 | Caixa posicionada na frente |
| Turntable Back | Input 28 | Caixa subiu no turntable |
| Limit 0° | Input 26 | Posição inicial |
| Limit 90° | Input 27 | Posição de ejeção (90°) |
| Diffuse 11 | Input 13 | Caixa saindo ESQUERDA |
| Diffuse 12 | Input 14 | Caixa saindo DIREITA |

#### 3.3. Atuadores do Turntable

| Atuador | Endereço | Função |
|---------|----------|--------|
| TURN | Coil 26 | Rotaciona turntable |
| Roll + | Coil 27 | Puxa/empurra DIREITA |
| Roll - | Coil 28 | Puxa/empurra ESQUERDA |

### 4. Controle de Esteiras

O sistema possui controle inteligente de esteiras para evitar colisões e garantir fluxo suave:

**Esteiras Controladas:**
- Conveyor 1 (Coil 0)
- Conveyor 2 (Coil 7)
- Roller 6M 1 (Coil 47)
- Load 1 (Coil 11)
- Load 2 (Coil 2)

**Lógica de Controle:**

1. **Estado IDLE:**
   - ✅ Todas ligadas
   - Sistema flui normalmente

2. **Estado LOADING (Back sensor = 0):**
   - ✅ Todas ligadas
   - Caixa ainda está chegando

3. **Estado LOADING (Back sensor = 1):**
   - ❌ Todas desligadas
   - Caixa subiu no turntable
   - Impede próxima caixa de entrar

4. **Estados POSICIONADO, GIRANDO, EJETANDO:**
   - ❌ Todas desligadas
   - Turntable está processando

5. **Estado RETORNANDO (Limit 0° = 1):**
   - ✅ Todas religadas
   - Turntable pronto, libera fluxo

**Por que esse controle?**
- Evita múltiplas caixas no turntable
- Garante sincronização perfeita
- Previne colisões e travamentos

## 🔄 Fluxo Completo de Operação

### Exemplo: Caixa Tamanho 3 (vai para ESQUERDA)

```
1. [INÍCIO] Sistema START pressionado
   → Esteiras ligam
   → Emissores ligam
   → Stack Light verde

2. [MEDIÇÃO] Caixa passa pelos beams
   → 3 beams bloqueados
   → Tamanho 3 adicionado à fila: [3]

3. [TRANSFERÊNCIA] (se necessário)
   → Caixa pode ser transferida de esteira 2 para 1
   → Esteiras param temporariamente
   → Transfer acionado
   → Esteiras religam

4. [TURNTABLE - IDLE] Stack Light verde
   → Diffuse 10 detecta caixa
   → Vai para LOADING

5. [TURNTABLE - LOADING] Stack Light verde
   → Roll+ ligado, puxa caixa
   → Back sensor ativa → PARA ESTEIRAS
   → Front limit ativa → Roll+ desliga
   → Vai para POSICIONADO

6. [TURNTABLE - POSICIONADO] Stack Light amarelo
   → Remove tamanho 3 da fila
   → Decide: tamanho 3 → ESQUERDA (Roll-)
   → Liga TURN
   → Vai para GIRANDO

7. [TURNTABLE - GIRANDO] Stack Light amarelo
   → TURN girando de 0° para 90°
   → Limit 90° ativa
   → Vai para EJETANDO

8. [TURNTABLE - EJETANDO] Stack Light vermelho
   → TURN mantido ligado (segura 90°)
   → Roll- ligado (empurra para esquerda)
   → Monitora: Front=0, Back=0, Diffuse_11=0
   → Todos OFF → caixa saiu
   → Desliga TURN e Roll-
   → Vai para RETORNANDO

9. [TURNTABLE - RETORNANDO] Stack Light amarelo
   → TURN desligado
   → Retorna por gravidade
   → Limit 0° ativa
   → RELIGA ESTEIRAS
   → Vai para IDLE

10. [FIM DO CICLO]
    → Sistema pronto para próxima caixa
    → Stack Light verde
```

## 📊 Diagrama de Fluxo

```
        ┌─────────────┐
        │   START     │
        └──────┬──────┘
               │
        ┌──────▼──────┐
        │   MEDIÇÃO   │ (8 beams)
        │   DE ALTURA │
        └──────┬──────┘
               │
        ┌──────▼──────────┐
        │ TRANSFERÊNCIA   │ (2→1)
        │ (se necessário) │
        └──────┬──────────┘
               │
        ┌──────▼──────┐
        │    IDLE     │ 🟢
        └──────┬──────┘
               │ Diffuse 10 ON
        ┌──────▼──────┐
        │   LOADING   │ 🟢
        │  Back → Para│
        │   esteiras  │
        └──────┬──────┘
               │ Front Limit ON
        ┌──────▼──────────┐
        │  POSICIONADO    │ 🟡
        │ Define direção  │
        │ (1→DIR, >1→ESQ) │
        └──────┬──────────┘
               │
        ┌──────▼──────┐
        │   GIRANDO   │ 🟡
        │   0° → 90°  │
        └──────┬──────┘
               │ Limit 90° ON
        ┌──────▼──────────┐
        │   EJETANDO      │ 🔴
        │ Roll+ ou Roll-  │
        │ TURN mantido ON │
        └──────┬──────────┘
               │ 3 sensores OFF
        ┌──────▼──────────┐
        │  RETORNANDO     │ 🟡
        │ 90° → 0°        │
        │ (por gravidade) │
        └──────┬──────────┘
               │ Limit 0° ON
               │ RELIGA ESTEIRAS
               │
        ┌──────▼──────┐
        │    IDLE     │ 🟢
        └─────────────┘
```

## ⚙️ Configurações e Parâmetros

### Timeouts
- **SCAN_INTERVAL:** 0.15s (ciclo de varredura)
- **Timeout align:** 10.0s (tempo máximo para alinhamento/rotação)
- **Timeout eject:** 10.0s (tempo máximo para ejeção)
- **Transfer delay:** 0.5s (ativação dos transfers)
- **Transfer resume:** 0.3s (pausa antes de religar)

### Comunicação Modbus TCP
- **Host:** 127.0.0.1 (localhost)
- **Porta:** 502
- **Unit ID:** 1

## 🎯 Lógica de Classificação

| Tamanho da Caixa | Destino | Roll | Sensor de Saída |
|------------------|---------|------|-----------------|
| 1 | DIREITA | Roll+ | Diffuse 12 |
| 2, 3, 4, 5, 6, 7, 8 | ESQUERDA | Roll- | Diffuse 11 |

## 🔒 Segurança e Sincronização

### Pontos Críticos de Segurança

1. **Back Sensor é Gatilho de Parada**
   - Não usa Diffuse 10
   - Garante que caixa realmente subiu

2. **Esteiras Desligadas Durante Processamento**
   - Desde Back sensor até Limit 0°
   - Evita entrada de novas caixas

3. **Condição Tripla de Ejeção**
   - Front=0 AND Back=0 AND Sensor_saída=0
   - Garante saída completa da caixa

4. **TURN Mantido no EJETANDO**
   - Segura posição 90°
   - Evita desalinhamento durante ejeção

5. **Releitura de Sensores**
   - Sensores relidos a cada ciclo no EJETANDO
   - Valores sempre atualizados

### Prevenção de Problemas

| Problema | Solução Implementada |
|----------|---------------------|
| Múltiplas caixas no turntable | Esteiras param quando Back sensor ativa |
| Caixa mal ejetada | Condição tripla de sensores |
| Desalinhamento durante ejeção | TURN mantido ligado no EJETANDO |
| Valores desatualizados | Releitura de sensores no EJETANDO |
| Colisão de caixas | Esteiras só religam quando turntable volta ao IDLE |

## 📝 Notas Importantes

1. **Ordem dos Estados é Fixa**
   - Não pule estados
   - Cada estado valida pré-condições

2. **Fila de Caixas (FIFO)**
   - Primeira caixa medida = primeira processada
   - Mantém ordem de produção

3. **Stack Light é Indicador Visual**
   - Verde: Sistema operando normalmente
   - Amarelo: Sistema processando
   - Vermelho: Caixa sendo ejetada
   - Apagado: Sistema parado

4. **Emissores Sempre Ligados Quando Sistema Ativo**
   - Necessário para medição contínua
   - Param apenas em STOP/ESTOP

5. **Sistema Tolerante a Falhas**
   - ESTOP para tudo imediatamente
   - START sempre reinicia do zero
   - Fila é limpa em STOP/ESTOP

## 🔧 Manutenção e Troubleshooting

### Problemas Comuns

**Caixa não entra no turntable:**
- Verificar se esteiras estão ligadas no IDLE
- Verificar Diffuse 10
- Verificar Roll+

**Turntable não gira:**
- Verificar TURN (Coil 26)
- Verificar Limit 90° sensor

**Caixa não ejeta:**
- Verificar Roll+ ou Roll- dependendo da direção
- Verificar se TURN está mantido ligado
- Verificar sensores de saída (Diffuse 11/12)

**Esteiras não religam:**
- Verificar se turntable voltou ao IDLE
- Verificar Limit 0° sensor

**Stack Light não muda:**
- Verificar Coils 17, 18, 19 (Red, Green, Yellow)

## 📚 Referências

- **Arquivo de Controle:** `controlador_fabrica_v_17.py`
- **Diagrama de Estados:** `DIAGRAMA_ESTADOS_CENA_SEPARADOR.md`
- **Documentação do Código:** `README_CODIGO.md`
- **Factory I/O:** Software de simulação
- **Protocolo:** Modbus TCP/IP

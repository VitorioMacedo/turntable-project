# Sistema de Controle de Turntable - Documentação do Código

## 📁 Arquivo Principal

**controlador_fabrica_v_17.py**

## 🏗️ Arquitetura do Código

### Estrutura Geral

```
controlador_fabrica_v_17.py
├── Imports e Configurações Globais
├── Funções Auxiliares
├── Leitura e Mapeamento de Tags CSV
├── Configurações de Endereços Modbus
├── Funções Modbus (Conexão e I/O)
├── Funções de Sistema
├── Máquina de Estados do Turntable
├── Funções de Transferência
└── Loop Principal
```

## 🔧 Componentes Principais

### 1. Configurações Globais

```python
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 502
UNIT = 1
SCAN_INTERVAL = 0.15  # Intervalo de scan em segundos
```

**NÃO ALTERAR** - Configurações críticas do servidor Modbus.

### 2. Mapeamento de Endereços

#### Endereços Resolvidos Automaticamente (CSV)
```python
RESOLVED_INPUTS = resolver_nome_logico_para_addr_map(LOGICAL_INPUTS, INPUTS_RAW_MAP)
RESOLVED_COILS = resolver_nome_logico_para_addr_map(LOGICAL_COILS, COILS_RAW_MAP)
```

O sistema carrega `factory_tags.csv` e mapeia nomes lógicos para endereços físicos.

#### Endereços Fixos Críticos (Turntable)
```python
# NÃO ALTERAR - Mapeamento manual do turntable
INP_TURNTABLE_LIMIT = 26       # Limit 0°
INP_TURNTABLE_LIMIT_90 = 27    # Limit 90°
INP_TURNTABLE_BACK = 28        # Back sensor
INP_TURNTABLE_FRONT = 29       # Front sensor
COIL_TURNTABLE_TURN = 26       # Turn motor
COIL_TURNTABLE_ROLL_PLUS = 27  # Roll +
COIL_TURNTABLE_ROLL_MINUS = 28 # Roll -
```

#### Stack Light
```python
COIL_STACK_LIGHT_RED = 17      # Luz vermelha
COIL_STACK_LIGHT_GREEN = 18    # Luz verde
COIL_STACK_LIGHT_YELLOW = 19   # Luz amarela
```

### 3. Funções Auxiliares

#### `normalizar_nome(nome: str) -> str`
Remove caracteres especiais e normaliza nomes para comparação.

#### `tokens(nome: str) -> set`
Extrai tokens de um nome para matching fuzzy.

#### `resolver_nome_logico_para_addr_map(logical_names, map_dict)`
Resolve nomes lógicos para endereços físicos usando CSV com fallback.

### 4. Funções Modbus

#### `connect_modbus(host, port)`
```python
def connect_modbus(host, port):
    client = ModbusTcpClient(host, port=port)
    if not client.connect():
        raise ConnectionError(f"Falha ao conectar a {host}:{port}")
    return client
```

#### `read_input(client, address)`
Lê discrete input (sensor) do servidor Modbus.

#### `write_coil(client, address, value)`
Escreve em coil (atuador) do servidor Modbus.

### 5. Funções de Sistema

#### `desligar_tudo(client)`
Desliga TODOS os atuadores e Stack Light. Usado em:
- Inicialização
- STOP
- ESTOP
- Finalização

#### `ligar_esteiras_e_loads(client)`
Liga apenas esteiras e loads. Usado no START.

#### `ligar_emissores(client)`
Liga emissores de feixe para medição de altura.

#### `medir_altura(client)`
```python
def medir_altura(client):
    bloqueados = 0
    for addr in INPUT_BEAMS:
        if read_input(client, addr):
            bloqueados += 1
    return bloqueados
```
Conta quantos feixes estão bloqueados = altura da caixa.

#### `set_stack_light(client, red=0, green=0, yellow=0)`
Controla Stack Light de forma simples:
```python
set_stack_light(client, red=1, green=0, yellow=0)  # Vermelho
set_stack_light(client, red=0, green=1, yellow=0)  # Verde
set_stack_light(client, red=0, green=0, yellow=1)  # Amarelo
```

### 6. Máquina de Estados do Turntable

#### Estado Global
```python
TURNTABLE_STATE = {
    'estado': 'IDLE',
    'caixa_atual': None,
    'timestamp': 0,
    'contador_giro': 0
}
```

#### Função Principal: `controlar_turntable(client, fila_caixas)`

##### Estado IDLE
```python
if estado_atual == 'IDLE':
    set_stack_light(client, red=0, green=1, yellow=0)  # Verde
    
    if diffuse == 1:
        # Detectou caixa → vai para LOADING
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
        TURNTABLE_STATE['estado'] = 'LOADING'
```

**Saídas**: Stack Light verde, esteiras ligadas

##### Estado LOADING
```python
elif estado_atual == 'LOADING':
    set_stack_light(client, red=0, green=1, yellow=0)  # Verde
    
    if back_limit == 1:
        # Caixa subiu → PARA esteiras
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
    
    if front_limit == 1:
        # Caixa posicionada → vai para POSICIONADO
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        TURNTABLE_STATE['estado'] = 'POSICIONADO'
```

**Critério de parada de esteiras**: Back sensor (não Diffuse 10!)

##### Estado POSICIONADO
```python
elif estado_atual == 'POSICIONADO':
    set_stack_light(client, red=0, green=0, yellow=1)  # Amarelo
    
    # Decide direção baseada no tamanho
    if tamanho == 1:
        TURNTABLE_STATE['direcao'] = 'DIREITA'
    else:
        TURNTABLE_STATE['direcao'] = 'ESQUERDA'
    
    # Liga TURN para girar
    write_coil(client, COIL_TURNTABLE_TURN, 1)
    TURNTABLE_STATE['estado'] = 'GIRANDO'
```

**Decisão crítica**: Define para onde a caixa vai

##### Estado GIRANDO
```python
elif estado_atual == 'GIRANDO':
    set_stack_light(client, red=0, green=0, yellow=1)  # Amarelo
    
    # Mantém esteiras desligadas
    write_coil(client, COIL_ROLLER_6M_1, 0)
    write_coil(client, COIL_CONVEYOR_1, 0)
    write_coil(client, COIL_CONVEYOR_2, 0)
    write_coil(client, COIL_LOAD_1, 0)
    
    if limit_90 == 1:
        # Completou giro → vai para EJETANDO
        TURNTABLE_STATE['estado'] = 'EJETANDO'
```

**Importante**: TURN fica ligado até completar 90°

##### Estado EJETANDO
```python
elif estado_atual == 'EJETANDO':
    set_stack_light(client, red=1, green=0, yellow=0)  # Vermelho
    
    # RE-LÊ sensores a cada ciclo (CRÍTICO!)
    front_limit = read_input(client, INP_TURNTABLE_FRONT)
    back_limit = read_input(client, INP_TURNTABLE_BACK)
    diffuse_11 = read_input(client, INP_DIFFUSE_11)
    diffuse_12 = read_input(client, INP_DIFFUSE_12)
    
    if direcao == 'DIREITA':
        sensor_saida = diffuse_12
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
    else:
        sensor_saida = diffuse_11
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 1)
    
    # MANTÉM TURN ligado para segurar posição!
    write_coil(client, COIL_TURNTABLE_TURN, 1)
    
    # Condição de parada: TODOS os 3 sensores OFF
    if front_limit == 0 and back_limit == 0 and sensor_saida == 0:
        write_coil(client, COIL_TURNTABLE_TURN, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        TURNTABLE_STATE['estado'] = 'RETORNANDO'
```

**Pontos críticos**:
1. Sensores relidos a cada ciclo (valores atualizados)
2. TURN mantém-se ligado durante toda ejeção
3. Condição AND de 3 sensores para parar

##### Estado RETORNANDO
```python
elif estado_atual == 'RETORNANDO':
    set_stack_light(client, red=0, green=0, yellow=1)  # Amarelo
    
    # TURN desligado - retorna por mola
    write_coil(client, COIL_TURNTABLE_TURN, 0)
    
    if limit_0 == 1:
        # Voltou à posição inicial → RELIGA esteiras
        write_coil(client, COIL_ROLLER_6M_1, 1)
        write_coil(client, COIL_CONVEYOR_1, 1)
        write_coil(client, COIL_CONVEYOR_2, 1)
        write_coil(client, COIL_LOAD_1, 1)
        
        TURNTABLE_STATE['estado'] = 'IDLE'
```

**Importante**: Esteiras só religam aqui!

### 7. Loop Principal

```python
def main():
    # Conecta Modbus
    client = connect_modbus(args.host, args.port)
    desligar_tudo(client)
    
    # Estados do sistema
    sistema_ativo = False
    estop_ativo = False
    fila_caixas = []
    
    while True:
        # Lê botões START/STOP/ESTOP
        start = read_input(client, INP_START)
        stop = read_input(client, INP_STOP)
        estop = read_input(client, INP_ESTOP)
        
        # Detecção de borda de subida (botão pressionado)
        if start == 1 and start_anterior == 0:
            sistema_ativo = True
            ligar_esteiras_e_loads(client)
            ligar_emissores(client)
        
        if stop == 1 and stop_anterior == 0:
            sistema_ativo = False
            desligar_tudo(client)
        
        if estop == 1 and estop_anterior == 0:
            estop_ativo = True
            sistema_ativo = False
            desligar_tudo(client)
        
        # Lógica operacional (só se sistema ativo)
        if sistema_ativo and not estop_ativo:
            # Medição de altura
            altura = medir_altura(client)
            if altura > 0:
                fila_caixas.append(altura)
            
            # Transferências
            transferencia_2_para_1(client, sensores, ...)
            
            # Controle do turntable
            controlar_turntable(client, fila_caixas)
        
        time.sleep(SCAN_INTERVAL)
```

## 🔍 Pontos de Atenção para Modificações

### ✅ Pode Modificar Livremente
- Tempos de delay e timeouts
- Mensagens de debug/log
- Lógica de decisão de direção (linha que decide DIREITA/ESQUERDA)
- Cores do Stack Light para cada estado

### ⚠️ Modificar com Cuidado
- `SCAN_INTERVAL`: Afeta responsividade
- Ordem dos estados na máquina de estados
- Condições de transição entre estados

### 🚫 NÃO MODIFICAR
```python
# BEGIN: DO NOT MODIFY
from pymodbus.client.sync import ModbusTcpClient
# END: DO NOT MODIFY
```

- Endereços do turntable (linhas 154-162)
- Endereços do Stack Light (linhas 165-169)
- Lógica de releitura de sensores no EJETANDO
- Condição `front_limit == 0 and back_limit == 0 and sensor_saida == 0`

## 🐛 Debug

### Variáveis de Debug Úteis
```python
print(f"[DEBUG] Estado atual: {TURNTABLE_STATE['estado']}")
print(f"[DEBUG] Front={front_limit} Back={back_limit}")
print(f"[DEBUG] Fila de caixas: {fila_caixas}")
```

### Logs Disponíveis
- `[TURNTABLE]`: Operações do turntable
- `[SISTEMA]`: Sistema geral
- `[TRANSFER]`: Transferências
- `[ALTURA]`: Medição de caixas
- `[DEBUG]`: Informações de debug

## 📊 Fluxo de Dados

```
CSV File → INPUTS_RAW_MAP / COILS_RAW_MAP
    ↓
resolver_nome_logico_para_addr_map()
    ↓
RESOLVED_INPUTS / RESOLVED_COILS
    ↓
Constantes globais (INP_*, COIL_*)
    ↓
Funções read_input() / write_coil()
    ↓
Máquina de Estados / Loop Principal
```

## 🔐 Segurança

1. **Sempre** use `desligar_tudo()` antes de encerrar
2. **Sempre** trate exceções em funções Modbus
3. **Sempre** valide estado antes de transição
4. **Nunca** pule estados na máquina de estados
5. **Nunca** modifique `TURNTABLE_STATE` diretamente fora da máquina de estados

## 📝 Convenções de Código

- Constantes em UPPER_CASE
- Funções em snake_case
- Comentários descritivos em cada estado
- Logs com prefixo identificador
- Endereços comentados com nome físico do componente

## 🧪 Testando Modificações

1. Teste cada estado individualmente
2. Verifique transições entre estados
3. Teste com diferentes tamanhos de caixa
4. Teste START/STOP/ESTOP em cada estado
5. Verifique Stack Light em cada transição
6. Valide que esteiras param/ligam corretamente

## 📚 Referências

- **Factory IO**: https://factoryio.com/
- **Modbus TCP**: Porta 502, Unit 1
- **pymodbus**: Biblioteca Python para Modbus

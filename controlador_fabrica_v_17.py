"""
Versão: v17-turntable-rollplus-hold-integrado
Base: controlador_fabrica_v15_turntable_manualmap_fix.py + v16
Função: Sistema completo integrado (Start/Stop/ESTOP, transferência, medição de altura) com Turntable
        aprimorado: Roll + mantido até Front Limit, Roll - bloqueado durante carregamento e mapeamento
        manual do turntable para evitar confusões do CSV.
Autor: Sebastião Lopes
Data: 2025-11-12
"""

import time
import argparse
import csv
import os
import re
# BEGIN: DO NOT MODIFY
from pymodbus.client.sync import ModbusTcpClient
# END: DO NOT MODIFY
# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar_nome(nome: str) -> str:
    if nome is None:
        return ""
    nome = nome.replace("\ufeff", "").lower()
    nome = re.sub(r"[^a-z0-9]+", "", nome)
    return nome

def tokens(nome: str):
    if not nome:
        return set()
    return set(re.findall(r"[a-z0-9]+", nome.lower()))

# ============================================================
# LEITURA DO CSV (autoleitura para elementos NÃO críticos)
# ============================================================

def carregar_mapa_factoryio(caminho_csv="factory_tags.csv"):
    inputs, coils = {}, {}
    if not os.path.exists(caminho_csv):
        print(f"[AVISO] Arquivo '{caminho_csv}' não encontrado. Usando endereços fixos.")
        return inputs, coils
    with open(caminho_csv, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tipo = (row.get("Type") or "").strip().lower()
            nome = (row.get("Name") or "").strip()
            endereco_raw = (row.get("Address") or "").strip()
            m = re.search(r"(\d+)", endereco_raw)
            if not m:
                continue
            addr = int(m.group(1))
            chave_norm = normalizar_nome(nome)
            if "input" in tipo:
                inputs[chave_norm] = {"orig": nome, "addr": addr}
            elif "output" in tipo or "coil" in tipo:
                coils[chave_norm] = {"orig": nome, "addr": addr}
    print(f"[MAPA] Carregado: {len(inputs)} entradas e {len(coils)} coils de '{caminho_csv}'.")
    return inputs, coils

INPUTS_RAW_MAP, COILS_RAW_MAP = carregar_mapa_factoryio("factory_tags.csv")

# ============================================================
# RESOLUÇÃO LÓGICA (para elementos gerais) - mantém fallback
# ============================================================

def resolver_nome_logico_para_addr_map(logical_names, map_dict):
    resolved = {}
    available = list(map_dict.keys())
    for logical, fallback in logical_names:
        l_norm = normalizar_nome(logical)
        match = None
        if l_norm in map_dict:
            match = l_norm
        else:
            for k in available:
                if k.startswith(l_norm) or l_norm.startswith(k) or l_norm in k or k in l_norm:
                    match = k
                    break
            if not match:
                best, best_score = None, 0
                l_tokens = tokens(logical)
                for k in available:
                    k_tokens = tokens(map_dict[k]["orig"])
                    score = len(l_tokens & k_tokens)
                    if score > best_score:
                        best, best_score = k, score
                if best_score > 0:
                    match = best
        if match:
            resolved[logical] = map_dict[match]["addr"]
        else:
            resolved[logical] = fallback
            print(f"[AVISO] (resolver) '{logical}' não encontrado no mapa CSV. Usando fallback {fallback}.")
    return resolved

# ============================================================
# NOMES LÓGICOS (apenas para elementos não críticos - turntable será manual)
# ============================================================
LOGICAL_INPUTS = [
    ("At entry 1", 0), ("At entry 2", 1), ("At transfer 1", 2), ("At transfer 2", 3), ("At exit", 4),
    ("Start", 5), ("Reset", 6), ("Stop", 7), ("Diffuse 10", 12),
] + [(f"Beam {i}", 17 + i) for i in range(8)]

LOGICAL_COILS = [
    ("Conveyor 1", 0), ("Load 1", 1), ("Transfer Left 1", 4),
    ("Conveyor 2", 5), ("Load 2", 6), ("Transfer Left 2", 9),
    ("Roller 4m 0", 10), ("Roller 4m 3", 11),
    ("Emitter 1", 14), ("Emitter 2", 15), ("Roller 6m 1", 16),
]

RESOLVED_INPUTS = resolver_nome_logico_para_addr_map(LOGICAL_INPUTS, INPUTS_RAW_MAP)
RESOLVED_COILS = resolver_nome_logico_para_addr_map(LOGICAL_COILS, COILS_RAW_MAP)

# ============================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 502
UNIT = 1
DEFAULT_EJECTION_DELAY = 0.5
DEFAULT_RESUME_DELAY = 0.3
SCAN_INTERVAL = 0.15

# ============================================================
# MAPEAMENTO RESOLVIDO (geral)
# ============================================================
INP_AT_ENTRY_1 = RESOLVED_INPUTS["At entry 1"]
INP_AT_TRANSFER_1 = RESOLVED_INPUTS["At transfer 1"]
INP_AT_TRANSFER_2 = RESOLVED_INPUTS["At transfer 2"]
INP_AT_EXIT = RESOLVED_INPUTS["At exit"]
INP_START = RESOLVED_INPUTS["Start"]
INP_ESTOP = RESOLVED_INPUTS["Reset"]
INP_STOP = RESOLVED_INPUTS["Stop"]
INP_DIFFUSE_10 = RESOLVED_INPUTS["Diffuse 10"]
INP_DIFFUSE_11 = 13  # Diffuse Sensor 11 (saída esquerda)
INP_DIFFUSE_12 = 14  # Diffuse Sensor 12 (saída direita)
INPUT_BEAMS = [RESOLVED_INPUTS[f"Beam {i}"] for i in range(8)]

COIL_CONVEYOR_1 = RESOLVED_COILS["Conveyor 1"]
COIL_LOAD_1 = RESOLVED_COILS["Load 1"]
COIL_TRANSFER_LEFT_1 = RESOLVED_COILS["Transfer Left 1"]
COIL_CONVEYOR_2 = RESOLVED_COILS["Conveyor 2"]
COIL_LOAD_2 = RESOLVED_COILS["Load 2"]
COIL_TRANSFER_LEFT_2 = RESOLVED_COILS["Transfer Left 2"]
COIL_ROLLER_4M_0 = RESOLVED_COILS["Roller 4m 0"]
COIL_ROLLER_4M_3 = RESOLVED_COILS["Roller 4m 3"]
COIL_EMITTER_1 = RESOLVED_COILS["Emitter 1"]
COIL_EMITTER_2 = RESOLVED_COILS["Emitter 2"]
COIL_ROLLER_6M_1 = RESOLVED_COILS["Roller 6m 1"]

# ============================================================
# MAPEAMENTO MANUAL DO TURNTABLE (ENDEREÇOS CORRETOS DA CENA)
# ============================================================
INP_TURNTABLE_LIMIT = 26       # Turntable 0 (Limit 0) - posição neutra
INP_TURNTABLE_LIMIT_90 = 27    # Turntable 0 (Limit 90)
INP_TURNTABLE_BACK = 28        # Turntable Back
INP_TURNTABLE_FRONT = 29       # Turntable 0 (Front Limit)
COIL_TURNTABLE_TURN = 26       # Turntable 0 Turn
COIL_TURNTABLE_ROLL_PLUS = 27  # Turntable 0 Roll (+)
COIL_TURNTABLE_ROLL_MINUS = 28 # Turntable 0 Roll (-)

# ============================================================
# STACK LIGHT (ENDEREÇOS CORRETOS DA CENA)
# ============================================================
COIL_STACK_LIGHT_RED = 17      # Stack Light 2 (Red)
COIL_STACK_LIGHT_GREEN = 18    # Stack Light 2 (Green)
COIL_STACK_LIGHT_YELLOW = 19   # Stack Light 2 (Yellow)

# DEBUG print dos endereços críticos
print("[MAPA-DEBUG] INP_DIFFUSE_10 =", INP_DIFFUSE_10)
print("[MAPA-DEBUG] INP_TURNTABLE_LIMIT =", INP_TURNTABLE_LIMIT)
print("[MAPA-DEBUG] INP_TURNTABLE_LIMIT_90 =", INP_TURNTABLE_LIMIT_90)
print("[MAPA-DEBUG] INP_TURNTABLE_FRONT =", INP_TURNTABLE_FRONT)
print("[MAPA-DEBUG] INP_TURNTABLE_BACK =", INP_TURNTABLE_BACK)
print("[MAPA-DEBUG] COIL_TURNTABLE_TURN =", COIL_TURNTABLE_TURN)
print("[MAPA-DEBUG] COIL_TURNTABLE_ROLL_PLUS =", COIL_TURNTABLE_ROLL_PLUS)
print("[MAPA-DEBUG] COIL_TURNTABLE_ROLL_MINUS =", COIL_TURNTABLE_ROLL_MINUS)

# ============================================================
# FUNÇÕES MODBUS
# ============================================================

def connect_modbus(host, port):
    client = ModbusTcpClient(host, port=port)
    if not client.connect():
        raise ConnectionError(f"Falha ao conectar a {host}:{port}")
    return client

def read_input(client, address):
    try:
        rr = client.read_discrete_inputs(address=address, count=1, slave=UNIT)
        if not rr.isError():
            return int(rr.bits[0])
    except Exception:
        pass
    return 0

def write_coil(client, address, value):
    try:
        client.write_coil(address=address, value=int(bool(value)), slave=UNIT)
    except Exception:
        pass

# ============================================================
# FUNÇÕES DE SISTEMA (desligar/ligar esteiras/emissores etc.)
# ============================================================

def desligar_tudo(client):
    coils = [
        COIL_LOAD_1, COIL_LOAD_2,
        COIL_CONVEYOR_1, COIL_CONVEYOR_2,
        COIL_ROLLER_4M_0, COIL_ROLLER_4M_3, COIL_ROLLER_6M_1,
        COIL_EMITTER_1, COIL_EMITTER_2,
        COIL_TRANSFER_LEFT_1, COIL_TRANSFER_LEFT_2,
        COIL_TURNTABLE_TURN, COIL_TURNTABLE_ROLL_PLUS, COIL_TURNTABLE_ROLL_MINUS
    ]
    for c in coils:
        write_coil(client, c, 0)
    # Desliga Stack Light
    set_stack_light(client, red=0, green=0, yellow=0)
    print("[SISTEMA] Todos os atuadores desligados.")

def ligar_esteiras_e_loads(client):
    for coil in [COIL_LOAD_1, COIL_LOAD_2, COIL_CONVEYOR_1, COIL_CONVEYOR_2,
                 COIL_ROLLER_4M_0, COIL_ROLLER_4M_3, COIL_ROLLER_6M_1]:
        write_coil(client, coil, 1)
    print("[SISTEMA] Esteiras e Loads ligados.")

def ligar_emissores(client):
    write_coil(client, COIL_EMITTER_1, 1)
    write_coil(client, COIL_EMITTER_2, 1)
    print("[SISTEMA] Emissores ligados.")

def medir_altura(client):
    bloqueados = 0
    for addr in INPUT_BEAMS:
        if read_input(client, addr):
            bloqueados += 1
    return bloqueados

# ============================================================
# LÓGICA DO TURNTABLE COM MÁQUINA DE ESTADOS SIMPLES
# ============================================================

# Estados do turntable (variável global para manter estado entre chamadas)
TURNTABLE_STATE = {
    'estado': 'IDLE',  # IDLE, LOADING, POSICIONADO, GIRANDO, EJETANDO, RETORNANDO
    'caixa_atual': None,
    'timestamp': 0,
    'contador_giro': 0
}

def parar_turntable(client):
    """Para todos os movimentos do turntable"""
    write_coil(client, COIL_TURNTABLE_TURN, 0)
    write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
    write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)

def set_stack_light(client, red=0, green=0, yellow=0):
    """Controla as cores do Stack Light"""
    write_coil(client, COIL_STACK_LIGHT_RED, red)
    write_coil(client, COIL_STACK_LIGHT_GREEN, green)
    write_coil(client, COIL_STACK_LIGHT_YELLOW, yellow)

def controlar_turntable(client, fila_caixas, timeout_align=10.0, timeout_eject=10.0):
    """
    Controla o turntable com máquina de estados simples e robusta.
    Estados: IDLE → LOADING → POSICIONADO → GIRANDO → EJETANDO → RETORNANDO → IDLE
    """
    
    # Leitura de sensores
    diffuse = read_input(client, INP_DIFFUSE_10)
    front_limit = read_input(client, INP_TURNTABLE_FRONT)
    back_limit = read_input(client, INP_TURNTABLE_BACK)
    diffuse_11 = read_input(client, INP_DIFFUSE_11)  # Sensor saída ESQUERDA
    diffuse_12 = read_input(client, INP_DIFFUSE_12)  # Sensor saída DIREITA
    
    estado_atual = TURNTABLE_STATE['estado']
    
    # ========== ESTADO: IDLE (Aguardando caixa) ==========
    if estado_atual == 'IDLE':
        # Stack Light VERDE - Sistema pronto
        set_stack_light(client, red=0, green=1, yellow=0)
        
        if diffuse == 1:
            # Caixa detectada! Inicia carregamento
            print(f"[TURNTABLE] Diffuse 10 ON! Caixa detectada.")
            print(f"[TURNTABLE] Estado: IDLE → LOADING")
            print(f"[TURNTABLE] Ligando Roll+...")
            
            # Liga Roll+ para puxar caixa (esteiras continuam ligadas até Back sensor)
            write_coil(client, COIL_TURNTABLE_TURN, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
            
            TURNTABLE_STATE['estado'] = 'LOADING'
            TURNTABLE_STATE['timestamp'] = time.time()
            
            # Pega tamanho da caixa se disponível
            if fila_caixas:
                TURNTABLE_STATE['caixa_atual'] = fila_caixas.pop(0)
            else:
                TURNTABLE_STATE['caixa_atual'] = None
        else:
            # Nada a fazer, garantir tudo desligado
            parar_turntable(client)
    
    # ========== ESTADO: LOADING (Puxando caixa) ==========
    elif estado_atual == 'LOADING':
        # Stack Light VERDE - Carregando
        set_stack_light(client, red=0, green=1, yellow=0)
        
        # Verifica se caixa subiu no turntable (Back sensor acionado)
        if back_limit == 1:
            # Caixa subiu! PARA as esteiras agora
            print(f"[TURNTABLE] Back sensor ON! Caixa no turntable.")
            print(f"[TURNTABLE] PARANDO esteiras e Load 1 - Turntable ocupado!")
            write_coil(client, COIL_ROLLER_6M_1, 0)
            write_coil(client, COIL_CONVEYOR_1, 0)
            write_coil(client, COIL_CONVEYOR_2, 0)
            write_coil(client, COIL_LOAD_1, 0)
        
        # MANTÉM Roll+ ligado
        write_coil(client, COIL_TURNTABLE_TURN, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        # Verifica se caixa chegou no Front Limit
        if front_limit == 1:
            print(f"[TURNTABLE] Front Limit ON! Caixa posicionada.")
            print(f"[TURNTABLE] Desligando Roll+...")
            
            # DESLIGA Roll+ IMEDIATAMENTE
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            
            TURNTABLE_STATE['estado'] = 'POSICIONADO'
            TURNTABLE_STATE['timestamp'] = time.time()
            print(f"[TURNTABLE] Estado: LOADING → POSICIONADO")
    
    # ========== ESTADO: POSICIONADO (Pronto para girar) ==========
    elif estado_atual == 'POSICIONADO':
        # Stack Light AMARELO - Preparando para girar
        set_stack_light(client, red=0, green=0, yellow=1)
        
        # MANTÉM esteiras e Load 1 DESLIGADAS
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        # Determina direção baseada no tamanho da caixa
        tamanho = TURNTABLE_STATE['caixa_atual']
        
        if tamanho == 1:
            direcao = 'DIREITA'
            TURNTABLE_STATE['direcao'] = 'DIREITA'
            print(f"[TURNTABLE] Caixa tamanho {tamanho} → Vai para DIREITA (Roll+)")
        else:
            direcao = 'ESQUERDA'
            TURNTABLE_STATE['direcao'] = 'ESQUERDA'
            print(f"[TURNTABLE] Caixa tamanho {tamanho} → Vai para ESQUERDA (Roll-)")
        
        print(f"[TURNTABLE] Iniciando giro de 90°...")
        print(f"[TURNTABLE] Ligando TURN...")
        
        # Liga TURN para girar
        write_coil(client, COIL_TURNTABLE_TURN, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        TURNTABLE_STATE['estado'] = 'GIRANDO'
        TURNTABLE_STATE['contador_giro'] = 0
        TURNTABLE_STATE['timestamp'] = time.time()
        print(f"[TURNTABLE] Estado: POSICIONADO → GIRANDO")
    
    # ========== ESTADO: GIRANDO (Rotação de 90°) ==========
    elif estado_atual == 'GIRANDO':
        # Stack Light AMARELO - Girando
        set_stack_light(client, red=0, green=0, yellow=1)
        
        # Lê sensor de limite 90°
        limit_90 = read_input(client, INP_TURNTABLE_LIMIT_90)
        
        # MANTÉM esteiras e Load 1 DESLIGADAS durante o giro
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        # MANTÉM TURN ligado
        write_coil(client, COIL_TURNTABLE_TURN, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        print(f"[GIRANDO] Limit90={limit_90}   ", end='\r')
        
        # Verifica se completou o giro (sensor Limit 90 acionado)
        if limit_90 == 1:
            print(f"\n[TURNTABLE] Limit 90° ON! Giro completo detectado.")
            print(f"[TURNTABLE] MANTENDO TURN LIGADO para segurar posição...")
            
            # NÃO desliga TURN! Mantém ligado para segurar a posição 90°
            
            # Vai para EJETANDO
            TURNTABLE_STATE['estado'] = 'EJETANDO'
            TURNTABLE_STATE['timestamp'] = time.time()
            print(f"[TURNTABLE] Estado: GIRANDO → EJETANDO")
            print(f"[TURNTABLE] Ligando Roll+ para ejetar...")
    
    # ========== ESTADO: EJETANDO (Empurrando caixa para esteira) ==========
    elif estado_atual == 'EJETANDO':
        # Stack Light VERMELHO - Ejetando
        set_stack_light(client, red=1, green=0, yellow=0)
        
        # MANTÉM esteiras e Load 1 DESLIGADAS durante ejeção
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        # RE-LÊ todos os sensores a cada ciclo para garantir valores atualizados
        front_limit = read_input(client, INP_TURNTABLE_FRONT)
        back_limit = read_input(client, INP_TURNTABLE_BACK)
        diffuse_11 = read_input(client, INP_DIFFUSE_11)
        diffuse_12 = read_input(client, INP_DIFFUSE_12)
        
        # DEBUG CRÍTICO: Mostra se está realmente neste estado
        if 'ejetando_iniciado' not in TURNTABLE_STATE:
            direcao = TURNTABLE_STATE.get('direcao', 'DIREITA')
            print(f"\n[DEBUG] ENTROU NO EJETANDO! Direção={direcao}")
            print(f"[DEBUG] Front={front_limit} Back={back_limit} D12={diffuse_12} D11={diffuse_11}")
            TURNTABLE_STATE['ejetando_iniciado'] = True
            TURNTABLE_STATE['ciclos_ejetando'] = 0
        
        # Determina qual sensor de saída monitorar e qual Roll usar
        direcao = TURNTABLE_STATE.get('direcao', 'DIREITA')
        
        if direcao == 'DIREITA':
            # Ejeta para DIREITA com Roll+
            sensor_saida = diffuse_12  # Diffuse Sensor 12 (saída direita)
            write_coil(client, COIL_TURNTABLE_TURN, 1)  # MANTÉM LIGADO até caixa sair!
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
            roll_status = "Roll+ON"
        else:
            # Ejeta para ESQUERDA com Roll-
            sensor_saida = diffuse_11  # Diffuse Sensor 11 (saída esquerda)
            
            # DEBUG EXTRA: Mostra EXATAMENTE o que está sendo acionado
            print(f"\n[DEBUG-ESQ] Acionando: TURN=1, Roll+=0, Roll-=1")
            print(f"[DEBUG-ESQ] Sensor_saida (D11) = {sensor_saida}")
            
            write_coil(client, COIL_TURNTABLE_TURN, 1)  # MANTÉM LIGADO até caixa sair!
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 1)
            roll_status = "Roll-ON"
        
        # Conta ciclos
        TURNTABLE_STATE['ciclos_ejetando'] += 1
        
        # DEBUG: Mostra estado dos sensores CONTINUAMENTE com condição de parada
        condicao_parada = (front_limit == 0 and back_limit == 0 and sensor_saida == 0)
        if direcao == 'DIREITA':
            print(f"[EJETANDO-DIR #{TURNTABLE_STATE['ciclos_ejetando']}] Front={front_limit} Back={back_limit} D12={sensor_saida} | TURN=ON {roll_status} | PARAR?={condicao_parada}   ", end='\r')
        else:
            print(f"[EJETANDO-ESQ #{TURNTABLE_STATE['ciclos_ejetando']}] Front={front_limit} Back={back_limit} D11={sensor_saida} | TURN=ON {roll_status} | PARAR?={condicao_parada}   ", end='\r')
        
        # Verifica se caixa SAIU completamente (TODOS os 3 sensores OFF)
        if front_limit == 0 and back_limit == 0 and sensor_saida == 0:
            print(f"\n[TURNTABLE] *** CONDIÇÃO DE PARADA ATINGIDA! ***")
            print(f"[TURNTABLE] Front={front_limit}, Back={back_limit}, Sensor_saida={sensor_saida}")
            print(f"[TURNTABLE] Caixa ejetada para {direcao} após {TURNTABLE_STATE['ciclos_ejetando']} ciclos!")
            print(f"[TURNTABLE] Sensores liberados (Front=0, Back=0, Sensor_saída=0)")
            print(f"[TURNTABLE] Desligando Roll E TURN...")
            
            # Desliga Roll+ ou Roll- E TURN
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
            write_coil(client, COIL_TURNTABLE_TURN, 0)  # AGORA SIM desliga TURN!
            
            # NÃO religa esteiras aqui - só no IDLE!
            
            # Vai para RETORNANDO
            TURNTABLE_STATE['estado'] = 'RETORNANDO'
            TURNTABLE_STATE['timestamp'] = time.time()
            TURNTABLE_STATE.pop('ejetando_iniciado', None)  # Remove flag
            TURNTABLE_STATE.pop('ciclos_ejetando', None)
            TURNTABLE_STATE.pop('direcao', None)
            print(f"[TURNTABLE] Estado: EJETANDO → RETORNANDO")
    
    # ========== ESTADO: RETORNANDO (Volta para posição inicial 0°) ==========
    elif estado_atual == 'RETORNANDO':
        # Stack Light AMARELO - Retornando
        set_stack_light(client, red=0, green=0, yellow=1)
        
        # MANTÉM esteiras e Load 1 DESLIGADAS durante retorno
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        # Lê sensor de limite 0° (posição inicial)
        limit_0 = read_input(client, INP_TURNTABLE_LIMIT)
        
        print(f"[RETORNANDO] Limit0={limit_0}   ", end='\r')
        
        # TURN está DESLIGADO (turntable volta naturalmente por mola/gravidade)
        # NÃO precisa ligar TURN novamente!
        write_coil(client, COIL_TURNTABLE_TURN, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        # Verifica se voltou à posição inicial (Limit 0 acionado)
        if limit_0 == 1:
            print(f"\n[TURNTABLE] Limit 0° ON! Posição inicial alcançada.")
            
            # Desliga tudo
            parar_turntable(client)
            
            # RELIGA as esteiras e Load 1 SOMENTE AGORA - turntable pronto!
            print(f"[TURNTABLE] RELIGANDO esteiras e Load 1 - Turntable pronto!")
            write_coil(client, COIL_ROLLER_6M_1, 1)
            write_coil(client, COIL_CONVEYOR_1, 1)
            write_coil(client, COIL_CONVEYOR_2, 1)
            write_coil(client, COIL_LOAD_1, 1)
            
            # Volta ao IDLE
            TURNTABLE_STATE['estado'] = 'IDLE'
            TURNTABLE_STATE['caixa_atual'] = None
            print(f"[TURNTABLE] Estado: RETORNANDO → IDLE")
            print(f"[TURNTABLE] Pronto para próxima caixa!\n")

# ============================================================
# TRANSFERÊNCIA 2->1
# ============================================================

def transferencia_2_para_1(client, sensores, delay, resume):
    at_entry_1, at_transfer_1, at_transfer_2, at_exit = sensores
    if at_transfer_2 and not at_exit and not at_entry_1:
        print("[TRANSFER] Iniciando transferência 2→1...")
        for c in [COIL_CONVEYOR_1, COIL_CONVEYOR_2, COIL_EMITTER_1, COIL_EMITTER_2]:
            write_coil(client, c, 0)
        write_coil(client, COIL_TRANSFER_LEFT_1, 1)
        write_coil(client, COIL_TRANSFER_LEFT_2, 1)
        time.sleep(delay)
        while not read_input(client, INP_AT_TRANSFER_1):
            time.sleep(0.05)
        write_coil(client, COIL_TRANSFER_LEFT_1, 0)
        write_coil(client, COIL_TRANSFER_LEFT_2, 0)
        time.sleep(resume)
        ligar_esteiras_e_loads(client)
        ligar_emissores(client)
        print("[TRANSFER] Concluída.")

# ============================================================
# LOOP PRINCIPAL INTEGRADO
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    client = connect_modbus(args.host, args.port)
    desligar_tudo(client)
    print(f"[INFO] Conectado a {args.host}:{args.port}")

    # Estados do sistema
    sistema_ativo = False
    estop_ativo = False
    start_anterior = 0
    stop_anterior = 0
    estop_anterior = 0
    fila_caixas = []
    
    print("[INFO] Sistema aguardando START...")
    print("[INFO] Pressione START para iniciar ou RESET para emergency stop.")

    try:
        while True:
            # Lê botões
            start = read_input(client, INP_START)
            stop = read_input(client, INP_STOP)
            estop = read_input(client, INP_ESTOP)
            
            # Detecta borda de subida do START
            if start == 1 and start_anterior == 0:
                if estop_ativo:
                    print("[START] Liberando Emergency Stop...")
                    estop_ativo = False
                if not sistema_ativo:
                    print("[START] Iniciando sistema...")
                    sistema_ativo = True
                    ligar_esteiras_e_loads(client)
                    ligar_emissores(client)
                    print("[START] Sistema ATIVO! Produção iniciada.\n")
            
            # Detecta borda de subida do STOP
            if stop == 1 and stop_anterior == 0:
                if sistema_ativo:
                    print("[STOP] Parando sistema...")
                    sistema_ativo = False
                    desligar_tudo(client)
                    fila_caixas.clear()
                    print("[STOP] Sistema PARADO.\n")
            
            # Detecta borda de subida do ESTOP (Reset)
            if estop == 1 and estop_anterior == 0:
                print("[EMERGENCY STOP] Ativado!")
                estop_ativo = True
                sistema_ativo = False
                desligar_tudo(client)
                fila_caixas.clear()
                print("[ESTOP] Sistema em EMERGENCY STOP. Pressione START para liberar.\n")
            
            start_anterior = start
            stop_anterior = stop
            estop_anterior = estop
            
            # Só executa lógica se sistema ativo e sem ESTOP
            if sistema_ativo and not estop_ativo:
                # leituras operacionais
                at_entry_1 = read_input(client, INP_AT_ENTRY_1)
                at_transfer_1 = read_input(client, INP_AT_TRANSFER_1)
                at_transfer_2 = read_input(client, INP_AT_TRANSFER_2)
                at_exit = read_input(client, INP_AT_EXIT)

                # medição de altura / fila
                altura = medir_altura(client)
                if altura > 0 and (not fila_caixas or altura != fila_caixas[-1]):
                    fila_caixas.append(altura)
                    print(f"[ALTURA] Caixa detectada com tamanho {altura}. Fila: {fila_caixas}")

                # transferências e controle
                sensores = (at_entry_1, at_transfer_1, at_transfer_2, at_exit)
                transferencia_2_para_1(client, sensores, DEFAULT_EJECTION_DELAY, DEFAULT_RESUME_DELAY)

                # lógica do turntable integrado (auto-alimentação + ciclo de rotação)
                controlar_turntable(client, fila_caixas)

            time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Encerrado manualmente.")
    finally:
        desligar_tudo(client)
        client.close()
        print("[INFO] Desconectado do servidor Modbus.")

if __name__ == "__main__":
    main()

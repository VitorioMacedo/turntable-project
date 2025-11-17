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
] + [(f"Beam {i}", 16 + i) for i in range(1, 9)]  # Beam 1-8 (Input 17-24)

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
INP_DIFFUSE_0 = 30   # Diffuse Sensor 0 (detector de passagem após beams)
INPUT_BEAMS = [RESOLVED_INPUTS[f"Beam {i}"] for i in range(1, 9)]  # Beam 1-8

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
    set_stack_light(client, red=0, green=0, yellow=0)

def ligar_esteiras_e_loads(client):
    for coil in [COIL_LOAD_1, COIL_LOAD_2, COIL_CONVEYOR_1, COIL_CONVEYOR_2,
                 COIL_ROLLER_4M_0, COIL_ROLLER_4M_3, COIL_ROLLER_6M_1]:
        write_coil(client, coil, 1)

def ligar_emissores(client):
    write_coil(client, COIL_EMITTER_1, 1)
    write_coil(client, COIL_EMITTER_2, 1)

def medir_altura(client):
    bloqueados = 0
    debug_beams = []
    beam_values = {}
    
    # Lê todos os beams (8=mais baixo, 1=mais alto)
    for i in range(1, 9):
        addr = RESOLVED_INPUTS[f"Beam {i}"]
        valor = read_input(client, addr)
        beam_values[i] = valor
        debug_beams.append(f"B{i}={valor}")
    
    # Conta todos os beams bloqueados
    for i in range(1, 9):
        if beam_values[i]:
            bloqueados += 1
    
    # DEBUG: Mostra estado quando houver bloqueio
    if bloqueados > 0:
        print(f"[DEBUG-BEAMS] {' '.join(debug_beams)} | Total: {bloqueados}")
    
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
        set_stack_light(client, red=0, green=1, yellow=0)
        
        if diffuse == 1:
            write_coil(client, COIL_TURNTABLE_TURN, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
            
            TURNTABLE_STATE['estado'] = 'LOADING'
            TURNTABLE_STATE['timestamp'] = time.time()
            
            if fila_caixas:
                TURNTABLE_STATE['caixa_atual'] = fila_caixas.pop(0)
                print(f"[TURNTABLE] Carregando caixa tamanho {TURNTABLE_STATE['caixa_atual']} (Fila restante: {fila_caixas})")
            else:
                TURNTABLE_STATE['caixa_atual'] = None
                print(f"[TURNTABLE] Carregando caixa (tamanho desconhecido - fila vazia)")
        else:
            parar_turntable(client)
    
    # ========== ESTADO: LOADING (Puxando caixa) ==========
    elif estado_atual == 'LOADING':
        set_stack_light(client, red=0, green=1, yellow=0)
        
        if back_limit == 1:
            write_coil(client, COIL_ROLLER_6M_1, 0)
            write_coil(client, COIL_CONVEYOR_1, 0)
            write_coil(client, COIL_CONVEYOR_2, 0)
            write_coil(client, COIL_LOAD_1, 0)
        
        write_coil(client, COIL_TURNTABLE_TURN, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        if front_limit == 1:
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            TURNTABLE_STATE['estado'] = 'POSICIONADO'
            TURNTABLE_STATE['timestamp'] = time.time()
    
    # ========== ESTADO: POSICIONADO (Pronto para girar) ==========
    elif estado_atual == 'POSICIONADO':
        set_stack_light(client, red=0, green=0, yellow=1)
        
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        tamanho = TURNTABLE_STATE['caixa_atual']
        
        if tamanho in [1, 2]:
            TURNTABLE_STATE['direcao'] = 'DIREITA'  # Na visão do usuário: ESQUERDA
            print(f"[SEPARADOR] Caixa tamanho {tamanho} → ESQUERDA (sua visão)")
        elif tamanho in [3, 4]:
            TURNTABLE_STATE['direcao'] = 'ESQUERDA'  # Na visão do usuário: DIREITA
            print(f"[SEPARADOR] Caixa tamanho {tamanho} → DIREITA (sua visão)")
        else:
            # Fallback para tamanhos inesperados
            TURNTABLE_STATE['direcao'] = 'ESQUERDA'
            print(f"[SEPARADOR] Caixa tamanho {tamanho} (desconhecido) → DIREITA (sua visão)")
        
        write_coil(client, COIL_TURNTABLE_TURN, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        TURNTABLE_STATE['estado'] = 'GIRANDO'
        TURNTABLE_STATE['contador_giro'] = 0
        TURNTABLE_STATE['timestamp'] = time.time()
    
    # ========== ESTADO: GIRANDO (Rotação de 90°) ==========
    elif estado_atual == 'GIRANDO':
        set_stack_light(client, red=0, green=0, yellow=1)
        
        limit_90 = read_input(client, INP_TURNTABLE_LIMIT_90)
        
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        write_coil(client, COIL_TURNTABLE_TURN, 1)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        if limit_90 == 1:
            TURNTABLE_STATE['estado'] = 'EJETANDO'
            TURNTABLE_STATE['timestamp'] = time.time()
    
    # ========== ESTADO: EJETANDO (Empurrando caixa para esteira) ==========
    elif estado_atual == 'EJETANDO':
        set_stack_light(client, red=1, green=0, yellow=0)
        
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        front_limit = read_input(client, INP_TURNTABLE_FRONT)
        back_limit = read_input(client, INP_TURNTABLE_BACK)
        diffuse_11 = read_input(client, INP_DIFFUSE_11)
        diffuse_12 = read_input(client, INP_DIFFUSE_12)
        
        direcao = TURNTABLE_STATE.get('direcao', 'DIREITA')
        
        if direcao == 'DIREITA':
            sensor_saida = diffuse_12
            write_coil(client, COIL_TURNTABLE_TURN, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        else:
            sensor_saida = diffuse_11
            write_coil(client, COIL_TURNTABLE_TURN, 1)
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 1)
        
        if front_limit == 0 and back_limit == 0 and sensor_saida == 0:
            print(f"[SEPARADOR] Caixa ejetada para {direcao}")
            
            write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
            write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
            write_coil(client, COIL_TURNTABLE_TURN, 0)
            
            TURNTABLE_STATE['estado'] = 'RETORNANDO'
            TURNTABLE_STATE['timestamp'] = time.time()
            TURNTABLE_STATE.pop('direcao', None)
    
    # ========== ESTADO: RETORNANDO (Volta para posição inicial 0°) ==========
    elif estado_atual == 'RETORNANDO':
        set_stack_light(client, red=0, green=0, yellow=1)
        
        write_coil(client, COIL_ROLLER_6M_1, 0)
        write_coil(client, COIL_CONVEYOR_1, 0)
        write_coil(client, COIL_CONVEYOR_2, 0)
        write_coil(client, COIL_LOAD_1, 0)
        
        limit_0 = read_input(client, INP_TURNTABLE_LIMIT)
        
        write_coil(client, COIL_TURNTABLE_TURN, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_PLUS, 0)
        write_coil(client, COIL_TURNTABLE_ROLL_MINUS, 0)
        
        if limit_0 == 1:
            parar_turntable(client)
            
            write_coil(client, COIL_ROLLER_6M_1, 1)
            write_coil(client, COIL_CONVEYOR_1, 1)
            write_coil(client, COIL_CONVEYOR_2, 1)
            write_coil(client, COIL_LOAD_1, 1)
            
            TURNTABLE_STATE['estado'] = 'IDLE'
            TURNTABLE_STATE['caixa_atual'] = None
            print(f"[SEPARADOR] Pronto para próxima caixa\n")

# ============================================================
# TRANSFERÊNCIA 2->1
# ============================================================

def transferencia_2_para_1(client, sensores, delay, resume):
    at_entry_1, at_transfer_1, at_transfer_2, at_exit = sensores
    # Só ativa transferência se at_transfer_2 está ON e TODOS os outros sensores estão OFF
    if at_transfer_2 and not at_exit and not at_entry_1 and not at_transfer_1:
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
    print(f"[SISTEMA] Conectado a {args.host}:{args.port}")
    print(f"[SISTEMA] Aguardando START...\n")

    # Estados do sistema
    sistema_ativo = False
    estop_ativo = False
    start_anterior = 0
    stop_anterior = 0
    estop_anterior = 0
    fila_caixas = []
    
    # Controle de detecção de altura com sensor único
    sensor_passagem_anterior = 0
    altura_maxima_atual = 0

    try:
        while True:
            # Lê botões
            start = read_input(client, INP_START)
            stop = read_input(client, INP_STOP)
            estop = read_input(client, INP_ESTOP)
            
            # Detecta borda de subida do START
            if start == 1 and start_anterior == 0:
                if estop_ativo:
                    estop_ativo = False
                if not sistema_ativo:
                    sistema_ativo = True
                    ligar_esteiras_e_loads(client)
                    ligar_emissores(client)
                    print("[SISTEMA] Iniciado\n")
            
            # Detecta borda de subida do STOP
            if stop == 1 and stop_anterior == 0:
                if sistema_ativo:
                    sistema_ativo = False
                    desligar_tudo(client)
                    fila_caixas.clear()
                    sensor_passagem_anterior = 0
                    altura_maxima_atual = 0
                    print("[SISTEMA] Parado\n")
            
            # Detecta borda de subida do ESTOP (Reset)
            if estop == 1 and estop_anterior == 0:
                estop_ativo = True
                sistema_ativo = False
                desligar_tudo(client)
                fila_caixas.clear()
                sensor_passagem_anterior = 0
                altura_maxima_atual = 0
                print("[SISTEMA] Emergency Stop\n")
            
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
                
                # Sensor de detecção de passagem (após os beams)
                sensor_passagem = read_input(client, INP_DIFFUSE_0)
                
                # Enquanto o sensor detecta a caixa (ON), mede a altura continuamente
                if sensor_passagem == 1:
                    altura = medir_altura(client)
                    # Não subtrai nada - o número de beams bloqueados = tamanho da caixa
                    
                    if altura > altura_maxima_atual:
                        altura_maxima_atual = altura
                        print(f"[ALTURA] Medindo: {altura}")
                
                # Quando sensor vai para OFF (borda de descida) = caixa passou completamente
                if sensor_passagem == 0 and sensor_passagem_anterior == 1:
                    if altura_maxima_atual > 0:
                        fila_caixas.append(altura_maxima_atual)
                        print(f"[ALTURA] ✓ Caixa detectada - Tamanho: {altura_maxima_atual} | Fila: {fila_caixas}")
                        altura_maxima_atual = 0
                
                sensor_passagem_anterior = sensor_passagem

                # transferências e controle
                sensores = (at_entry_1, at_transfer_1, at_transfer_2, at_exit)
                transferencia_2_para_1(client, sensores, DEFAULT_EJECTION_DELAY, DEFAULT_RESUME_DELAY)

                # lógica do turntable integrado (auto-alimentação + ciclo de rotação)
                controlar_turntable(client, fila_caixas)

            time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\n[SISTEMA] Encerrado")
    finally:
        desligar_tudo(client)
        client.close()

if __name__ == "__main__":
    main()

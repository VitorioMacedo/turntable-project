# Factory I/O – Turntable Sorting System

Sistema de separação automatizada de caixas utilizando Python 3.11, Modbus TCP e uma célula simulada no Factory I/O.  
A lógica inclui medição de altura, roteamento por direção e controle completo da turntable através de uma máquina de estados industrial.

---

## Visão da Célula de Separação – Factory I/O

A cena representa uma célula industrial com:
- Esteira central de alimentação  
- Turntable rotativa  
- Duas linhas laterais (esquerda/direita)  
- Sensores difusos, ópticos e limites mecânicos  

O controlador identifica a caixa, mede sua altura e executa:
- Carregamento  
- Posicionamento  
- Giro (90°)  
- Ejeção  
- Retorno para 0°  

Toda a lógica é gerenciada por uma máquina de estados sincronizada com as esteiras.

## 🏭 Planta Industrial
<img width="601" height="336" alt="image" src="https://github.com/user-attachments/assets/9407570d-7143-42ea-9653-3e9329f4cc5f" />

## Tecnologias

- Python 3.11  
- Modbus TCP (pymodbus)  
- Factory I/O  
- Mermaid (diagramas de estado)

---

## Estrutura do Projeto

```
controlador_fabrica_v_17.py
gerar_diagrama_mermaid.py
factory_tags.csv
cena_separador.factoryio

docs/
 ├─ DIAGRAMA_ESTADOS_TURNTABLE.md
 ├─ README_CODIGO.md
 └─ README_FUNCIONAMENTO.md
```

---

## Como Rodar o Sistema

### 1. Iniciar o Controlador Modbus

```
python controlador_fabrica_v_17.py
```

### 2. Configurar o Factory I/O

Driver: Modbus TCP  
Modo: Client  
Host: 127.0.0.1  
Port: 502  

Passos:
- Carregar a cena  
- Verificar endereços  
- Pressionar RUN  

Os endereços são mapeados automaticamente por `factory_tags.csv`.
<img width="601" height="600" alt="image" src="https://github.com/VitorioMacedo/turntable-project/blob/8524fe26f261a746c82b23268e999cd397e7594c/Drive.png" />

---

## Conectar Sensores e Atuadores

- Cada sensor no Factory I/O tem um nome claro.  
- O Python lê `factory_tags.csv` usando `carregar_mapa_factoryio()`.  
- Endereços críticos são fixos no código (ex.: turntable e stack light).

<img width="601" height="600" alt="image" src="https://github.com/VitorioMacedo/turntable-project/blob/98712f394471568ba6ed0d920c87d909e65c2e9a/atuadores.png" />
---

## Sobre o Controlador Modbus

### Controlador Principal
- Implementa Start / Stop / Emergency Stop  
- Faz leitura e escrita Modbus  
- Gerencia fila de caixas e estados  

### Mapa Factory I/O
- Centraliza nomes e endereços  
- Facilita manutenção  

### Funções
- desligar_tudo()  
- ligar_esteiras_e_loads()  
- ligar_emissores()  
- medir_altura()  

### Máquina de Estados
<img width="601" height="600" alt="image" src="https://github.com/VitorioMacedo/turntable-project/blob/66fad7fb0fce3e51fc5acb8e94f48366b1244c21/arquitetura.jpg" /> 

---

## Diagramas da Máquina de Estados
- `docs/DIAGRAMA_ESTADOS_TURNTABLE.md`  
- `gerar_diagrama_mermaid.py`

---

## Arquitetura

```
Factory I/O ── Modbus TCP ──> controlador_fabrica_v_17.py
 ↑                                      │
 └────── factory_tags.csv ◄────────────┘
```

---

## Referências

- Factory I/O – Driver Modbus  
- Modbus TCP  
- pymodbus  
- Mermaid  

# Sistema de Controle de Turntable - Funcionamento

Sistema automatizado de separação de caixas por tamanho usando turntable rotativa.

## Estados da Máquina

1. **IDLE** 🟢 Verde - Sistema pronto
2. **LOADING** 🟢 Verde - Carregando caixa  
3. **POSICIONADO** 🟡 Amarelo - Preparando para girar
4. **GIRANDO** 🟡 Amarelo - Rotação 90°
5. **EJETANDO** 🔴 Vermelho - Empurrando caixa
6. **RETORNANDO** 🟡 Amarelo - Volta à posição inicial

## Lógica de Separação

- Tamanho 1 → DIREITA
- Outros → ESQUERDA

## Controle de Esteiras

Param quando caixa sobe (Back sensor) e religam só quando turntable volta ao IDLE.

# 🤖 Bot de Trading Bitcoin - Binance

Bot de trading automatizado para Bitcoin (BTCBRL) na Binance, com análise técnica multi-indicador e gerenciamento de risco avançado.

## 🎯 Características

- **Meta de lucro**: Mínimo de R$1.000,00 por trade
- **Análise multi-indicador**: RSI, MACD, Bollinger Bands, EMA
- **Stop-loss dinâmico**: Baseado em ATR (volatilidade) e percentual fixo
- **Trailing stop**: Maximiza ganhos acompanhando o preço
- **Take-profit ajustável**: Aumenta com a confiança do sinal
- **Confirmação de tendência**: Usa timeframe maior (1h) para confirmar sinais
- **Modo simulação**: Teste sem risco antes de operar com dinheiro real

## 📋 Pré-requisitos

- Python 3.10+
- Conta na Binance com API habilitada
- Saldo suficiente em BRL para atingir a meta (recomendado: R$25.000+)

## 🔧 Instalação

```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

Defina as variáveis de ambiente:

```bash
# Obrigatórias
export BINANCE_API_KEY="sua_api_key"
export BINANCE_API_SECRET="sua_api_secret"

# Opcionais (valores padrão mostrados)
export DRY_RUN=true                  # true = simulação, false = operações reais
export MIN_PROFIT_BRL=1000           # Meta de lucro mínimo por trade (R$)
export STOP_LOSS_PCT=0.02            # Stop-loss: 2%
export TAKE_PROFIT_PCT=0.04          # Take-profit: 4% (risk:reward 1:2)
export TRAILING_STOP_PCT=0.015       # Trailing stop: 1.5%
export MAX_POSITION_PCT=0.25         # Máximo 25% do saldo por trade
export CHECK_INTERVAL_SECONDS=60     # Intervalo entre análises (segundos)
export ANALYSIS_INTERVAL=15m         # Timeframe de análise
export TREND_INTERVAL=1h             # Timeframe para tendência
```

## 🚀 Execução

### Modo simulação (recomendado para testes)
```bash
python run_trader.py
```

### Modo live (operações reais)
```bash
DRY_RUN=false python run_trader.py
```

## 📊 Estratégia de Trading

### Indicadores utilizados

| Indicador | Uso | Sinal de Compra | Sinal de Venda |
|-----------|-----|-----------------|----------------|
| **RSI** | Sobrecompra/sobrevenda | RSI < 30 | RSI > 70 |
| **MACD** | Momentum | Cruzamento altista | Cruzamento baixista |
| **EMA 9/21** | Tendência curta | EMA rápida cruza acima | EMA rápida cruza abaixo |
| **Bollinger Bands** | Volatilidade | Preço na banda inferior | Preço na banda superior |
| **Volume** | Confirmação | Volume acima da média confirma | Volume acima da média confirma |

### Sistema de pontuação

Cada indicador contribui com pontos (+2 a -2). A decisão depende da pontuação total:
- **Compra**: Score ≥ 3 pontos
- **Venda**: Score ≤ -3 pontos
- **Aguardar**: Score entre -2 e 2

### Filtro de tendência

Antes de comprar, o bot verifica a tendência no timeframe de 1h:
- Tendência de **alta** → Permite compra
- Tendência **lateral** → Permite compra
- Tendência de **baixa** → Bloqueia compra (evita operar contra a tendência)

## 🛡️ Gerenciamento de Risco

### Stop-Loss
- **Percentual fixo**: 2% abaixo do preço de entrada
- **Baseado em ATR**: 2x ATR abaixo do preço de entrada
- Usa o **mais conservador** (mais próximo do preço)

### Take-Profit
- **Base**: 4% acima do preço de entrada (risk:reward 1:2)
- **Ajustável**: Aumenta até 10% com alta confiança do sinal

### Trailing Stop
- Ativado quando o preço ultrapassa o ponto de entrada
- Acompanha o preço a 1.5% de distância do máximo
- Protege ganhos não realizados

### Tamanho da posição
- Calcula automaticamente para atingir a meta de R$1.000
- Nunca excede 25% do saldo disponível
- Ajustado com base na volatilidade (ATR)

## ⚠️ Avisos Importantes

1. **Risco financeiro**: Trading de criptomoedas envolve risco significativo de perda. Nunca invista mais do que pode perder.
2. **Modo simulação**: Sempre teste extensivamente em modo simulação antes de usar dinheiro real.
3. **Segurança da API**: 
   - Nunca compartilhe suas chaves API
   - Configure permissões mínimas na API (apenas spot trading)
   - Desabilite retiradas na API
   - Use IP whitelist
4. **Monitoramento**: Mesmo no modo automático, monitore o bot regularmente.
5. **Sem garantias**: Desempenho passado não garante resultados futuros.

## 📁 Estrutura do Projeto

```
binance_trader/
├── __init__.py          # Package init
├── config.py            # Configurações e variáveis de ambiente
├── indicators.py        # Indicadores técnicos (RSI, MACD, BB, EMA, ATR)
├── strategy.py          # Estratégia de trading com sistema de pontuação
├── risk_manager.py      # Gerenciamento de risco (SL, TP, trailing stop)
└── trader.py            # Bot principal com integração Binance
run_trader.py            # Script de entrada
requirements.txt         # Dependências Python
```

## 📝 Logs

O bot gera logs detalhados em:
- **Console**: Saída em tempo real
- **trader.log**: Arquivo de log persistente

Cada ciclo mostra:
- Tendência geral do mercado
- Sinais de cada indicador
- Pontuação total e decisão
- Status da posição atual
- P&L realizado e não realizado

# TradyBull - Claude Instructions

## Description

TradyBull est un dashboard de trading pour les Nasdaq 100 Futures (NQ=F). L'application permet d'explorer les graphiques avec différents indicateurs techniques, et de backtester des stratégies de trading avec calcul automatique des signaux et KPIs.

## Stack Technique

### Frontend (Next.js)
- **Framework**: Next.js 16 avec App Router
- **React**: 19.2
- **Charts**: lightweight-charts v5
- **UI**: Tailwind CSS 4, shadcn/ui (style new-york)
- **Icons**: lucide-react
- **Port**: 3080

### Backend (Python FastAPI)
- **Framework**: FastAPI avec uvicorn
- **Data Source**: yfinance (Yahoo Finance)
- **Database**: SQLite (tradybull.db)
- **WebSocket**: Communication temps réel avec le frontend
- **Port**: 8000

## Structure du Projet

```
tradybull/
├── src/
│   ├── app/
│   │   ├── page.tsx                    # Redirect vers /exploration/real-time
│   │   ├── layout.tsx                  # Layout principal avec Sidebar
│   │   ├── exploration/
│   │   │   ├── real-time/              # Exploration temps réel
│   │   │   │   ├── page.tsx            # Multi-indicator view
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── realtime-context.tsx
│   │   │   │   ├── bollinger/
│   │   │   │   ├── macd/
│   │   │   │   ├── ichimoku/
│   │   │   │   ├── moving-averages/
│   │   │   │   └── stochastic-rsi/
│   │   │   └── historical/             # Exploration données historiques
│   │   │       ├── page.tsx
│   │   │       ├── layout.tsx
│   │   │       ├── historical-context.tsx  # Context partagé pour zoom/data
│   │   │       ├── bollinger/
│   │   │       ├── macd/
│   │   │       ├── ichimoku/
│   │   │       ├── moving-averages/
│   │   │       └── stochastic-rsi/
│   │   └── strategy/
│   │       ├── real-time/              # Stratégies temps réel
│   │       │   ├── page.tsx
│   │       │   ├── layout.tsx
│   │       │   └── [strategy]/page.tsx # Page dynamique par stratégie
│   │       └── backtesting/            # Backtesting stratégies
│   │           ├── page.tsx
│   │           ├── layout.tsx
│   │           ├── overview/page.tsx   # Tableau comparatif KPIs
│   │           └── [strategy]/page.tsx # Page dynamique par stratégie
│   ├── components/
│   │   ├── chart/
│   │   │   ├── candlestick-chart.tsx   # Graphique principal
│   │   │   └── chart-navigator.tsx     # Barre de zoom/navigation
│   │   ├── dashboard/
│   │   │   ├── exploration-dashboard.tsx
│   │   │   ├── realtime-exploration-dashboard.tsx
│   │   │   ├── historical-dashboard.tsx
│   │   │   ├── multi-indicator-historical-dashboard.tsx
│   │   │   ├── strategy-backtesting-dashboard.tsx
│   │   │   └── strategy-realtime-dashboard.tsx
│   │   ├── kpi/
│   │   │   ├── kpi-tiles.tsx           # Tuiles KPI individuelles
│   │   │   └── kpi-overview-table.tsx  # Tableau comparatif stratégies
│   │   ├── sidebar/
│   │   │   └── sidebar.tsx             # Navigation avec mode switch
│   │   └── ui/                         # Composants shadcn/ui
│   │       ├── button.tsx
│   │       ├── calendar.tsx
│   │       ├── date-picker.tsx
│   │       ├── group-button.tsx
│   │       ├── popover.tsx
│   │       └── tooltip.tsx
│   ├── hooks/
│   │   ├── useStrategies.ts            # Récupère la liste des stratégies
│   │   ├── useSignals.ts               # Récupère les signaux d'une stratégie
│   │   └── useKPIs.ts                  # Récupère les KPIs (simple + all)
│   ├── lib/
│   │   └── utils.ts
│   └── types/
│       └── market.ts                   # CandleData, TimeFrame, Signal
├── backend/
│   ├── main.py                         # API FastAPI + WebSocket
│   ├── signal_calculator.py            # Orchestrateur calcul signaux
│   ├── kpi_calculator.py               # Calcul des KPIs
│   ├── bootstrap_backtest.py           # Charge l'historique depuis yfinance
│   ├── bootstrap_signals.py            # Calcule tous les signaux
│   ├── import_csv.py                   # Import données CSV
│   ├── requirements.txt
│   ├── tradybull.db                    # Base SQLite
│   └── strategies/                     # Définitions des stratégies
│       ├── __init__.py                 # Registry STRATEGIES
│       ├── base.py                     # BaseStrategy, Signal, StrategyDisplayConfig
│       ├── bollinger_nosl.py
│       ├── bollinger_sl1.py
│       ├── bollinger_sl1_trend.py
│       ├── bollinger_sl1_crossing.py
│       ├── bollinger_sl25.py
│       ├── bollinger_sl25_trend.py
│       ├── bollinger_sl25_crossing.py
│       ├── daily.py
│       ├── daily_sl1.py
│       ├── daily_sl1_trend.py
│       ├── daily_sl1_trend_v2.py
│       ├── daily_sl1_crossing.py
│       ├── daily_sl25.py
│       ├── daily_sl25_trend.py
│       ├── daily_sl25_crossing.py
│       ├── trend.py
│       └── trend_22h.py
└── public/
    └── logo*.svg
```

## Commandes

### Frontend
```bash
npm run dev      # Démarre sur http://localhost:3080
npm run build    # Build production
npm run lint     # ESLint
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py   # Démarre sur http://localhost:8000

# Scripts utilitaires
python bootstrap_backtest.py        # Charge 730 jours d'historique 1H
python bootstrap_signals.py         # Calcule les signaux pour toutes les stratégies
python bootstrap_signals.py -f      # Force recalcul (efface et recalcule)
python bootstrap_signals.py -s bollinger-sl1  # Calcul pour une stratégie
python import_csv.py <fichier.csv>  # Import données CSV
```

### Base de données
```bash
sqlite3 backend/tradybull.db
.schema                              # Voir les tables
SELECT COUNT(*) FROM candles;        # Bougies temps réel
SELECT COUNT(*) FROM backtest_candles; # Bougies backtest
SELECT COUNT(*) FROM signals;        # Signaux calculés
SELECT strategy_name, COUNT(*) FROM signals GROUP BY strategy_name;
```

## Architecture

### Modes de l'Application

L'application a 2 modes principaux (toggle dans la sidebar) :

1. **Exploration** : Visualisation des indicateurs techniques
   - Real-Time : Données en temps réel via WebSocket
   - Historical : Données historiques avec zoom/navigation

2. **Strategy** : Test et analyse des stratégies de trading
   - Real-Time : Signaux calculés sur données live
   - Backtesting : Analyse historique avec KPIs

### Système de Stratégies

Les stratégies sont définies en Python et héritent de `BaseStrategy` :

```python
class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Identifiant unique (e.g., 'bollinger-sl1')"""

    @property
    @abstractmethod
    def display_config(self) -> StrategyDisplayConfig:
        """Configuration d'affichage frontend"""

    @property
    @abstractmethod
    def required_lookback(self) -> int:
        """Nombre de bougies nécessaires avant le premier signal"""

    @abstractmethod
    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        """Calcule les signaux"""
```

#### Signal
```python
@dataclass
class Signal:
    signal_timestamp: int      # Timestamp du marker (bougie suivante)
    trigger_timestamp: int     # Timestamp de la bougie déclencheuse
    type: str                  # 'buy' ou 'sell'
    price: float              # Prix d'entrée/sortie
    label: Optional[str]      # Label optionnel
    metadata: Optional[Dict]  # Données additionnelles
```

#### Stratégies Disponibles

| Nom | Description |
|-----|-------------|
| `bollinger-nosl` | Bollinger sans Stop Loss, close à 22h |
| `bollinger-sl1` | Bollinger avec SL -1%, close à 22h |
| `bollinger-sl25` | Bollinger avec SL -2.5%, close à 22h |
| `bollinger-sl1-trend` | SL -1% + filtre tendance MA200 |
| `bollinger-sl25-trend` | SL -2.5% + filtre tendance MA200 |
| `bollinger-sl1-crossing` | SL -1% + attente croisement MA200 |
| `bollinger-sl25-crossing` | SL -2.5% + attente croisement MA200 |
| `daily` | Signal daily sans SL |
| `daily-sl1` | Daily avec SL -1% |
| `daily-sl25` | Daily avec SL -2.5% |
| `daily-sl1-trend` | Daily SL -1% + filtre tendance |
| `daily-sl1-trend-v2` | Variante v2 du trend |
| `daily-sl25-trend` | Daily SL -2.5% + filtre tendance |
| `daily-sl1-crossing` | Daily SL -1% + croisement |
| `daily-sl25-crossing` | Daily SL -2.5% + croisement |
| `trend` | Trend following basé sur MA200 |
| `trend-22h` | Trend avec entrées à 22h uniquement |

### Calcul des KPIs

Le module `kpi_calculator.py` calcule :

```python
@dataclass
class StrategyKPIs:
    total_return_pct: float          # Rendement total (%)
    win_rate_pct: float              # Taux de réussite (%)
    profit_factor: float             # Profit Factor
    max_drawdown_pct: float          # Drawdown maximum (%)
    num_trades: int                  # Nombre de trades
    avg_return_per_trade_pct: float  # Rendement moyen par trade (%)
    avg_trade_duration_hours: float  # Durée moyenne des trades (h)
```

## API Endpoints

### Données de Marché
- `GET /api/nasdaq?interval=15min|1h|1day` - Données temps réel
- `GET /api/status` - État du marché et infos
- `GET /api/backtest/info` - Infos sur les données historiques
- `GET /api/backtest/data?start=&end=&limit=` - Données historiques

### Signaux
- `GET /api/signals?strategy=bollinger-sl1&start=&end=` - Signaux d'une stratégie
- `GET /api/signals/info?strategy=bollinger-sl1` - Stats des signaux
- `GET /api/signals/strategies` - Liste toutes les stratégies
- `POST /api/signals/calculate?strategy=&source=backtest|realtime` - Déclenche le calcul

### KPIs
- `GET /api/kpis?strategy=bollinger-sl1&start=&end=` - KPIs d'une stratégie
- `GET /api/kpis/all?start=&end=` - KPIs de toutes les stratégies

### WebSocket
- `ws://localhost:8000/ws` - Données temps réel + signaux

## Conventions de Code

### TypeScript/React
- Composants fonctionnels avec hooks
- `'use client'` pour les composants interactifs
- Types dans `src/types/`
- Pas de `any`, utiliser des types explicites

### Styles
- Tailwind CSS avec classes utilitaires
- Couleur primaire (brand): `#C59471` (cuivre/bronze)
- Light/Dark mode supporté
- Dark mode: Fond `#0a0a0a`, `#0d0d0d`, bordures `#1a1a1a`

### Indicateurs Techniques (dans candlestick-chart.tsx)
- Bollinger Bands: BB_PERIOD=20, BB_STD_DEV=2
- MACD: MACD_FAST=12, MACD_SLOW=26, MACD_SIGNAL=9
- Ichimoku: TENKAN=9, KIJUN=26, SENKOU_B=52
- Moving Averages: MA_SHORT=20, MA_MEDIUM=50, MA_LONG=200
- Stochastic RSI: PERIOD=14, K_SMOOTH=3, D_SMOOTH=3

### lightweight-charts v5
- Utiliser `createSeriesMarkers()` pour les markers (pas `setMarkers()`)
- Les temps utilisent `chartTimes[]` (format ajusté timezone Paris)
- Type `SeriesMarker<Time>` pour les markers

## Données

### Timeframes (temps réel avec rétention)
- `15min`: Rétention 6 jours
- `1h`: Rétention 21 jours
- `1day`: Rétention 540 jours

### Backtest
- Intervalle: 1H uniquement
- Pas de rétention (données permanentes)
- Source: yfinance ou CSV

### Symbole
- Uniquement `NQ=F` (Nasdaq 100 Futures)
- Timezone: Europe/Paris

## Tables SQLite

```sql
-- Bougies temps réel
candles (id, interval, timestamp, open, high, low, close, volume)

-- Bougies historiques
backtest_candles (id, symbol, timestamp, open, high, low, close, volume, source)

-- Signaux calculés
signals (id, strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata, created_at)

-- État de traitement (pour calcul incrémental)
signal_processing_state (id, strategy_name, symbol, data_source, last_processed_timestamp, last_signal_state, updated_at)
```

## Hooks Frontend

### useStrategies
```tsx
const { strategies, isLoading, error } = useStrategies();
// strategies: StrategyConfig[] avec name, display_name, description, show_*
```

### useSignals
```tsx
const { signals, isLoading, error, refetch } = useSignals({
  strategy: 'bollinger-sl1',
  startTs: 1700000000,
  endTs: 1710000000,
  enabled: true,
});
```

### useKPIs
```tsx
const { kpis, isLoading, error, refetch } = useKPIs({
  strategy: 'bollinger-sl1',
  startTs,
  endTs,
  enabled: true,
});

// Pour toutes les stratégies
const { data, isLoading, error, refetch } = useAllKPIs({ startTs, endTs });
```

## Notes Importantes

1. **Timezone**: Toutes les heures sont en Europe/Paris
2. **Signaux**: Calculés côté backend, stockés en base, servis via API
3. **Charts**: Seul le chart 1H affiche les signaux de trading
4. **Navigator**: Utilisé uniquement pour les données historiques (zoom/pan)
5. **Build**: Toujours vérifier `npm run build` après modifications
6. **Database**: Utiliser les scripts bootstrap_* pour initialiser
7. **Stratégies dynamiques**: La sidebar charge les stratégies depuis l'API
8. **shadcn/ui**: Utiliser `npx shadcn@latest add <component>` pour ajouter

## Créer une Nouvelle Stratégie

1. Créer `backend/strategies/my_strategy.py` qui hérite de `BaseStrategy`
2. Implémenter `name`, `display_config`, `required_lookback`, `calculate_signals`
3. Ajouter l'import et l'entrée dans `backend/strategies/__init__.py`
4. Exécuter `python bootstrap_signals.py -s my-strategy` pour calculer les signaux
5. La stratégie apparaîtra automatiquement dans la sidebar

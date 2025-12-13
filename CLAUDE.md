# TradyBull - Claude Instructions

## Description

TradyBull est un dashboard de trading en temps réel pour les Nasdaq 100 Futures (NQ=F). L'application affiche des graphiques de chandeliers avec différents indicateurs techniques et permet l'analyse de stratégies de trading.

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
│   ├── app/                    # Pages Next.js (App Router)
│   │   ├── page.tsx            # Page Exploration (/)
│   │   ├── layout.tsx          # Layout avec Sidebar
│   │   ├── strategies/         # Pages stratégies temps réel
│   │   │   ├── bollinger/
│   │   │   ├── macd/
│   │   │   ├── ichimoku/
│   │   │   ├── moving-averages/
│   │   │   └── stochastic-rsi/
│   │   └── backtesting/        # Pages backtesting
│   │       └── strat-1/
│   ├── components/
│   │   ├── chart/
│   │   │   └── candlestick-chart.tsx  # Composant principal des graphiques
│   │   ├── dashboard/
│   │   │   ├── trading-dashboard.tsx   # Dashboard temps réel
│   │   │   └── exploration-dashboard.tsx
│   │   ├── sidebar/
│   │   │   └── sidebar.tsx
│   │   └── ui/                 # Composants shadcn/ui
│   ├── lib/
│   │   └── utils.ts            # Utilitaires (cn function)
│   └── types/
│       └── market.ts           # Types CandleData, TimeFrame
├── backend/
│   ├── main.py                 # API FastAPI + WebSocket
│   ├── bootstrap_backtest.py   # Script pour charger l'historique
│   ├── import_csv.py           # Import données CSV
│   ├── requirements.txt
│   └── tradybull.db            # Base SQLite
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
python bootstrap_backtest.py        # Charge 730 jours d'historique
python import_csv.py <fichier.csv>  # Import données CSV
```

### Base de données
```bash
sqlite3 backend/tradybull.db
.schema                              # Voir les tables
SELECT COUNT(*) FROM candles;        # Compter les bougies temps réel
SELECT COUNT(*) FROM backtest_candles; # Compter les bougies backtest
```

## Conventions de Code

### TypeScript/React
- Composants fonctionnels avec hooks
- `'use client'` pour les composants interactifs
- Types dans `src/types/`
- Pas de `any`, utiliser des types explicites

### Styles
- Tailwind CSS avec classes utilitaires
- Couleur primaire: `#C59471` (cuivre/bronze)
- Dark mode par défaut (`className="dark"` sur html)
- Fond: `#0a0a0a`, `#0d0d0d`
- Bordures: `#1a1a1a`

### Indicateurs Techniques (dans candlestick-chart.tsx)
- Bollinger Bands: BB_PERIOD=20, BB_STD_DEV=2
- MACD: MACD_FAST=12, MACD_SLOW=26, MACD_SIGNAL=9
- Ichimoku: TENKAN=9, KIJUN=26, SENKOU_B=52
- Moving Averages: MA_SHORT=20, MA_MEDIUM=50, MA_LONG=200
- Stochastic RSI: PERIOD=14, K_SMOOTH=3, D_SMOOTH=3

### lightweight-charts v5
- Utiliser `createSeriesMarkers()` pour les markers (pas `setMarkers()`)
- Les temps doivent utiliser `chartTimes[]` (format ajusté timezone Paris)
- Type `SeriesMarker<Time>` pour les markers

## Données

### Timeframes
- `15min`: Rétention 6 jours
- `1h`: Rétention 21 jours
- `1day`: Rétention 540 jours

### Symbole
- Uniquement `NQ=F` (Nasdaq 100 Futures)
- Timezone: Europe/Paris

### WebSocket
- URL: `ws://localhost:8000/ws`
- Message type: `data_update`
- Rafraîchissement: toutes les 10 secondes

## Signaux de Trading (Bollinger)

### Règles
1. **Signal Buy**: Quand le LOW d'une bougie passe sous la bande Bollinger basse
2. **Placement**: Le signal apparaît sur la bougie SUIVANTE (achat à l'ouverture)
3. **Pas de signal consécutif**: Attendre que le LOW remonte AU-DESSUS de la bande
4. **Signal majeur**: Premier signal après 7h (heure Paris) = jaune vif + "Buy"
5. **Signal secondaire**: Autres signaux du jour = jaune transparent, sans texte

### Props TradingDashboard
```tsx
<TradingDashboard
  pageName="Bollinger Bands"
  showBollinger={true}
  enableSignalsToggle={true}      // Affiche la checkbox "Signals"
  defaultSignalsEnabled={true}    // État initial
/>
```

## Notes Importantes

1. **Timezone**: Toutes les heures sont en Europe/Paris
2. **Charts**: Seul le chart 1H affiche les signaux de trading
3. **Build**: Toujours vérifier `npm run build` après modifications
4. **Database**: Ne pas modifier tradybull.db manuellement, utiliser les scripts
5. **shadcn/ui**: Utiliser `npx shadcn@latest add <component>` pour ajouter des composants

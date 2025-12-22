# TradyBull

Dashboard de trading pour les Nasdaq 100 Futures (NQ=F) avec exploration d'indicateurs techniques et backtesting de stratégies.

## Stack

- **Frontend**: Next.js 16, React 19, lightweight-charts v5, Tailwind CSS, shadcn/ui
- **Backend**: Python FastAPI, SQLite, yfinance

## Installation

### Prérequis

- Node.js 18+
- Python 3.10+

### 1. Frontend

```bash
npm install
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. Initialisation des données

```bash
cd backend
python bootstrap_backtest.py    # Télécharge l'historique (~730 jours, ~5 min)
python bootstrap_signals.py     # Calcule les signaux (~2 min)
```

## Démarrage

```bash
# Terminal 1 - Backend
cd backend && python main.py    # http://localhost:8000

# Terminal 2 - Frontend
npm run dev                     # http://localhost:3080
```

## Scripts utiles

```bash
# Recalculer les signaux d'une stratégie
python bootstrap_signals.py -s bollinger-sl1

# Forcer le recalcul de tous les signaux
python bootstrap_signals.py --force

# Importer des données CSV
python import_csv.py <fichier.csv>
```

## Documentation

Voir [CLAUDE.md](./CLAUDE.md) pour la documentation technique complète.

# Rapport Backend & Base de Données TradyBull

*Généré le 14 décembre 2025*

---

## 1. Architecture Backend

**Technologie**: FastAPI (Python) sur port 8000

**Fichiers**:
```
backend/
├── main.py                 # API principale + WebSocket
├── bootstrap_backtest.py   # Script d'initialisation historique
├── import_csv.py           # Import données CSV externes
└── tradybull.db            # Base SQLite
```

---

## 2. Structure de la Base de Données

**2 tables principales**:

### Table `candles` (Temps Réel)
```sql
CREATE TABLE candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interval TEXT NOT NULL,        -- '15m', '1h', '1d'
    timestamp INTEGER NOT NULL,    -- Unix timestamp
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    UNIQUE(interval, timestamp)
);
```

**Données actuelles**:
| Interval | Count | Début | Fin |
|----------|-------|-------|-----|
| 15m | 460 | 2025-12-08 | 2025-12-12 |
| 1h | 309 | 2025-11-24 | 2025-12-12 |
| 1d | 373 | 2024-06-24 | 2025-12-12 |

**Rétention automatique**:
- 15min: 6 jours
- 1h: 21 jours
- 1day: 540 jours (~18 mois)

### Table `backtest_candles` (Historique)
```sql
CREATE TABLE backtest_candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL DEFAULT 'NQ=F',
    timestamp INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER,
    source TEXT DEFAULT 'yfinance',
    UNIQUE(symbol, timestamp)
);
```

**Données actuelles**:
| Symbol | Count | Début | Fin |
|--------|-------|-------|-----|
| NQ=F | 13,731 | 2023-07-25 | 2025-12-12 |

**Pas de rétention** - les données historiques sont conservées indéfiniment.

---

## 3. Endpoints API

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Status du service |
| GET | `/api/nasdaq?interval=` | Données temps réel (15min/1h/1day) |
| GET | `/api/status` | Status marché + infos DB |
| GET | `/api/backtest/info` | Infos données historiques |
| GET | `/api/backtest/data` | Données historiques (filtrable) |
| WS | `/ws` | WebSocket temps réel |

---

## 4. Flux de Données

```
┌─────────────────────────────────────────────────────────────┐
│                    TEMPS RÉEL (WebSocket)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   yfinance ──(10s)──> candles table ──(broadcast)──> /ws    │
│                            │                                 │
│                            ▼                                 │
│                   1h aussi stocké dans                       │
│                   backtest_candles                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    HISTORIQUE (REST)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   backtest_candles ──> /api/backtest/data                   │
│         ▲                                                    │
│         │                                                    │
│   Sources:                                                   │
│   - bootstrap_backtest.py (yfinance, ~730 jours)            │
│   - import_csv.py (FirstRate Data, 15+ ans possible)        │
│   - Auto-alimenté par le flux temps réel 1h                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Scripts Utilitaires

### `bootstrap_backtest.py`
- Télécharge jusqu'à 730 jours d'historique 1h depuis yfinance
- Usage: `python bootstrap_backtest.py [--force]`

### `import_csv.py`
- Importe des fichiers CSV (format FirstRate Data)
- Permet d'avoir 15+ ans d'historique
- Usage: `python import_csv.py <fichier.csv> [--symbol NQ=F]`

---

## 6. Comportement du Backend

### Mode Normal (Lun-Ven)
- Fetch yfinance toutes les 10 secondes
- Broadcast aux clients WebSocket connectés
- Nettoyage automatique des données anciennes

### Mode Weekend (Sam-Dim)
- Pas de fetch (marché fermé)
- Broadcast status toutes les 60 secondes
- Données en cache conservées

---

## 7. Utilisation par le Frontend

| Dashboard | Source de données |
|-----------|-------------------|
| **Real Time** (TradingDashboard) | WebSocket `/ws` → 3 timeframes (15m, 1h, 1d) |
| **Historical** (HistoricalDashboard) | REST `/api/backtest/data` → 1h uniquement |

---

## 8. Résumé de l'état actuel

### Fonctionnel
- API temps réel avec WebSocket
- 3 timeframes pour le temps réel
- ~17 mois d'historique 1h pour backtesting
- Rétention automatique des données temps réel
- Scripts d'import pour données externes

### Supprimé récemment
- Table `signals` (supprimée lors du nettoyage)
- Endpoints `/api/signals` et `/api/signals/recalculate`

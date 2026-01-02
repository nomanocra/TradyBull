# Architecture du Système de Signaux TradyBull

## Vue d'ensemble

TradyBull utilise un système de calcul de signaux **incrémental et stateful** qui fonctionne en deux modes parallèles : **Backtest** et **Temps Réel**.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCES DE DONNÉES                           │
├─────────────────────────────────┬───────────────────────────────────┤
│         BACKTEST                │           TEMPS RÉEL              │
│   backtest_candles (1h)         │      candles (15m, 1h, 1d)        │
│   730 jours d'historique        │      21 jours max (rétention)     │
│   Chargé via bootstrap          │      Mis à jour toutes les 10s    │
└─────────────────────────────────┴───────────────────────────────────┘
                    │                              │
                    ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CALCUL DES SIGNAUX                               │
│                  signal_calculator.py                               │
│                                                                     │
│   Pour chaque stratégie :                                           │
│   1. Récupère l'état précédent (signal_processing_state)            │
│   2. Charge les bougies depuis last_processed_timestamp             │
│   3. Appelle strategy.calculate_signals(candles, initial_state)     │
│   4. Filtre les signaux déjà traités                                │
│   5. Sauvegarde les nouveaux signaux                                │
│   6. Met à jour l'état de traitement                                │
└─────────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STOCKAGE (SQLite)                              │
├─────────────────────────────────┬───────────────────────────────────┤
│         TABLE: signals          │   TABLE: signal_processing_state  │
│   - strategy_name               │   - strategy_name                 │
│   - signal_timestamp            │   - data_source (backtest/realtime)│
│   - type (buy/sell)             │   - last_processed_timestamp      │
│   - price                       │   - last_signal_state (JSON)      │
│   - metadata (JSON)             │                                   │
└─────────────────────────────────┴───────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DIFFUSION                                    │
├─────────────────────────────────┬───────────────────────────────────┤
│        WebSocket                │         Notifications             │
│   Broadcast toutes les 10s      │   Telegram / Desktop              │
│   Payload: candles + signals    │   Uniquement nouveaux signaux     │
└─────────────────────────────────┴───────────────────────────────────┘
```

---

## 1. Les Deux Modes : Backtest vs Temps Réel

### Le Point Clé

**C'est le MÊME code de stratégie** qui s'exécute dans les deux modes. La différence est :
- Les **données sources** (tables différentes)
- L'**état de traitement** (stocké séparément)
- Le **moment d'exécution** (manuel vs automatique)

### Tableau Comparatif

| Aspect | Backtest | Temps Réel |
|--------|----------|------------|
| **Table source** | `backtest_candles` | `candles` |
| **Intervalle** | 1h uniquement | 15m, 1h, 1d |
| **Rétention** | Illimitée (730 jours) | 21 jours max |
| **Déclenchement** | Manuel (`bootstrap_signals.py`) | Auto (toutes les 10s) |
| **État stocké** | `data_source='backtest'` | `data_source='realtime'` |

### Conséquence Importante

Quand tu modifies le code d'une stratégie :
1. Le **temps réel** utilisera le nouveau code au prochain cycle (10s)
2. Le **backtest** gardera les anciens signaux jusqu'à recalcul manuel

---

## 2. Le Calcul Incrémental

### Pourquoi Incrémental ?

Recalculer 730 jours × 24 heures × 31 stratégies à chaque mise à jour serait trop lent. Le système ne traite que les **nouvelles bougies**.

### Comment ça Marche

```python
# signal_calculator.py - calculate_signals_incremental()

1. Récupérer l'état précédent
   ├─ last_processed_timestamp = dernière bougie traitée
   └─ last_signal_state = état de la stratégie (ex: position ouverte)

2. Charger les bougies nécessaires
   ├─ Lookback: 2 × required_lookback heures AVANT last_timestamp
   └─ Nouvelles: toutes les bougies APRÈS last_timestamp

3. Exécuter la stratégie
   └─ signals, final_state = strategy.calculate_signals(candles, initial_state)

4. Filtrer les signaux déjà traités
   └─ signals = [s for s if s.timestamp > last_processed_timestamp]

5. Sauvegarder
   ├─ INSERT OR IGNORE INTO signals (évite les doublons)
   └─ UPDATE signal_processing_state
```

### L'État de la Stratégie (`last_signal_state`)

Chaque stratégie peut stocker un état JSON entre les calculs :

```python
# Exemple pour daily-sl1-trend
{
    "open_position": {
        "buy_price": 25626.5,
        "buy_time": 1767333600,
        "date": "2026-01-02"
    }
}

# Ou si pas de position ouverte
{
    "open_position": null
}
```

**C'est CRITIQUE** : Si cet état est perdu ou corrompu, la stratégie "oublie" qu'elle a une position ouverte.

---

## 3. Schéma de la Base de Données

### Table `signals`

```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    strategy_name TEXT NOT NULL,      -- ex: "daily-sl1-trend"
    symbol TEXT DEFAULT 'NQ=F',
    signal_timestamp INTEGER,          -- Quand afficher le marker
    trigger_timestamp INTEGER,         -- Quand la condition s'est produite
    type TEXT CHECK(IN 'buy','sell'),
    price REAL,                        -- Prix d'entrée/sortie
    label TEXT,                        -- "Buy", "SL", "Trend", "Close"
    metadata TEXT,                     -- JSON avec détails

    UNIQUE(strategy_name, symbol, signal_timestamp, type)
);
```

### Table `signal_processing_state`

```sql
CREATE TABLE signal_processing_state (
    strategy_name TEXT,
    symbol TEXT DEFAULT 'NQ=F',
    data_source TEXT,                  -- 'backtest' ou 'realtime'
    last_processed_timestamp INTEGER,  -- Dernière bougie traitée
    last_signal_state TEXT,            -- État JSON de la stratégie

    UNIQUE(strategy_name, symbol, data_source)
);
```

**Point Important** : Chaque stratégie a DEUX entrées :
- Une pour `data_source='backtest'`
- Une pour `data_source='realtime'`

---

## 4. Flux de Données Temps Réel

```
Toutes les 10 secondes (main.py):

fetch_all_intervals()
│
├─1─ Télécharge les nouvelles bougies (yfinance)
│    └─ Stocke dans `candles` + `backtest_candles` (1h)
│
├─2─ calculate_all_strategies(conn, 'NQ=F', 'realtime', 'candles')
│    │
│    └─ Pour chaque stratégie (31+):
│        ├─ calculate_signals_incremental()
│        ├─ Si nouveaux signaux:
│        │   ├─ Print "[strategy] X new signal(s)"
│        │   └─ send_signal_notification() → Telegram
│        └─ Retourne (count, signals)
│
├─3─ broadcast_to_clients()
│    └─ WebSocket: envoie candles + signaux à tous les clients
│
└─ Attendre 10 secondes, recommencer
```

---

## 5. Flux de Données Backtest

```
Manuel (bootstrap_signals.py):

python bootstrap_signals.py [--force] [--strategy NAME]
│
├─1─ Si --force: supprime tous les signaux existants
│
├─2─ Pour chaque stratégie (ou une seule si --strategy):
│    │
│    └─ calculate_signals_incremental(conn, strategy, 'NQ=F', 'backtest', 'backtest_candles')
│        ├─ Récupère l'état backtest
│        ├─ Charge TOUTES les bougies backtest
│        ├─ Calcule les signaux
│        └─ Sauvegarde
│
└─3─ Affiche le résumé
```

---

## 6. Pourquoi les Signaux Peuvent Différer

### Cas 1 : Code Modifié mais Backtest Non Recalculé

```
Situation:
- Tu modifies daily_sl1_trend.py (ex: LOW < MA200 au lieu de CLOSE < MA200)
- Le temps réel utilise le nouveau code
- Le backtest garde les anciens signaux en base

Solution:
python bootstrap_signals.py --force --strategy daily-sl1-trend
```

### Cas 2 : État Corrompu ou Désynchronisé

```
Situation:
- Un BUY est généré en temps réel
- Crash/redémarrage avant que l'état soit sauvegardé
- Le système "oublie" la position ouverte
- Pas de SELL généré

Solution:
- Vérifier signal_processing_state
- Recalculer si nécessaire
```

### Cas 3 : Données Manquantes

```
Situation:
- Table `candles` n'a que 21 jours (rétention)
- Table `backtest_candles` a 730 jours
- Les signaux historiques ne matchent pas les signaux récents

Solution:
- C'est normal, les deux sources ont des données différentes
```

### Cas 4 : Horaires de Marché Dynamiques

```
Situation:
- Le marché ferme à 22h normalement
- Certains jours (fériés), il ferme plus tôt
- market_hours.py calcule dynamiquement l'heure de fermeture

Solution:
- is_last_candle_of_day() vérifie le calendrier CME
```

---

## 7. Système de Notifications

### Configuration par Stratégie

```sql
-- Table notification_settings
strategy_name: "daily-sl1-trend"
enabled: 1
telegram_enabled: 1
telegram_bot_token: "xxx"
telegram_chat_id: "xxx"
notify_buy: 1
notify_sell: 1
time_start: "00:00"
time_end: "23:59"
```

### Flux de Notification

```
Nouveau signal généré
│
├─ Vérifier notification_settings
│   ├─ enabled = 1 ?
│   ├─ notify_sell = 1 ? (si c'est un SELL)
│   └─ Dans la fenêtre horaire ?
│
├─ Si tout OK:
│   └─ send_telegram_message()
│
└─ Le signal est DÉJÀ sauvegardé en base
   (la notification est indépendante)
```

**Important** : Un échec de notification n'empêche PAS le signal d'être enregistré.

---

## 8. Commandes Utiles

### Voir l'état de traitement

```bash
sqlite3 backend/tradybull.db "
SELECT
    strategy_name,
    data_source,
    datetime(last_processed_timestamp, 'unixepoch', 'localtime') as last_processed,
    last_signal_state
FROM signal_processing_state
WHERE strategy_name = 'daily-sl1-trend'
"
```

### Voir les signaux récents

```bash
sqlite3 backend/tradybull.db "
SELECT
    datetime(signal_timestamp, 'unixepoch', 'localtime') as time,
    type, price, label
FROM signals
WHERE strategy_name = 'daily-sl1-trend'
ORDER BY signal_timestamp DESC
LIMIT 10
"
```

### Recalculer une stratégie

```bash
cd backend
python bootstrap_signals.py --force --strategy daily-sl1-trend
```

### Recalculer TOUTES les stratégies

```bash
cd backend
python bootstrap_signals.py --force
```

### Redémarrer le backend (pour charger le nouveau code)

```bash
# Arrêter le processus actuel (Ctrl+C ou kill)
cd backend
python main.py
```

---

## 9. Résumé

| Question | Réponse |
|----------|---------|
| Même algo backtest/realtime ? | **OUI**, même code Python |
| Même données ? | **NON**, tables différentes |
| Même état ? | **NON**, état séparé par data_source |
| Quand recalculer backtest ? | Après modification du code stratégie |
| Quand les notifications partent ? | Uniquement pour les NOUVEAUX signaux temps réel |
| Comment forcer un recalcul ? | `python bootstrap_signals.py --force` |

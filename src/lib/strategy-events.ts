/**
 * Simple event emitter for strategy changes (archive/unarchive)
 * Used to synchronize sidebar and overview table
 */

type Listener = () => void;

class StrategyEventEmitter {
  private listeners: Set<Listener> = new Set();

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(): void {
    this.listeners.forEach((listener) => listener());
  }
}

export const strategyEvents = new StrategyEventEmitter();

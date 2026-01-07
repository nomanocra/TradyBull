/**
 * Event emitter for strategy changes (archive/unarchive/create/delete)
 * Used to synchronize sidebar and overview table
 */

export type StrategyEventType = 'archive' | 'unarchive' | 'create' | 'delete';

export interface StrategyEvent {
  type: StrategyEventType;
  strategyName: string;
}

type Listener = (event: StrategyEvent) => void;

class StrategyEventEmitter {
  private listeners: Set<Listener> = new Set();

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(event: StrategyEvent): void {
    this.listeners.forEach((listener) => listener(event));
  }
}

export const strategyEvents = new StrategyEventEmitter();

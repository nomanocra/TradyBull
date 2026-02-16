/**
 * Event emitter for bot changes (create/delete)
 * Used to synchronize sidebar bot icons without polling
 */

type Listener = () => void;

class BotEventEmitter {
  private listeners: Set<Listener> = new Set();

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(): void {
    this.listeners.forEach((listener) => listener());
  }
}

export const botEvents = new BotEventEmitter();

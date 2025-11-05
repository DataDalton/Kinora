/**
 * Generates and plays notification sounds using Web Audio API
 */

type NotificationType = 'success' | 'error' | 'info' | 'warning';

class AudioNotification {
  private audioContext: AudioContext | null = null;

  private getAudioContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    return this.audioContext;
  }

  /**
   * Plays a notification sound based on type
   */
  play(type: NotificationType): void {
    try {
      const context = this.getAudioContext();

      // Create oscillator and gain nodes
      const oscillator = context.createOscillator();
      const gainNode = context.createGain();

      // Connect nodes
      oscillator.connect(gainNode);
      gainNode.connect(context.destination);

      // Set volume (0 to 1)
      gainNode.gain.setValueAtTime(0.1, context.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.3);

      // Configure sound based on notification type
      switch (type) {
        case 'success':
          // Two ascending tones for success
          oscillator.frequency.setValueAtTime(523.25, context.currentTime); // C5
          oscillator.frequency.setValueAtTime(659.25, context.currentTime + 0.1); // E5
          oscillator.type = 'sine';
          oscillator.start(context.currentTime);
          oscillator.stop(context.currentTime + 0.2);
          break;

        case 'error':
          // Low descending tone for error
          oscillator.frequency.setValueAtTime(329.63, context.currentTime); // E4
          oscillator.frequency.exponentialRampToValueAtTime(220.00, context.currentTime + 0.2); // A3
          oscillator.type = 'square';
          oscillator.start(context.currentTime);
          oscillator.stop(context.currentTime + 0.25);
          break;

        case 'warning':
          // Two quick same tones for warning
          oscillator.frequency.setValueAtTime(440.00, context.currentTime); // A4
          oscillator.type = 'triangle';
          oscillator.start(context.currentTime);
          oscillator.stop(context.currentTime + 0.15);

          // Second beep
          setTimeout(() => {
            const osc2 = context.createOscillator();
            const gain2 = context.createGain();
            osc2.connect(gain2);
            gain2.connect(context.destination);
            gain2.gain.setValueAtTime(0.1, context.currentTime);
            gain2.gain.exponentialRampToValueAtTime(0.01, context.currentTime + 0.15);
            osc2.frequency.setValueAtTime(440.00, context.currentTime);
            osc2.type = 'triangle';
            osc2.start(context.currentTime);
            osc2.stop(context.currentTime + 0.15);
          }, 150);
          break;

        case 'info':
          // Single neutral tone for info
          oscillator.frequency.setValueAtTime(523.25, context.currentTime); // C5
          oscillator.type = 'sine';
          oscillator.start(context.currentTime);
          oscillator.stop(context.currentTime + 0.15);
          break;
      }
    } catch (error) {
      // Silently fail if audio is not supported or blocked
      console.warn('Audio notification failed:', error);
    }
  }
}

export const audioNotification = new AudioNotification();

// Tactical audio synthesis using Web Audio API

class SoundFX {
  private ctx: AudioContext | null = null;
  public enabled: boolean = true;
  private motorOsc: OscillatorNode | null = null;
  private motorGain: GainNode | null = null;

  private init() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playClick(type: 'tactile' | 'light' | 'shutter' | 'switch' = 'tactile') {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;

      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      if (type === 'tactile') {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(110, now + 0.04);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now);
        osc.stop(now + 0.05);
      } else if (type === 'light') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(1320, now + 0.06);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now);
        osc.stop(now + 0.07);
      } else if (type === 'shutter') {
        // Camera click
        osc.type = 'square';
        osc.frequency.setValueAtTime(1200, now);
        osc.frequency.exponentialRampToValueAtTime(300, now + 0.08);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now);
        osc.stop(now + 0.09);
      } else if (type === 'switch') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(600, now);
        osc.frequency.exponentialRampToValueAtTime(400, now + 0.05);
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now);
        osc.stop(now + 0.05);
      }
    } catch {
      // Audio not permitted yet or not supported
    }
  }

  playStopAlert() {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.setValueAtTime(180, now + 0.1);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.26);
    } catch {
      // Ignored
    }
  }

  startMotor(speedPct: number) {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;

      if (!this.motorOsc) {
        this.motorOsc = this.ctx.createOscillator();
        this.motorGain = this.ctx.createGain();
        this.motorOsc.type = 'triangle';
        this.motorOsc.frequency.setValueAtTime(65 + speedPct * 0.8, this.ctx.currentTime);
        this.motorGain.gain.setValueAtTime(0.04 + (speedPct / 100) * 0.08, this.ctx.currentTime);
        this.motorOsc.connect(this.motorGain);
        this.motorGain.connect(this.ctx.destination);
        this.motorOsc.start();
      } else if (this.motorGain) {
        this.motorOsc.frequency.setTargetAtTime(65 + speedPct * 0.8, this.ctx.currentTime, 0.05);
        this.motorGain.gain.setTargetAtTime(0.04 + (speedPct / 100) * 0.08, this.ctx.currentTime, 0.05);
      }
    } catch {
      // Ignored
    }
  }

  stopMotor() {
    try {
      if (this.motorOsc && this.motorGain && this.ctx) {
        this.motorGain.gain.setTargetAtTime(0.0001, this.ctx.currentTime, 0.05);
        setTimeout(() => {
          if (this.motorOsc) {
            try {
              this.motorOsc.stop();
              this.motorOsc.disconnect();
            } catch {
              /* ignore error when stopping oscillator */
            }
            this.motorOsc = null;
            this.motorGain = null;
          }
        }, 80);
      }
    } catch {
      // Ignored
    }
  }
}

export const sounds = new SoundFX();

export const playSound = (name: 'click' | 'snapshot' | 'stop' | 'switch') => {
  if (name === 'click' || name === 'switch') sounds.playClick('tactile');
  else if (name === 'snapshot') sounds.playClick('shutter');
  else if (name === 'stop') sounds.playStopAlert();
};

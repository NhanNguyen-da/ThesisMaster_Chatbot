// Center column: chat card with the live message list and the composer.
import {
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  effect,
  inject,
  viewChild,
} from '@angular/core';
import { ChatSession } from './chat-session';

@Component({
  selector: 'app-chat-center',
  templateUrl: './chat-center.html',
  // The host tag must not break the flex layout of its parent.
  host: { style: 'display: contents' },
})
export class ChatCenter {
  private readonly session = inject(ChatSession);
  private readonly injector = inject(Injector);
  private readonly messageBox = viewChild.required<ElementRef<HTMLElement>>('msgs');

  readonly messages = this.session.messages;
  readonly chips = this.session.chips;
  readonly isSending = this.session.isSending;
  readonly isEnded = this.session.isEnded;

  constructor() {
    // Scroll to the newest message whenever the list changes.
    effect(() => {
      this.session.messages();
      this.isSending();
      afterNextRender(() => this.scrollToBottom(), { injector: this.injector });
    });
  }

  async send(input: HTMLInputElement): Promise<void> {
    // Send the trimmed input; restore it if the send fails, then refocus.
    const text = input.value.trim();
    if (!text || this.isSending()) {
      return;
    }
    input.value = '';
    const sent = await this.session.sendMessage(text);
    if (!sent) {
      input.value = text;
    }
    afterNextRender(() => input.focus(), { injector: this.injector });
  }

  onEnter(event: Event, input: HTMLInputElement): void {
    // Send on Enter, but not while an input method is still composing text.
    if ((event as KeyboardEvent).isComposing) {
      return;
    }
    this.send(input);
  }

  formatTime(isoText: string): string {
    // Format a timestamp as local 24-hour HH:mm.
    const date = new Date(isoText);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  private scrollToBottom(): void {
    // Move the message list scroll position to its bottom.
    const list = this.messageBox().nativeElement;
    list.scrollTop = list.scrollHeight;
  }
}

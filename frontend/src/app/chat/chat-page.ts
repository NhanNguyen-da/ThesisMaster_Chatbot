// Whole chat screen: sidebar, header and the three columns.
import { Component, inject } from '@angular/core';
import { ChatLeft } from './chat-left';
import { ChatCenter } from './chat-center';
import { ChatRight } from './chat-right';
import { ChatSession } from './chat-session';

@Component({
  selector: 'app-chat-page',
  imports: [ChatLeft, ChatCenter, ChatRight],
  templateUrl: './chat-page.html',
  // The host tag must not break the flex layout of its parent.
  host: { style: 'display: contents' },
})
export class ChatPage {
  private readonly session = inject(ChatSession);

  constructor() {
    // Start a backend session when the page opens.
    this.session.startSession();
  }

  async startNew(): Promise<void> {
    // End the current session, then reload so a new one is created.
    await this.session.abandonSession();
    window.location.reload();
  }
}

// Root component: only shows the chat screen.
import { Component } from '@angular/core';
import { ChatPage } from './chat/chat-page';

@Component({
  selector: 'app-root',
  imports: [ChatPage],
  template: '<app-chat-page />',
})
export class App {}

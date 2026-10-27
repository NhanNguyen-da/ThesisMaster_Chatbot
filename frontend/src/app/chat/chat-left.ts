// Left column: session card and processing steps, filled from the session state.
import { Component, computed, inject } from '@angular/core';
import { ChatSession, RESULT_LABELS } from './chat-session';

@Component({
  selector: 'app-chat-left',
  templateUrl: './chat-left.html',
  // The host tag must not break the flex layout of its parent.
  host: { style: 'display: contents' },
})
export class ChatLeft {
  private readonly session = inject(ChatSession);

  readonly sessionId = this.session.sessionId;
  readonly state = this.session.state;
  readonly resultLabel = this.session.resultLabel;
  readonly isSending = this.session.isSending;
  readonly isEnded = this.session.isEnded;
  readonly resultLabels = RESULT_LABELS;
  // Current step of the flow: 4 after the session ends, 2 while sending, otherwise 1.
  readonly currentStep = computed<number>(() => (this.isEnded() ? 4 : this.isSending() ? 2 : 1));

  receivedText(): string {
    // Detail line of pipeline step 1.
    const round = this.state().round;
    return round >= 1 ? `Đã nhận câu trả lời lượt ${round}` : 'Chờ câu trả lời lượt 1';
  }

  conclusionText(): string {
    // Detail line of pipeline step 3.
    const label = this.resultLabel();
    return label ? `Kết luận: ${label}` : 'Chưa kết luận';
  }

  extractionText(): string {
    // Detail line of pipeline step 2.
    const run = this.state().last_run;
    if (run === null) {
      return 'Chưa có đầu vào';
    }
    return run.valid ? `JSON hợp lệ · ${run.new_keys.length} trường mới` : 'JSON không hợp lệ';
  }
}

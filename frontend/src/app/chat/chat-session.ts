// Chat session service: holds session state and calls the Flask backend.
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

const API_URL = 'http://localhost:8000';
const PENDING_ID = -1;

// The three possible final results: emergency, clinical visit, handover to staff.
export const RESULT_LABELS = ['Cấp cứu', 'Khám lâm sàng', 'Chuyển nhân viên hỗ trợ'] as const;

function withoutPending(list: ChatMessage[]): ChatMessage[] {
  // Remove the temporary patient bubble from a message list.
  return list.filter((message) => message.id !== PENDING_ID);
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'chatbot';
  order: number;
  round: number;
  text: string;
  created_at: string;
}

export interface OpqrstValues {
  onset: string | null;
  provocation_palliation: string | null;
  quality: string | null;
  region_radiation: string | null;
  severity: string | null;
  time_course: string | null;
}

export interface MatchedSymptom {
  phrase: string;
  standard_name: string | null;
  status: boolean;
}

export interface LastRun {
  valid: boolean;
  off_topic: boolean | null;
  processing_ms: number;
  new_keys: string[];
}

export interface SessionState {
  round: number;
  opqrst: OpqrstValues;
  filled_count: number;
  completeness_percent: number;
  symptoms: MatchedSymptom[];
  last_run: LastRun | null;
  result: { end_reason_id: number | null; outcome_id: number | null; rule_id: number | null; rule_name: string | null };
  off_topic_count: number;
}

// Small status line shown under a patient bubble (browser only).
export interface MessageChip {
  text: string;
  warn: boolean;
}

interface SessionResponse {
  session_id: number;
  messages: ChatMessage[];
  ended?: boolean;
  state?: SessionState | null;
}

const EMPTY_STATE: SessionState = {
  round: 0,
  opqrst: {
    onset: null,
    provocation_palliation: null,
    quality: null,
    region_radiation: null,
    severity: null,
    time_course: null,
  },
  filled_count: 0,
  completeness_percent: 0,
  symptoms: [],
  last_run: null,
  result: { end_reason_id: null, outcome_id: null, rule_id: null, rule_name: null },
  off_topic_count: 0,
};

const KEY_LETTERS: Record<string, string> = {
  onset: 'O',
  provocation_palliation: 'P',
  quality: 'Q',
  region_radiation: 'R',
  severity: 'S',
  time_course: 'T',
};

function buildChip(run: LastRun): MessageChip {
  // Turn the newest extraction run into the chip text and kind.
  const seconds = (run.processing_ms / 1000).toFixed(1).replace('.', ',');
  if (!run.valid) {
    return { text: `Phản hồi của LLM không hợp lệ · ${seconds} giây`, warn: true };
  }
  if (run.off_topic) {
    return { text: `Tin nhắn không liên quan · ${seconds} giây`, warn: true };
  }
  if (run.new_keys.length === 0) {
    return { text: `LLM không tìm thấy dữ kiện mới · ${seconds} giây`, warn: false };
  }
  const letters = run.new_keys.map((key) => KEY_LETTERS[key]).join(', ');
  return { text: `LLM đã cập nhật ${run.new_keys.length} dữ kiện (${letters}) · ${seconds} giây`, warn: false };
}

@Injectable({ providedIn: 'root' })
export class ChatSession {
  private readonly http = inject(HttpClient);

  readonly sessionId = signal<number | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly isSending = signal(false);
  readonly isEnded = signal(false);
  readonly state = signal<SessionState>(EMPTY_STATE);
  readonly chips = signal<Record<number, MessageChip>>({});
  // Final result text of the session; empty while it has no result.
  readonly resultLabel = computed(() => {
    const { end_reason_id, outcome_id } = this.state().result;
    if (outcome_id === 1) {
      return RESULT_LABELS[0];
    }
    if (outcome_id === 2) {
      return RESULT_LABELS[1];
    }
    return end_reason_id !== null ? RESULT_LABELS[2] : '';
  });

  async startSession(): Promise<void> {
    // Create a new backend session and load its greeting.
    this.isEnded.set(false);
    this.state.set(EMPTY_STATE);
    this.chips.set({});
    try {
      const response = await firstValueFrom(
        this.http.post<SessionResponse>(`${API_URL}/sessions`, {}),
      );
      this.sessionId.set(response.session_id);
      this.messages.set(response.messages);
      this.state.set(response.state ?? EMPTY_STATE);
    } catch (error) {
      this.logError('startSession', error);
    }
  }

  async sendMessage(text: string): Promise<boolean> {
    // Send the patient text and append the saved messages; returns true on success.
    const id = this.sessionId();
    if (id === null) {
      return false;
    }
    this.isSending.set(true);
    this.messages.update((list) => [...list, this.pendingMessage(text)]);
    try {
      const response = await firstValueFrom(
        this.http.post<SessionResponse>(`${API_URL}/sessions/${id}/messages`, { text }),
      );
      this.messages.update((list) => [...withoutPending(list), ...response.messages]);
      this.isEnded.set(response.ended === true);
      this.showResult(response);
      return true;
    } catch (error) {
      this.messages.update((list) => withoutPending(list));
      this.logError('sendMessage', error);
      return false;
    } finally {
      this.isSending.set(false);
    }
  }

  async abandonSession(): Promise<void> {
    // End the current session on the backend with reason "bỏ phiên".
    if (this.isEnded()) {
      return;
    }
    const id = this.sessionId();
    if (id === null) {
      return;
    }
    try {
      await firstValueFrom(
        this.http.post(`${API_URL}/sessions/${id}/end`, { end_reason_id: 2, outcome_id: null }),
      );
    } catch (error) {
      this.logError('abandonSession', error);
    }
  }

  private showResult(response: SessionResponse): void {
    // Store the new state and the chip of the patient message; skip when the state is missing.
    const state = response.state;
    const patient = response.messages.find((message) => message.role === 'user');
    if (!state) {
      return;
    }
    this.state.set(state);
    if (patient && state.last_run) {
      const chip = buildChip(state.last_run);
      this.chips.update((map) => ({ ...map, [patient.id]: chip }));
    }
  }

  private pendingMessage(text: string): ChatMessage {
    // Build the temporary patient bubble shown while the backend works.
    return { id: PENDING_ID, role: 'user', order: 0, round: 0, text, created_at: new Date().toISOString() };
  }

  private logError(action: string, error: unknown): void {
    // Print the status and body of an HTTP error to the console.
    if (error instanceof HttpErrorResponse) {
      console.error(`${action} failed`, error.status, error.error);
    } else {
      console.error(`${action} failed`, error);
    }
  }
}

// Right column: rule engine and conditions (static), OPQRST fields and matched symptoms from the state.
import { Component, inject } from '@angular/core';
import { ChatSession, MatchedSymptom, OpqrstValues } from './chat-session';

interface FieldTile {
  key: keyof OpqrstValues;
  letter: string;
  label: string;
}

@Component({
  selector: 'app-chat-right',
  templateUrl: './chat-right.html',
  // The host tag must not break the flex layout of its parent.
  host: { style: 'display: contents' },
})
export class ChatRight {
  private readonly session = inject(ChatSession);

  readonly state = this.session.state;
  readonly isEnded = this.session.isEnded;
  readonly tiles: FieldTile[] = [
    { key: 'onset', letter: 'O', label: 'Khởi phát' },
    { key: 'provocation_palliation', letter: 'P', label: 'Tăng / giảm' },
    { key: 'quality', letter: 'Q', label: 'Tính chất' },
    { key: 'region_radiation', letter: 'R', label: 'Vùng / lan' },
    { key: 'severity', letter: 'S', label: 'Mức độ' },
    { key: 'time_course', letter: 'T', label: 'Diễn tiến' },
  ];

  resultTitle(): string {
    // Panel title for the final result, or a non-breaking space while the session runs.
    return this.session.resultLabel() || '\u00a0';
  }

  missingLabels(): string {
    // Labels of the OPQRST fields that are still empty, in order.
    const values = this.state().opqrst;
    return this.tiles.filter((tile) => values[tile.key] === null).map((tile) => tile.label).join(', ');
  }

  symptomText(symptom: MatchedSymptom): string {
    // Chip text for one matched or unmatched symptom.
    if (symptom.standard_name !== null) {
      return symptom.status ? symptom.standard_name : `Không: ${symptom.standard_name}`;
    }
    return symptom.status ? `Chưa khớp: ${symptom.phrase}` : `Không · chưa khớp: ${symptom.phrase}`;
  }
}

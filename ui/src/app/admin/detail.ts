import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { Api } from '../api';
import { AdminQuestionRow, CandidateDetail } from '../models';

type Filter = 'all' | 'differs' | 'unanswered';

@Component({
  selector: 'qm-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './detail.html',
  styleUrl: './detail.css',
})
export class DetailComponent {
  private api = inject(Api);
  private route = inject(ActivatedRoute);

  id = Number(this.route.snapshot.paramMap.get('id'));
  data = signal<CandidateDetail | null>(null);
  filter = signal<Filter>('all');
  running = signal(false);
  note = '';

  constructor() { this.load(); }

  private load() {
    this.api.candidate(this.id).subscribe(d => this.data.set(d));
  }

  rows = computed<AdminQuestionRow[]>(() => {
    const all = this.data()?.questions ?? [];
    switch (this.filter()) {
      case 'differs':
        return all.filter(q => Object.values(q.comparison ?? {})
          .some(c => c.verdict === 'differs' || c.verdict === 'partial'));
      case 'unanswered':
        return all.filter(q => !this.hasAnswer(q));
      default:
        return all;
    }
  });

  counts = computed(() => {
    const all = this.data()?.questions ?? [];
    return {
      total: all.length,
      answered: all.filter(q => this.hasAnswer(q)).length,
      differs: all.filter(q => Object.values(q.comparison ?? {})
        .some(c => c.verdict === 'differs' || c.verdict === 'partial')).length,
    };
  });

  hasAnswer(q: AdminQuestionRow): boolean {
    const a = q.answer;
    if (!a) return false;
    return q.type === 'mc'
      ? !!(a.choices && a.choices.length)
      : a.value !== null && a.value !== undefined && a.value.trim() !== '';
  }

  parts(q: AdminQuestionRow) {
    return Object.entries(q.comparison ?? {})
      .map(([part, c]) => ({ part, ...c }))
      .sort((a, b) => (a.part === 'answer' ? -1 : 1));
  }

  runComparison() {
    this.running.set(true);
    this.api.runComparison(this.id).subscribe(() => {
      // The run is a background task; give it room, then reload.
      setTimeout(() => { this.load(); this.running.set(false); }, 8000);
    });
  }

  addNote() {
    const body = this.note.trim();
    if (!body) return;
    this.api.addNote(this.id, body).subscribe(() => { this.note = ''; this.load(); });
  }
}

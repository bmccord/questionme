import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { Subscription, interval, switchMap } from 'rxjs';

import { Api } from '../api';
import { AdminQuestionRow, CandidateDetail, ComparisonStatus } from '../models';

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
  status = signal<ComparisonStatus | null>(null);
  note = '';

  // Which question's baseline is open for editing, and the working copy.
  editing = signal<string | null>(null);
  draftBaseline = '';
  draftChoices: string[] = [];
  draftComment = '';
  savingBaseline = signal(false);
  busyQuestion = signal<string | null>(null);

  private poll?: Subscription;

  running = computed(() => this.status()?.running ?? false);
  progress = computed(() => {
    const s = this.status();
    if (!s || !s.running || !s.total) return null;
    return { done: s.done, total: s.total,
             pct: Math.round((s.done / s.total) * 100) };
  });

  constructor() {
    this.load();
    // If a run is already in flight when the page opens - started elsewhere,
    // or the tab was reloaded mid-run - pick it up rather than showing a
    // stale page.
    this.api.comparisonStatus(this.id).subscribe(s => {
      this.status.set(s);
      if (s.running) this.watch();
    });
  }

  ngOnDestroy() { this.poll?.unsubscribe(); }

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

  /** Poll while a run is in flight, then reload once it settles.
   *
   *  Replaces a flat 8-second wait, which was never long enough for a full
   *  candidate and left the page looking half-broken. Rows are written per
   *  question, so reloading as we go shows real progress rather than a
   *  spinner that hides it. */
  private watch() {
    this.poll?.unsubscribe();
    let sawRunning = false;
    this.poll = interval(1500).pipe(
      switchMap(() => this.api.comparisonStatus(this.id)),
    ).subscribe(s => {
      this.status.set(s);
      if (s.running) {
        sawRunning = true;
        this.load();                       // fill in as results land
      } else if (sawRunning) {
        this.poll?.unsubscribe();
        this.load();
      }
    });
  }

  runComparison() {
    this.status.set({ running: true, done: 0, total: 0, rows: 0, questions: 0 });
    this.api.runComparison(this.id).subscribe(() => this.watch());
  }

  recompareOne(q: AdminQuestionRow) {
    this.busyQuestion.set(q.id);
    this.api.runOneComparison(this.id, q.id).subscribe(() => {
      // One question is quick; poll briefly rather than reloading blind.
      setTimeout(() => {
        this.load();
        this.busyQuestion.set(null);
      }, 4000);
    });
  }

  startEdit(q: AdminQuestionRow) {
    this.editing.set(q.id);
    this.draftBaseline = q.baseline ?? '';
    this.draftChoices = [...(q.baseline_choices ?? [])];
    this.draftComment = q.comment_baseline ?? '';
  }

  cancelEdit() { this.editing.set(null); }

  toggleBaselineChoice(q: AdminQuestionRow, option: string) {
    if (q.multi_select) {
      this.draftChoices = this.draftChoices.includes(option)
        ? this.draftChoices.filter(o => o !== option)
        : [...this.draftChoices, option];
    } else {
      this.draftChoices = this.draftChoices.includes(option) ? [] : [option];
    }
  }

  saveBaseline(q: AdminQuestionRow) {
    this.savingBaseline.set(true);
    const body = q.type === 'mc'
      ? { baseline_choices: this.draftChoices, comment_baseline: this.draftComment }
      : { baseline: this.draftBaseline };
    this.api.editQuestion(q.id, body).subscribe({
      next: () => {
        this.savingBaseline.set(false);
        this.editing.set(null);
        this.load();
      },
      error: () => this.savingBaseline.set(false),
    });
  }

  addNote() {
    const body = this.note.trim();
    if (!body) return;
    this.api.addNote(this.id, body).subscribe(() => { this.note = ''; this.load(); });
  }
}

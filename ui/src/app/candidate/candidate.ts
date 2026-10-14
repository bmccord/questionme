import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { Subject, debounceTime, groupBy, mergeMap } from 'rxjs';

import { Api } from '../api';
import { Answer, CandidateView, Question, SubmitPreview } from '../models';

interface Pending { questionId: string; body: Partial<Answer>; }

@Component({
  selector: 'qm-candidate',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './candidate.html',
  styleUrl: './candidate.css',
})
export class CandidateComponent {
  private api = inject(Api);
  private route = inject(ActivatedRoute);

  token = this.route.snapshot.paramMap.get('token')!;
  view = signal<CandidateView | null>(null);
  error = signal<string | null>(null);
  saving = signal(0);
  current = signal(0);                       // index into questions
  showList = signal(false);
  // 'intro' until they choose to begin. Returning candidates skip it, but it
  // stays reachable from the header - the instructions explain that
  // submitting is final, which is the one thing they must not miss.
  stage = signal<'intro' | 'questions'>('intro');
  preview = signal<SubmitPreview | null>(null);
  submitting = signal(false);

  // Local edit buffer, so typing is never blocked on the network.
  draft = signal<Record<string, Answer>>({});

  private saves = new Subject<Pending>();

  constructor() {
    // One in-flight save per question, latest wins. A fast typist on question
    // 7 must never have their work reordered behind question 6's request.
    this.saves.pipe(
      groupBy(p => p.questionId),
      mergeMap(group => group.pipe(debounceTime(600))),
    ).subscribe(p => {
      this.saving.update(n => n + 1);
      this.api.saveAnswer(this.token, p.questionId, p.body).subscribe({
        next: () => this.saving.update(n => n - 1),
        error: err => {
          this.saving.update(n => n - 1);
          this.error.set(err?.error?.detail ?? 'Could not save that answer.');
        },
      });
    });

    this.api.view(this.token).subscribe({
      next: v => {
        this.view.set(v);
        this.draft.set({ ...v.answers });
        // Someone coming back to work they have already started, or reading a
        // submitted questionnaire, does not need the instructions again.
        if (v.read_only || Object.keys(v.answers).length > 0) {
          this.stage.set('questions');
        }
      },
      error: () => this.error.set('This link is not valid.'),
    });
  }

  questions = computed(() => this.view()?.questions ?? []);
  readOnly = computed(() => this.view()?.read_only ?? false);
  question = computed<Question | undefined>(() => this.questions()[this.current()]);

  answerFor(id: string): Answer {
    return this.draft()[id] ?? { question_id: id, value: null, choices: null, comment: null };
  }

  isAnswered(q: Question): boolean {
    const a = this.draft()[q.id];
    if (!a) return false;
    return q.type === 'mc'
      ? !!(a.choices && a.choices.length)
      : a.value !== null && a.value !== undefined && a.value.trim() !== '';
  }

  answeredCount = computed(() => this.questions().filter(q => this.isAnswered(q)).length);

  /** The question a cross-reference points at, with whatever they said. */
  referenced = computed(() => {
    const q = this.question();
    if (!q?.references?.length) return [];
    const byId = new Map(this.questions().map(x => [x.id, x]));
    return q.references
      .map(id => byId.get(id))
      .filter((x): x is Question => !!x)
      .map(ref => ({ question: ref, answer: this.draft()[ref.id] ?? null }));
  });

  private push(id: string, patch: Partial<Answer>) {
    if (this.readOnly()) return;
    const next = { ...this.draft() };
    next[id] = { ...this.answerFor(id), ...patch, question_id: id };
    this.draft.set(next);
    const a = next[id];
    this.saves.next({
      questionId: id,
      body: { value: a.value ?? null, choices: a.choices ?? null, comment: a.comment ?? null },
    });
  }

  onText(id: string, value: string) {
    // "" is a real edit; only an untouched question stays NULL.
    this.push(id, { value });
  }

  onComment(id: string, comment: string) { this.push(id, { comment }); }

  toggleChoice(q: Question, option: string) {
    const existing = this.answerFor(q.id).choices ?? [];
    let choices: string[];
    if (q.multi_select) {
      choices = existing.includes(option)
        ? existing.filter(o => o !== option)
        : [...existing, option];
    } else {
      choices = existing.includes(option) ? [] : [option];
    }
    this.push(q.id, { choices });
  }

  isChosen(q: Question, option: string): boolean {
    return (this.answerFor(q.id).choices ?? []).includes(option);
  }

  begin() {
    this.stage.set('questions');
    this.current.set(0);
    window.scrollTo({ top: 0 });
  }

  showIntro() {
    this.stage.set('intro');
    this.showList.set(false);
    window.scrollTo({ top: 0 });
  }

  go(i: number) {
    this.stage.set('questions');
    this.current.set(Math.max(0, Math.min(i, this.questions().length - 1)));
    this.showList.set(false);
    window.scrollTo({ top: 0 });
  }

  openSubmit() {
    this.api.submitPreview(this.token).subscribe(p => this.preview.set(p));
  }

  confirmSubmit() {
    this.submitting.set(true);
    this.api.submit(this.token).subscribe({
      next: v => { this.view.set(v); this.preview.set(null); this.submitting.set(false); },
      error: err => {
        this.submitting.set(false);
        this.error.set(err?.error?.detail ?? 'Could not submit.');
      },
    });
  }

  jumpToNum(num: string) {
    const i = this.questions().findIndex(q => q.num === num);
    if (i >= 0) this.go(i);
  }
}

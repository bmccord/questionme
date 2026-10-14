import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { Api } from '../api';
import { AdminQuestionRow, CandidateDetail } from '../models';

/**
 * A printable record of one candidate.
 *
 * Deliberately not a server-rendered PDF. The browser's own print engine
 * paginates flowing text, keeps a question with its answer, and embeds fonts
 * properly - all of which would otherwise mean a large rendering dependency
 * in the API image for a document that is read a handful of times.
 *
 * The baseline is Nathan Tate's private answers. It is included by default
 * because the usual reader is Brian, but it can be switched off before
 * printing something to hand round a committee.
 */
@Component({
  selector: 'qm-print',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './print.html',
  styleUrl: './print.css',
})
export class PrintComponent {
  private api = inject(Api);
  private route = inject(ActivatedRoute);

  id = Number(this.route.snapshot.paramMap.get('id'));
  data = signal<CandidateDetail | null>(null);

  includeBaseline = true;
  includeVerdicts = true;
  unansweredToo = true;

  /** The comparison text quotes and paraphrases the baseline - "the baseline
   *  says No, the kingdom is already established", and for multiple choice it
   *  prints the baseline's selections outright. So there is no useful
   *  "comparison without baseline": dropping one has to drop the other, or
   *  the privacy control is a fiction. */
  onBaselineToggle() {
    if (!this.includeBaseline) this.includeVerdicts = false;
  }

  printedOn = new Date();

  constructor() {
    this.api.candidate(this.id).subscribe(d => this.data.set(d));
  }

  rows = computed<AdminQuestionRow[]>(() => {
    const all = this.data()?.questions ?? [];
    return this.unansweredToo ? all : all.filter(q => this.hasAnswer(q));
  });

  counts = computed(() => {
    const all = this.data()?.questions ?? [];
    return { total: all.length, answered: all.filter(q => this.hasAnswer(q)).length };
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
      .sort(a => (a.part === 'answer' ? -1 : 1));
  }

  print() { window.print(); }
}

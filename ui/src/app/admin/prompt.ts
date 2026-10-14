import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Api } from '../api';
import { PromptSet } from '../models';

@Component({
  selector: 'qm-prompt',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <header>
      <div>
        <a routerLink="/admin" class="back">← Candidates</a>
        <h1>Comparison prompt</h1>
        <p class="sub">
          @if (data()?.active; as a) {
            Version {{ a.version }} is active.
          } @else {
            No version saved yet. The built-in prompt is in force and is loaded
            below — edit it and save to make it version 1.
          }
        </p>
      </div>
    </header>

    <p class="explain">
      This is the instruction Claude follows when comparing a candidate's
      free-text answer to the baseline. It lives in the database, not in the
      code, so it can be changed without a deploy — and it is never committed
      to the public repository.
    </p>
    <p class="explain">
      <strong>Saving creates a new version rather than overwriting.</strong>
      Comparisons record the version that produced them, so results from
      different weeks stay comparable. Existing verdicts are not recomputed;
      re-run a candidate, or a single question, when you want them refreshed.
    </p>

    <textarea rows="26" [(ngModel)]="body" spellcheck="false"></textarea>

    <div class="actions">
      <span class="count">{{ body.length }} characters</span>
      <button type="button" (click)="reload()">Revert</button>
      <button type="button" class="primary" [disabled]="saving() || !body.trim()"
              (click)="save()">
        {{ saving() ? 'Saving…' : 'Save as new version' }}
      </button>
    </div>
    @if (saved()) { <p class="ok">Saved as version {{ saved() }}.</p> }

    @if (data()?.versions?.length) {
      <h2>History</h2>
      <table>
        <tr><th>Version</th><th>Created</th><th></th></tr>
        @for (v of data()!.versions; track v.id) {
          <tr>
            <td class="num">{{ v.version }}</td>
            <td class="num">{{ v.created_at | date:'medium' }}</td>
            <td>@if (v.is_active) { <span class="pill">active</span> }</td>
          </tr>
        }
      </table>
    }
  `,
  styles: [`
    :host { display: block; max-width: 54rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
    h1 { font-size: 1.3rem; margin: .25rem 0; }
    h2 { font-size: 1rem; margin-top: 2.5rem; }
    .back { font-size: .85rem; color: #2f6f4f; text-decoration: none; }
    .sub { margin: 0; font-size: .88rem; color: #55555f; }
    .explain { font-size: .9rem; color: #44444c; line-height: 1.6; max-width: 46rem; }
    textarea { width: 100%; box-sizing: border-box; font: 13px/1.6 ui-monospace, monospace;
               padding: .9rem; border: 1px solid #ccccd4; border-radius: 6px; }
    .actions { display: flex; align-items: center; gap: .6rem; margin-top: .75rem; }
    .count { flex: 1; font-size: .82rem; color: #8a8a94; }
    button { font: inherit; padding: .5rem .9rem; border: 1px solid #ccccd4;
             background: #fff; border-radius: 6px; cursor: pointer; }
    button.primary { background: #2f6f4f; border-color: #2f6f4f; color: #fff; }
    button:disabled { opacity: .5; }
    .ok { color: #23593f; font-size: .9rem; }
    table { width: 100%; border-collapse: collapse; font-size: .9rem; }
    th { text-align: left; font-size: .76rem; text-transform: uppercase;
         color: #7a7a85; padding: .4rem .5rem; border-bottom: 1px solid #e3e3e8; }
    td { padding: .5rem; border-bottom: 1px solid #f0f0f4; }
    td.num { font-variant-numeric: tabular-nums; }
    .pill { font-size: .75rem; padding: .15rem .55rem; border-radius: 999px;
            background: #e4f1e9; color: #23593f; }
  `],
})
export class PromptComponent {
  private api = inject(Api);

  data = signal<PromptSet | null>(null);
  body = '';
  saving = signal(false);
  saved = signal<number | null>(null);

  constructor() { this.reload(); }

  reload() {
    this.api.prompts().subscribe(d => {
      this.data.set(d);
      // Open on whatever is actually in force - the saved version, or the
      // built-in fallback - so this is an edit rather than a blank page.
      this.body = d.active?.body ?? d.fallback ?? '';
    });
  }

  save() {
    this.saving.set(true);
    this.api.savePrompt(this.body).subscribe({
      next: r => { this.saving.set(false); this.saved.set(r.version); this.reload(); },
      error: () => this.saving.set(false),
    });
  }
}

import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../api';
import { CandidateRow } from '../models';

@Component({
  selector: 'qm-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <header>
      <h1>Candidates</h1>
      <div class="headactions">
        <a routerLink="/admin/prompt" class="plain">Comparison prompt</a>
        <button type="button" (click)="logout()">Sign out</button>
      </div>
    </header>

    <form class="invite" (ngSubmit)="invite()">
      <input name="n" [(ngModel)]="name" placeholder="Candidate name" required />
      <input name="e" [(ngModel)]="email" placeholder="Email (optional)" />
      <button type="submit" [disabled]="!name.trim()">Invite</button>
    </form>

    @if (newLink(); as l) {
      <div class="link">
        <p>Send this link to {{ newName() }}. It is the only way in — there is no password.</p>
        <code>{{ l }}</code>
        <button type="button" (click)="copy(l)">{{ copied() ? 'Copied' : 'Copy' }}</button>
      </div>
    }

    @if (pendingDelete(); as p) {
      <div class="scrim" (click)="cancelDelete()"></div>
      <div class="modal" role="dialog" aria-modal="true">
        <h3>Delete {{ p.name }}?</h3>
        @if (p.status === 'submitted') {
          <p class="warn">
            <strong>{{ p.name }} has already submitted.</strong> Their link locked
            when they did, so they cannot fill it in again. Deleting removes their
{{ p.answered }} {{ p.answered === 1 ? 'answer' : 'answers' }} permanently.
          </p>
          <p>Type <strong>{{ p.name }}</strong> to confirm:</p>
          <input [(ngModel)]="confirmName" name="cn" placeholder="Candidate name" />
        } @else {
          <p>
This removes the candidate and their {{ p.answered }}
            saved {{ p.answered === 1 ? 'answer' : 'answers' }}.
            Their link stops working. This cannot be undone.
          </p>
        }
        @if (deleteError()) { <p class="err">{{ deleteError() }}</p> }
        <div class="modalactions">
          <button type="button" (click)="cancelDelete()">Cancel</button>
          <button type="button" class="danger solid" [disabled]="deleting()"
                  (click)="doDelete()">
            {{ deleting() ? 'Deleting…' : 'Delete permanently' }}
          </button>
        </div>
      </div>
    }

    <table>
      <thead>
        <tr><th>Name</th><th>Status</th><th>Answered</th><th>Submitted</th><th></th></tr>
      </thead>
      <tbody>
        @for (c of rows(); track c.id) {
          <tr>
            <td><a [routerLink]="['/admin/c', c.id]">{{ c.name }}</a>
                @if (c.email) { <div class="sub">{{ c.email }}</div> }</td>
            <td><span class="pill {{ c.status }}">{{ label(c.status) }}</span></td>
            <td class="num">{{ c.answered }} / {{ c.total }}</td>
            <td class="num">{{ c.submitted_at ? (c.submitted_at | date:'mediumDate') : '—' }}</td>
            <td class="rowactions">
              <button type="button" class="small" (click)="copy(c.link)">Copy link</button>
              <button type="button" class="small danger" (click)="askDelete(c)">Delete</button>
            </td>
          </tr>
        } @empty {
          <tr><td colspan="5" class="empty">No candidates yet.</td></tr>
        }
      </tbody>
    </table>
  `,
  styles: [`
    :host { display: block; max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
    header { display: flex; justify-content: space-between; align-items: center; }
    h1 { font-size: 1.3rem; margin: 0; }
    .invite { display: flex; gap: .5rem; margin: 1.25rem 0; flex-wrap: wrap; }
    .invite input { flex: 1 1 12rem; font: inherit; padding: .5rem;
                    border: 1px solid #ccccd4; border-radius: 6px; }
    .link { background: #f2f7f4; border: 1px solid #cfe3d8; border-radius: 8px;
            padding: .9rem 1rem; margin-bottom: 1.25rem; }
    .link p { margin: 0 0 .5rem; font-size: .88rem; }
    .link code { display: block; word-break: break-all; font-size: .82rem; margin-bottom: .6rem; }
    table { width: 100%; border-collapse: collapse; font-size: .92rem; }
    th { text-align: left; font-size: .78rem; text-transform: uppercase;
         letter-spacing: .05em; color: #7a7a85; padding: .5rem .6rem;
         border-bottom: 1px solid #e3e3e8; }
    td { padding: .7rem .6rem; border-bottom: 1px solid #f0f0f4; vertical-align: top; }
    td.num { font-variant-numeric: tabular-nums; }
    .sub { font-size: .8rem; color: #7a7a85; }
    .empty { color: #7a7a85; text-align: center; padding: 2rem; }
    .pill { font-size: .75rem; padding: .15rem .55rem; border-radius: 999px; }
    .pill.not_started { background: #f0f0f4; color: #55555f; }
    .pill.in_progress { background: #fdf6e6; color: #8a6d22; }
    .pill.submitted { background: #e4f1e9; color: #23593f; }
    button { font: inherit; padding: .5rem .85rem; border: 1px solid #ccccd4;
             background: #fff; border-radius: 6px; cursor: pointer; }
    button.small { padding: .25rem .55rem; font-size: .8rem; }
    a { color: #2f6f4f; }
    .headactions { display: flex; align-items: center; gap: .9rem; }
    a.plain { font-size: .9rem; }
    .rowactions { display: flex; gap: .35rem; }
    button.danger { color: #9a2a1a; border-color: #e0bdb4; }
    button.danger.solid { background: #9a2a1a; border-color: #9a2a1a; color: #fff; }
    .scrim { position: fixed; inset: 0; background: rgba(20,20,26,.45); z-index: 10; }
    .modal { position: fixed; z-index: 11; top: 50%; left: 50%;
             transform: translate(-50%,-50%); width: min(30rem, calc(100vw - 2rem));
             background: #fff; border-radius: 10px; padding: 1.4rem;
             box-shadow: 0 18px 50px rgba(0,0,0,.25); }
    .modal h3 { margin: 0 0 .75rem; }
    .modal input { width: 100%; box-sizing: border-box; font: inherit; padding: .5rem;
                   border: 1px solid #ccccd4; border-radius: 6px; }
    .warn { background: #fdeee6; border-left: 4px solid #9a2a1a;
            padding: .7rem .85rem; border-radius: 0 6px 6px 0; }
    .err { color: #8a2020; font-size: .88rem; }
    .modalactions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1.2rem; }
  `],
})
export class DashboardComponent {
  private api = inject(Api);
  private router = inject(Router);

  rows = signal<CandidateRow[]>([]);
  name = '';
  email = '';
  newLink = signal<string | null>(null);
  newName = signal('');
  copied = signal(false);
  pendingDelete = signal<CandidateRow | null>(null);
  confirmName = '';
  deleting = signal(false);
  deleteError = signal<string | null>(null);

  constructor() { this.load(); }

  private load() {
    this.api.candidates().subscribe({
      next: r => this.rows.set(r),
      error: () => this.router.navigateByUrl('/admin/login'),
    });
  }

  label(s: string) {
    return { not_started: 'Not started', in_progress: 'In progress', submitted: 'Submitted' }[s] ?? s;
  }

  invite() {
    this.api.invite(this.name.trim(), this.email.trim() || undefined).subscribe(r => {
      this.newLink.set(r.link);
      this.newName.set(r.name);
      this.name = ''; this.email = '';
      this.load();
    });
  }

  copy(text: string) {
    navigator.clipboard?.writeText(text).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }

  askDelete(c: CandidateRow) {
    this.pendingDelete.set(c);
    this.confirmName = '';
    this.deleteError.set(null);
  }

  cancelDelete() { this.pendingDelete.set(null); }

  doDelete() {
    const c = this.pendingDelete();
    if (!c) return;
    this.deleting.set(true);
    this.deleteError.set(null);
    this.api.deleteCandidate(c.id, c.status === 'submitted' ? this.confirmName : undefined)
      .subscribe({
        next: () => {
          this.deleting.set(false);
          this.pendingDelete.set(null);
          this.load();
        },
        error: err => {
          this.deleting.set(false);
          this.deleteError.set(err?.error?.detail ?? 'Could not delete.');
        },
      });
  }

  logout() { this.api.logout().subscribe(() => this.router.navigateByUrl('/admin/login')); }
}

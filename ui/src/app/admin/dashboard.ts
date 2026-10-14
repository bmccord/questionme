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
      <button type="button" (click)="logout()">Sign out</button>
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
            <td><button type="button" class="small" (click)="copy(c.link)">Copy link</button></td>
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

  logout() { this.api.logout().subscribe(() => this.router.navigateByUrl('/admin/login')); }
}

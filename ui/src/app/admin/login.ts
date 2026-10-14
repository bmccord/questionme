import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { Api } from '../api';

@Component({
  selector: 'qm-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <form class="box" (ngSubmit)="submit()">
      <h1>questionme</h1>
      <label>Username <input name="u" [(ngModel)]="username" autocomplete="username" /></label>
      <label>Password
        <input name="p" type="password" [(ngModel)]="password" autocomplete="current-password" />
      </label>
      @if (error()) { <p class="err">{{ error() }}</p> }
      <button type="submit" [disabled]="busy()">{{ busy() ? 'Signing in…' : 'Sign in' }}</button>
    </form>
  `,
  styles: [`
    :host { display: grid; place-items: center; min-height: 80vh; font: inherit; }
    .box { display: flex; flex-direction: column; gap: .9rem; width: min(22rem, 90vw);
           padding: 1.75rem; border: 1px solid #e3e3e8; border-radius: 10px; }
    h1 { margin: 0 0 .25rem; font-size: 1.15rem; }
    label { display: flex; flex-direction: column; gap: .3rem; font-size: .85rem; color: #55555f; }
    input { font: inherit; padding: .5rem; border: 1px solid #ccccd4; border-radius: 6px; }
    button { font: inherit; padding: .55rem; border: 0; border-radius: 6px;
             background: #2f6f4f; color: #fff; cursor: pointer; }
    button:disabled { opacity: .5; }
    .err { color: #8a2020; font-size: .85rem; margin: 0; }
  `],
})
export class LoginComponent {
  private api = inject(Api);
  private router = inject(Router);

  username = '';
  password = '';
  error = signal<string | null>(null);
  busy = signal(false);

  submit() {
    this.busy.set(true);
    this.error.set(null);
    this.api.login(this.username, this.password).subscribe({
      next: () => this.router.navigateByUrl('/admin'),
      error: err => {
        this.busy.set(false);
        this.error.set(err?.status === 429
          ? 'Too many attempts. Wait a few minutes.'
          : 'Wrong username or password.');
      },
    });
  }
}

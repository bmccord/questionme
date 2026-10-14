import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Answer, CandidateDetail, CandidateRow, CandidateView, SubmitPreview,
} from './models';

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);

  // --- candidate -----------------------------------------------------------
  view(token: string): Observable<CandidateView> {
    return this.http.get<CandidateView>(`/api/c/${token}`);
  }

  saveAnswer(token: string, questionId: string, body: Partial<Answer>): Observable<Answer> {
    return this.http.put<Answer>(`/api/c/${token}/answers/${questionId}`, body);
  }

  submitPreview(token: string): Observable<SubmitPreview> {
    return this.http.get<SubmitPreview>(`/api/c/${token}/submit`);
  }

  submit(token: string): Observable<CandidateView> {
    return this.http.post<CandidateView>(`/api/c/${token}/submit`, {});
  }

  // --- admin ---------------------------------------------------------------
  login(username: string, password: string) {
    return this.http.post<{ ok: boolean }>('/api/admin/login', { username, password },
      { withCredentials: true });
  }

  logout() {
    return this.http.post('/api/admin/logout', {}, { withCredentials: true });
  }

  me() {
    return this.http.get<{ user: string }>('/api/admin/me', { withCredentials: true });
  }

  candidates(): Observable<CandidateRow[]> {
    return this.http.get<CandidateRow[]>('/api/admin/candidates', { withCredentials: true });
  }

  invite(name: string, email?: string) {
    return this.http.post<{ id: number; name: string; link: string }>(
      '/api/admin/candidates', { name, email }, { withCredentials: true });
  }

  candidate(id: number): Observable<CandidateDetail> {
    return this.http.get<CandidateDetail>(`/api/admin/candidates/${id}`,
      { withCredentials: true });
  }

  runComparison(id: number) {
    return this.http.post(`/api/admin/candidates/${id}/compare`, {},
      { withCredentials: true });
  }

  addNote(id: number, body: string) {
    return this.http.post(`/api/admin/candidates/${id}/notes`, { body },
      { withCredentials: true });
  }
}

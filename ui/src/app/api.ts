import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AdminQuestionRow, Answer, BaselineEdit, CandidateDetail, CandidateRow,
  CandidateView, ComparisonStatus, PromptSet, SubmitPreview,
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

  deleteCandidate(id: number, confirmName?: string) {
    const q = confirmName ? `?confirm=${encodeURIComponent(confirmName)}` : '';
    return this.http.delete<{ deleted: string; answers: number; comparisons: number;
                              notes: number }>(
      `/api/admin/candidates/${id}${q}`, { withCredentials: true });
  }

  candidate(id: number): Observable<CandidateDetail> {
    return this.http.get<CandidateDetail>(`/api/admin/candidates/${id}`,
      { withCredentials: true });
  }

  runComparison(id: number) {
    return this.http.post(`/api/admin/candidates/${id}/compare`, {},
      { withCredentials: true });
  }

  candidateQuestion(id: number, questionId: string): Observable<AdminQuestionRow> {
    return this.http.get<AdminQuestionRow>(
      `/api/admin/candidates/${id}/questions/${questionId}`, { withCredentials: true });
  }

  runOneComparison(id: number, questionId: string) {
    return this.http.post(`/api/admin/candidates/${id}/compare/${questionId}`, {},
      { withCredentials: true });
  }

  comparisonStatus(id: number): Observable<ComparisonStatus> {
    return this.http.get<ComparisonStatus>(
      `/api/admin/candidates/${id}/compare/status`, { withCredentials: true });
  }

  editQuestion(questionId: string, body: Partial<BaselineEdit>) {
    return this.http.put(`/api/admin/questions/${questionId}`, body,
      { withCredentials: true });
  }

  prompts(): Observable<PromptSet> {
    return this.http.get<PromptSet>('/api/admin/prompt', { withCredentials: true });
  }

  savePrompt(body: string) {
    return this.http.post<{ id: number; version: number }>('/api/admin/prompt',
      { body }, { withCredentials: true });
  }

  addNote(id: number, body: string) {
    return this.http.post(`/api/admin/candidates/${id}/notes`, { body },
      { withCredentials: true });
  }
}

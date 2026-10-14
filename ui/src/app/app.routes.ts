import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'q/:token',
    loadComponent: () => import('./candidate/candidate').then(m => m.CandidateComponent),
  },
  {
    path: 'admin/login',
    loadComponent: () => import('./admin/login').then(m => m.LoginComponent),
  },
  {
    path: 'admin/prompt',
    loadComponent: () => import('./admin/prompt').then(m => m.PromptComponent),
  },
  {
    path: 'admin/c/:id',
    loadComponent: () => import('./admin/detail').then(m => m.DetailComponent),
  },
  {
    path: 'admin',
    loadComponent: () => import('./admin/dashboard').then(m => m.DashboardComponent),
  },
  { path: '', redirectTo: 'admin', pathMatch: 'full' },
  { path: '**', redirectTo: 'admin' },
];
